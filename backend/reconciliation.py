"""
Reconciliation Engine — Data integrity checks between Raw and Working data.
"""
import pandas as pd
from core.logger import get_logger

logger = get_logger(__name__)


class ReconciliationEngine:
    """Verify data integrity between pipeline stages."""

    def __init__(self, raw_df, working_df):
        self.raw_df = raw_df
        self.working_df = working_df

    def run_all_checks(self) -> dict:
        """Run all reconciliation checks, return structured health report."""
        logger.info("Running reconciliation integrity checks")
        results = {"checks": [], "overall": "PASS"}

        # Check 1: Row count sanity
        raw_count = len(self.raw_df)
        working_count = len(self.working_df)
        summary_rows = len(self.raw_df[
            self.raw_df['Desc1'].astype(str).str.contains('~Date summary', na=False)
        ])
        expected_working = raw_count - summary_rows
        results["checks"].append({
            "name": "Row Count Integrity",
            "raw_rows": int(raw_count),
            "summary_rows_removed": int(summary_rows),
            "working_rows": int(working_count),
            "expected_working_rows": int(expected_working),
            "passed": bool(working_count == expected_working),
        })

        # Check 2: Credit sum match
        raw_txn = self.raw_df[
            ~self.raw_df['Desc1'].astype(str).str.contains('~Date summary', na=False)
        ]
        raw_credit = pd.to_numeric(
            raw_txn['Credit'].astype(str).str.replace(',', ''), errors='coerce'
        ).fillna(0).sum()
        working_credit = pd.to_numeric(
            self.working_df['Credit'].astype(str).str.replace(',', ''), errors='coerce'
        ).fillna(0).sum()
        results["checks"].append({
            "name": "Credit Sum Integrity",
            "raw_credit_sum": round(float(raw_credit), 2),
            "working_credit_sum": round(float(working_credit), 2),
            "passed": bool(abs(raw_credit - working_credit) < 0.01),
        })

        # Check 3: Debit sum match
        raw_debit = pd.to_numeric(
            raw_txn['Debit'].astype(str).str.replace(',', ''), errors='coerce'
        ).fillna(0).sum()
        working_debit = pd.to_numeric(
            self.working_df['Debit'].astype(str).str.replace(',', ''), errors='coerce'
        ).fillna(0).sum()
        results["checks"].append({
            "name": "Debit Sum Integrity",
            "raw_debit_sum": round(float(raw_debit), 2),
            "working_debit_sum": round(float(working_debit), 2),
            "passed": bool(abs(raw_debit - working_debit) < 0.01),
        })

        # Check 4: Channel coverage
        if 'Channel' in self.working_df.columns:
            channel_counts = {
                str(k): int(v) for k, v in self.working_df['Channel'].value_counts().to_dict().items()
            }
            uncategorized = channel_counts.get('Other', 0) + channel_counts.get('', 0)
            total = len(self.working_df)
            results["checks"].append({
                "name": "Channel Classification Coverage",
                "channel_breakdown": channel_counts,
                "uncategorized_count": int(uncategorized),
                "coverage_pct": round(float((total - uncategorized) / max(total, 1) * 100), 1),
                "passed": True,
            })

        # Overall
        for c in results["checks"]:
            if not c["passed"]:
                results["overall"] = "FAIL"
                logger.warning("Reconciliation check failed", extra={"check": c["name"], "details": c})
            else:
                logger.info("Reconciliation check passed", extra={"check": c["name"]})

        logger.info(f"Reconciliation completed with overall status: {results['overall']}")
        return results
