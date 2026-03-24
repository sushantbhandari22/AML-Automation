"""
FastAPI REST API for AML Report Generation.
Provides endpoints for file upload, verification, report generation, and download.
"""
import os
import shutil
import uuid
import io
import json
import zipfile
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import traceback
import gc
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pipeline import AMLReportGenerator
from core.metadata import MetadataExtractor
from core.processor import DataProcessor
from reconciliation import ReconciliationEngine
from core.logger import get_logger, session_ctx_var

logger = get_logger(__name__)


def sanitize_for_json(obj):
    """Recursively convert numpy/pandas types to native Python types."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if pd.isna(obj):
        return None
    return obj

app = FastAPI(title="AML Report Generator API", version="1.0.0")

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_dir(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, session_id)


def _output_dir(session_id: str) -> str:
    return os.path.join(_session_dir(session_id), "output")


# ── Sniff headers to detect file type ─────────────────────────────────
EXPECTED_RAW_HEADERS = {"Tran Date", "Desc1", "Debit", "Credit", "Balance"}
EXPECTED_WORKING_HEADERS = {"Channel", "Year"}


def _detect_file_type(df: pd.DataFrame) -> str:
    cols = set(df.columns)
    if EXPECTED_RAW_HEADERS.issubset(cols):
        if EXPECTED_WORKING_HEADERS.issubset(cols):
            return "processed"  # already has Channel + Year
        return "raw"
    return "unknown"


# ── Upload ────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload CSV/XLSX, sniff headers, return detected type + preview."""
    session_id = str(uuid.uuid4())
    session_ctx_var.set(session_id)
    logger.info("Received file upload", extra={"filename": file.filename})

    sess_dir = _session_dir(session_id)
    os.makedirs(sess_dir, exist_ok=True)

    # Save uploaded file
    ext = os.path.splitext(file.filename)[1].lower()
    raw_path = os.path.join(sess_dir, f"raw_data{ext}")
    with open(raw_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Read & sniff
    try:
        if ext == ".csv":
            df = pd.read_csv(raw_path)
        else:
            df = pd.read_excel(raw_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    file_type = _detect_file_type(df)
    columns = list(df.columns)
    preview = df.head(5).fillna("").to_dict(orient="records")

    # Extract min/max dates from Tran Date column if present
    start_date, end_date = None, None
    if "Tran Date" in df.columns:
        try:
            temp_dates = pd.to_datetime(df["Tran Date"], errors='coerce').dropna()
            if not temp_dates.empty:
                start_date = temp_dates.min().strftime('%Y-%m-%d')
                end_date = temp_dates.max().strftime('%Y-%m-%d')
        except Exception:
            pass

    detected_metadata = MetadataExtractor.extract_from_file(raw_path)
    if start_date: detected_metadata['start_date'] = start_date
    if end_date: detected_metadata['end_date'] = end_date

    return JSONResponse(content=sanitize_for_json({
        "session_id": session_id,
        "file_type": file_type,
        "columns": columns,
        "row_count": len(df),
        "preview": preview,
        "detected_metadata": detected_metadata,
        "message": (
            "Raw Data detected. System will generate Main, Working, and Pivot sheets."
            if file_type == "raw"
            else "Processed data detected." if file_type == "processed"
            else "Unknown format. Please check column headers."
        ),
    }))


# ── Verify ────────────────────────────────────────────────────────────
@app.post("/api/verify")
async def verify_data(session_id: str = Form(...)):
    """Run reconciliation checks on uploaded data."""
    session_ctx_var.set(session_id)
    logger.info("Starting data verification")
    
    sess_dir = _session_dir(session_id)
    if not os.path.exists(sess_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    # Find raw file
    raw_path = None
    for f in os.listdir(sess_dir):
        if f.startswith("raw_data"):
            raw_path = os.path.join(sess_dir, f)
            break

    if not raw_path:
        raise HTTPException(status_code=400, detail="No uploaded file found")

    # Read
    if raw_path.endswith('.csv'):
        raw_df = pd.read_csv(raw_path)
    else:
        raw_df = pd.read_excel(raw_path)

    # Clean numerics
    for col in ['Debit', 'Credit', 'Balance']:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(
                raw_df[col].astype(str).str.replace(',', ''), errors='coerce'
            ).fillna(0)

    # Quick working filter for reconciliation
    working_df = raw_df[
        ~raw_df['Desc1'].astype(str).str.contains('~Date summary', na=False)
    ].copy()

    # Re-use pipeline categorization logic so reconciliation matches pipeline exactly
    gen = DataProcessor(raw_path)
    working_df['Channel'] = working_df.apply(gen.classify_channel, axis=1)

    engine = ReconciliationEngine(raw_df, working_df)
    report = engine.run_all_checks()
    return JSONResponse(content=sanitize_for_json(report))


# ── Generate Reports ──────────────────────────────────────────────────
@app.post("/api/generate")
async def generate_reports(
    session_id: str = Form(...),
    bank_name: str = Form(""),
    branch_name: str = Form(""),
    account_name: str = Form(""),
    account_number: str = Form(""),
    account_type: str = Form(""),
    nature_of_account: str = Form(""),
    currency: str = Form("NPR"),
    start_date: str = Form(""),
    end_date: str = Form(""),
    annexes: str = Form("I,II,III,IV,TreeMap"),  # comma-separated
):
    """Generate selected AML reports with provided metadata."""
    session_ctx_var.set(session_id)
    logger.info("Starting report generation", extra={"bank_name": bank_name, "annexes": annexes})
    
    sess_dir = _session_dir(session_id)
    if not os.path.exists(sess_dir):
        raise HTTPException(status_code=404, detail="Session not found")

    raw_path = None
    for f in os.listdir(sess_dir):
        if f.startswith("raw_data"):
            raw_path = os.path.join(sess_dir, f)
            break
    if not raw_path:
        raise HTTPException(status_code=400, detail="No uploaded file found")

    output = _output_dir(session_id)
    meta = {
        "Bank Name": bank_name,
        "Branch Name": branch_name,
        "Account Name": account_name,
        "Account Number": account_number,
        "Account Type": account_type,
        "Nature of Account": nature_of_account,
        "Currency": currency,
        "Start Date": start_date,
        "End Date": end_date,
    }

    try:
        gen = AMLReportGenerator(raw_path, output, meta)

        # Parse selected annex list from comma-separated string
        annex_list = [a.strip().upper() for a in annexes.split(',') if a.strip()]
        if not annex_list:
            annex_list = ["I", "II", "III", "IV", "TREEMAP"]

        # Execute unified pipeline with all integrity checks
        pipeline_results = gen.run_full_pipeline(annex_list=annex_list)
        
        # Now returns a list of filenames
        filenames = pipeline_results['report']

        response_data = {
            "status": "success",
            "generated": ["Annex_Report", "Bank_Report"],
            "files": filenames,
            "output_dir": output,
            "integrity": pipeline_results.get('integrity'),
            "balance": pipeline_results.get('balance')
        }

        # Force garbage collection for large pandas DataFrames residing in the pipeline memory
        del gen
        del pipeline_results
        gc.collect()

        return response_data

    except ValueError as ve:
        logger.error("Validation Error during report generation", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Critical Pipeline Error during report generation", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")


# ── Download individual file ──────────────────────────────────────────
@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    """Download a single generated report."""
    path = os.path.join(_output_dir(session_id), filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)


# ── Download all as ZIP ───────────────────────────────────────────────
@app.get("/api/download-all/{session_id}")
async def download_all(session_id: str):
    """Download all generated reports as a ZIP archive."""
    output = _output_dir(session_id)
    if not os.path.exists(output):
        raise HTTPException(status_code=404, detail="No reports found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(output):
            fpath = os.path.join(output, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, fname)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=AML_Reports_{session_id[:8]}.zip"},
    )


# ── Health check ──────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/lookup/{account_number}")
async def lookup_account(account_number: str):
    """Real-time lookup for account metadata."""
    metadata = MetadataExtractor.lookup_account(account_number)
    return JSONResponse(content=sanitize_for_json(metadata))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
