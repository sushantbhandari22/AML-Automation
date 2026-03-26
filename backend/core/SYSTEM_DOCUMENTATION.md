# Automated AML Report Generation - System Documentation

This document provides a professional technical overview of the system architecture, core logic, and strategies implemented in the AML Report Generation pipeline.

## 1. Directory Structure

```text
AUTOMATION/
├── backend/
│   ├── app.py              # FastAPI REST API (Endpoints, Upload, Generation)
│   ├── pipeline.py         # Unified Pipeline Orchestrator
│   ├── reconciliation.py   # Data Integrity & Verification Engine
│   ├── core/
│   │   ├── processor.py    # Formatting & Channel Categorization
│   │   ├── validator.py    # Data Integrity Checks
│   ├── exporter.py     # Generates Annex_Report and Bank_Report
│   └── styler.py       # Openpyxl-based Visual Styling
└── frontend/
    ├── src/
    │   ├── App.jsx         # Main Application UI (Handles multiple downloads)
    │   └── App.css         # Modern, Premium Styling
```

## 2. Core Operational Logic

### Dual-Workbook Export
To maintain professional separation between accounting reports and raw audit data, the system now generates two distinct Excel files:

1. **Annex_Report_<session>.xlsx**:
   - Contains: `REPORT_SUMMARY`, `Annex-I`, `Annex-II`, `Annex-III`, `Annex-IV`, and `TreeMap`.
   - Formatted for final submission to management or regulators.
2. **Bank_Report_<session>.xlsx**:
   - Contains: `MAIN_DATASET`, `WORKING_DATASET`, `PIVOT_YEAR`, `PIVOT_CHANNEL`, and `PIVOT_MOBILE`.
   - Formatted for internal audit, verification, and deep-dive analysis.

### Smart Auto-Compliance & Windows
The system automates the selection of reporting windows based on standardized AML requirements. This ensures the output is compliant by default without requiring manual user input for every run.

| Report Component | Target Window | Calculation Logic |
| :--- | :--- | :--- |
| **Annex I (Statement)** | Last 2 Years | `End Date - 2 Years` |
| **Annex III (Deposits)** | Last 1 Year | `End Date - 1 Year` |
| **Annex IV (Withdrawals)**| Last 1 Year | `End Date - 1 Year` |
| **Annex II (Annual)** | Custom / All Time | Aggregates all years present in data |
| **TreeMap & Summary** | Last 2 Years | Matches the Annex I statement scope |

**Date Resolution Strategy**:
1. **User Input Override**: If the user provides a Start/End date in the UI, it acts as the global boundary.
2. **Data-Driven Discovery**: If inputs are blank, the backend automatically scans the `Tran Date` column of the entire dataset to find the min/max bounds.
3. **Annex limiting**: For specific annexes (I, III, IV), the system calculates the relative window (e.g., 2y). If the dataset is shorter than 2 years, it gracefully uses the available global start.

### Reversal Filtering Logic
To ensure financial accuracy in summaries and Top 10 reports, the system automatically identifies and excludes "Reversal" transactions.
- **Trigger**: Scans `Desc1` and `Remarks` for keywords "REV", "Reversal", or "~Date summary".
- **Impact**: Filtered rows are excluded from Annex III (Deposits), Annex IV (Withdrawals), and the Pivot summaries, preventing double-counting of reversed funds.

### Channel Mapping Engine
Standardizes diverse bank descriptions into curated logical channels using a prioritized keyword matcher.
- **Priority Rules**:
    1. `E-SEWA`: "ESEWA", "E-SEWA"
    2. `FONEPAY`: "FONEPAY", "FPAY", "QR_PAY"
    3. `CIPS`: "ConnectIPS", "CIP", "NPI"
    4. `CARD TXN`: "ATM", "VISA", "SCT", "POS"
    5. `MOBILE BANKING`: "MOBILE", "M-BANKING", "MBANK"
- **Fallback**: Anything not matching a rule is labeled as `OTHER`.

## 3. Data Integrity & Reconciliation
The system performs a 3-layer verification before report generation:
1. **Checksum Verification**: Ensures Total Debit - Total Credit correctly calculates the Closing Balance.
2. **Flow Integrity**: Confirms that the "Recalculated Balance" matches the "Reported Balance" from the bank file for every single row.
3. **Reversal Audit**: Provides a log of excluded transactions for audit transparency.

## 4. Technical Strategy

- **Zero-Touch Date Discovery**: Backend automatically scans both file headers and transaction columns to auto-fill the report date range (Start/End Date) upon upload.
- **Manual Metadata Entry**: Primary account metadata (Bank Name, Account Number) is entered by the user to ensure 100% accuracy in the final reports.
- **Hybrid Performance**: Uses `Pandas` for high-speed data crunching and `Openpyxl` for precise post-processing and visual styling.
- **Session Isolation**: Each user request is handled in a unique UUID-based session directory to prevent data leakage and ensure multi-user compatibility.

## 5. Observability & Logging Architecture

The system implements a structured logging strategy intended for immediate error tracking and business logic analytics.
- **Physical Log Storage**: All critical pipeline, system, and business logic events are continuously saved to **`backend/logs/system.log`**.
- **Log Rotation Protection**: A `RotatingFileHandler` is active to cap the file size at 10MB per file, keeping a maximum of 5 historical backups (e.g., `system.log.1`), preventing unrestricted disk space consumption.
- **Context-Aware Correlation**: Uses Python `contextvars` to automatically inject a global `session_id` into all relevant log entries, ensuring you can trace a user's exact path from upload to generated report.
- **JSON Formatting**: Configured via `backend/core/logger.py` to output machine-readable JSON logs for rapid parsing and ingestion into log monitoring tools.
- **Business Logic Telemetry**: The `ReconciliationEngine` explicitly tracks and logs when internal logic fails (e.g., checksum validation) separately from code crashes, giving insight into data-level corruption.
- **User Audit Trail**: Every significant user action (Login, Logout, Report Generation) is now formally recorded in the `system.log`. Log entries include the specific authenticated user (e.g., `"user": "sushant"`), ensuring full accountability for all system operations.
