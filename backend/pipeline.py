"""
AML Report Generator — Pipeline Facade.

Thin orchestrator that coordinates the core modules:
  core.processor  → Data ingestion, classification, balance reconstruction
  core.validator   → Non-blocking integrity checks
  core.exporter    → Excel report generation
  core.metadata    → Account metadata extraction

Usage:
    gen = AMLReportGenerator(raw_path, output_dir, account_metadata)
    result = gen.run_full_pipeline()
"""
import os
from datetime import datetime, timedelta

from core.processor import DataProcessor
from core.validator import DataValidator
from core.exporter import ReportExporter
from core.metadata import MetadataExtractor
from core.logger import get_logger

logger = get_logger(__name__)


class AMLReportGenerator:
    """High-level facade for the AML report generation pipeline."""

    def __init__(self, raw_data_path: str, output_dir: str, account_metadata: dict):
        self.output_dir = output_dir
        self.meta = account_metadata
        os.makedirs(output_dir, exist_ok=True)

        # Initialize core components
        logger.info("Initializing AMLReportGenerator", extra={"output_dir": output_dir})
        self.processor = DataProcessor(raw_data_path)
        self.exporter = ReportExporter(output_dir, self.meta)

    # ── Full Pipeline ────────────────────────────────────────────────
    def run_full_pipeline(self, annex_list: list = None) -> dict:
        """Execute all stages: Ingest → Validate → Pivot → Export."""
        if annex_list is None:
            annex_list = ["I", "II", "III", "IV", "TREEMAP"]

        logger.info("Starting full pipeline execution", extra={"annexes": annex_list})

        # Stage 1-3: Ingest, Classify, Reconstruct Balances
        logger.info("Stage 1-3: Processor ingest and classify")
        self.processor.generate_main_and_working()

        # Stage 3a: Row Integrity Check
        integrity = DataValidator.validate_row_integrity(
            self.processor.raw_df,
            self.processor.main_df,
            self.processor.working_df,
        )

        # Stage 3b: Balance Check
        balance = DataValidator.validate_balance(self.processor.working_df)

        # Stage 4: Pivot Aggregation
        self.processor.generate_pivots()

        # Stage 4a: Pivot Cross-Check
        pivot_validation = DataValidator.validate_pivots(
            self.processor.working_df,
            self.processor.pivot_channel,
        )

        # Stage 4b: Global Assertions
        DataValidator.validate_financial_integrity(
            self.processor.working_df,
            self.processor.pivot_channel,
        )
        DataValidator.validate_rows(
            self.processor.raw_df,
            self.processor.main_df,
            self.processor.working_df,
        )

        logger.info("Stage 5: Starting Excel export")
        # Stage 5: Generate Workbook(s)
        report_paths = self.exporter.generate(
            main_df=self.processor.main_df,
            working_df=self.processor.working_df,
            pivot_year=self.processor.pivot_year,
            pivot_channel=self.processor.pivot_channel,
            pivot_mobile=self.processor.pivot_mobile,
            annex_list=annex_list,
        )

        logger.info("Pipeline execution completed successfully")

        return {
            "report": report_paths,
            "integrity": integrity,
            "balance": balance,
            "pivot_validation": pivot_validation,
        }


# Re-export MetadataExtractor for backward compatibility with app.py
__all__ = ["AMLReportGenerator", "MetadataExtractor"]


# ── CLI Entry Point ──────────────────────────────────────────────────
if __name__ == "__main__":
    account_metadata = {
        "Bank Name": "Jyoti Bikash Bank Limited",
        "Branch Name": "064 (Parwanipur Branch)",
        "Account Name": "Amir Husen Ansari",
        "Account Number": "06401300927516000001",
        "Account Type": "13",
        "Nature of Account": "Jyoti Smart Savings",
        "Currency": "NPR",
        "Start Date": "2026-01-20",
        "End Date": "2026-01-25",
    }

    bot = AMLReportGenerator(
        raw_data_path="raw_data.csv",
        output_dir="./Automated_AML_Reports",
        account_metadata=account_metadata,
    )
    result = bot.run_full_pipeline()
    print("Pipeline complete!", result)
