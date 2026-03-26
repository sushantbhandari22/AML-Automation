"""
core/processor.py — Data Ingestion, Classification, and Balance Reconstruction.

Responsibilities:
  - Read raw CSV/Excel data and clean numeric columns.
  - Parse dates and sort transactions chronologically.
  - Classify transaction channels using the keyword plan.
  - Reconstruct cumulative balances after filtering summary rows.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
class DataProcessor:

    """Handles all data transformation from raw ingestion to working dataset."""

    # ── Channel Keywords — ALL LOWERCASE (combined string is .lower()) ──
    _CHANNEL_RULES: List[Tuple[str, Callable[[str, str], bool]]] = [
        ("FD Deal",               lambda c, r: 'fd deal' in c or ('choose by user' in r and 'fd' in c)),
        ("Internal Transfer TXN", lambda c, _: 'trf' in c or 'transfer' in c),
        ("IPS TXN",               lambda c, _: any(k in c for k in ['cips', 'bnkft', 'nimb-xp', 'connectips', 'o/w ips', 'ips-'])),
        ("Clearing/RTGS TXN",     lambda c, _: any(k in c for k in ['owl clg chq', 'owchq', 'rtgs', 'rtgs fund trf', 'inc-ecc', 'chq presentment'])),
        ("FONEPAY TXN",           lambda c, _: any(k in c for k in ['fpay:ibft', 'fonepay', 'fpay'])),
        ("eSewa TXN",             lambda c, _: 'esewa' in c),
        ("Khalti TXN",            lambda c, _: any(k in c for k in ['khalti', 'khlt'])),
        ("NPS TXN",               lambda c, _: any(k in c for k in ['nps', 'nps-if'])),
        ("MOBILE BANKING",        lambda c, _: any(k in c for k in ['mob', 'mobile banking', 'jpp'])),
        ("SYSTEM TXN",            lambda c, _: any(k in c for k in ['int from', 'int to', 'normal int', 'charge', 'tax', 'fee', 'interestbank'])),
        ("CARD TXN",              lambda c, _: any(k in c for k in ['atm', 'atm card', 'visa'])),
        ("CASH TXN",              lambda c, _: any(k in c for k in ['cash', 'cash depo', 'home cheque', 'home chq', 'self', 'withdrawn by', 'cash recieve'])),
        ("Remit TXN",             lambda c, _: 'remit' in c),
        ("CHOOSE BY USER",        lambda c, _: 'choose by user' in c),
    ]

    def __init__(self, raw_data_path: str):
        """Ingest and clean the raw data file."""
        if raw_data_path.endswith('.csv'):
            self.raw_df = pd.read_csv(raw_data_path)
        else:
            self.raw_df = pd.read_excel(raw_data_path)

        # Enforce mandatory columns early
        required_cols = {'Tran Date', 'Debit', 'Credit', 'Balance'}
        missing = required_cols - set(self.raw_df.columns)
        if missing:
            raise ValueError(f"Uploaded file is missing required columns: {', '.join(missing)}")

        # Clean numeric columns + enforce absolute values (Fix #6)
        for col in ('Debit', 'Credit', 'Balance'):
            if col in self.raw_df.columns:
                self.raw_df[col] = pd.to_numeric(
                    self.raw_df[col].astype(str).str.replace(',', '', regex=False),
                    errors='coerce',
                ).fillna(0.0)
        # Guard: Debit and Credit must always be positive
        if 'Debit' in self.raw_df.columns:
            self.raw_df['Debit'] = self.raw_df['Debit'].abs()
        if 'Credit' in self.raw_df.columns:
            self.raw_df['Credit'] = self.raw_df['Credit'].abs()

        self.main_df = pd.DataFrame()
        self.working_df = pd.DataFrame()

    # ── Channel Classification ───────────────────────────────────────
    @staticmethod
    def classify_channel(row) -> str:
        """Priority-based keyword search across Desc1, Remarks, Channel, AND Tran Code.

        If no match is found in the combined string, a secondary pass checks
        Tran Id and Tran Code alone before falling back to 'OTHER'.
        """
        desc = str(row.get('Desc1', '')).lower()
        remarks = str(row.get('Remarks', '')).lower()
        raw_chan = str(row.get('Channel', '')).lower()
        tran_code = str(row.get('Tran Code', '')).lower()
        tran_id = str(row.get('Tran Id', '')).lower()
        combined = f"{desc} {remarks} {raw_chan} {tran_code}"

        # Primary pass: search combined string built from all descriptive fields
        for label, matcher in DataProcessor._CHANNEL_RULES:
            if matcher(combined, remarks):
                return label

        # Secondary pass: Desc1/Remarks may be blank — try Tran Id + Tran Code alone
        id_code = f"{tran_id} {tran_code}".strip()
        if id_code:
            for label, matcher in DataProcessor._CHANNEL_RULES:
                if matcher(id_code, ""):
                    return label

        return "OTHER"

    # ── Balance Reconstruction ───────────────────────────────────────
    def _reconstruct_balances(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Re-calculate running balance on the given DataFrame.

        Fix #1/#3: Derives opening from the FIRST ROW of the given df,
        not from main_df. This ensures summary rows can't poison opening.
        Fix #8: Uses original file index as fallback tiebreaker.
        """
        if df.empty:
            return df

        # Stable sort: date → tran id → original file order (Fix #8)
        sort_cols = ["Tran Date Raw"]
        if "Tran Id" in df.columns:
            sort_cols.append("Tran Id")
        sort_cols.append("_file_order")
        df = df.sort_values(by=sort_cols).reset_index(drop=True)

        # Opening = balance BEFORE the first transaction
        first = df.iloc[0]
        opening = first['Balance'] - first['Credit'] + first['Debit']

        # Accumulate at full precision, round only for storage (Fix #7 defensive)
        running = float(opening)
        balances = []
        for _, row in df.iterrows():
            running = running + row['Credit'] - row['Debit']
            balances.append(round(running, 2))
        df['Recalc Balance'] = balances

        return df

    # ── Main Pipeline Step ───────────────────────────────────────────
    def generate_main_and_working(self) -> dict:
        """Parse dates, sort, classify channels, filter summaries, rebuild balances."""
        df = self.raw_df.copy()

        # Preserve original file order for stable tiebreaking (Fix #8)
        df['_file_order'] = range(len(df))

        # Date parsing (format='mixed' is valid in pandas ≥ 2.0)
        df['Tran Date Raw'] = pd.to_datetime(df['Tran Date'], format='mixed', errors='coerce')

        # Fix #2: Warn about unparseable dates
        nat_count = df['Tran Date Raw'].isna().sum()
        if nat_count > 0:
            print(f"⚠ WARNING: {nat_count} dates could not be parsed (NaT)")

        sort_cols = ["Tran Date Raw"]
        if "Tran Id" in df.columns:
            sort_cols.append("Tran Id")
        sort_cols.append("_file_order")
        df = df.sort_values(by=sort_cols).reset_index(drop=True)

        df['Year'] = df['Tran Date Raw'].dt.year
        df['Tran Date'] = df['Tran Date Raw'].dt.strftime('%Y-%m-%d')

        # Fix #ReversalFiltering: Exclude transactions with "REV" or "Reversal"
        reversal_mask = (
            df['Desc1'].astype(str).str.contains(r'REV|Reversal', case=False, na=False) |
            df['Remarks'].astype(str).str.contains(r'REV|Reversal', case=False, na=False)
        )
        df = df[~reversal_mask].copy()

        # Classify channels on ALL rows (Annex I uses main_df)
        df['Channel'] = df.apply(self.classify_channel, axis=1)

        # Split into main (all rows) and working (no summary rows)
        self.working_df = df[~df['Desc1'].astype(str).str.contains('~Date summary', na=False)].copy()

        # Fix #1/#3/#9: Reconstruct balances on working_df using its OWN first row
        self.working_df = self._reconstruct_balances(self.working_df)

        # Fix #9: Reconstruct balances on main_df too for consistency
        self.main_df = self._reconstruct_balances(df.copy())

        return {"main_rows": len(self.main_df), "working_rows": len(self.working_df)}

    # ── Pivot Aggregation ────────────────────────────────────────────
    def generate_pivots(self) -> dict:
        """Create Year, Channel, and Mobile pivots from working data."""
        if self.working_df.empty:
            raise RuntimeError("Call generate_main_and_working() first.")

        def _pivot(group_col):
            if group_col not in self.working_df.columns:
                return pd.DataFrame()
            p = self.working_df.groupby(group_col).agg(
                No_of_Debit=('Debit', lambda x: x.astype(float).abs().gt(0).sum()),
                Sum_of_Debit=('Debit', 'sum'),
                No_of_Credit=('Credit', lambda x: x.astype(float).abs().gt(0).sum()),
                Sum_of_Credit=('Credit', 'sum'),
            ).reset_index()
            # Fix #4: Keep zeros, do NOT replace with NaN
            return p

        self.pivot_year = _pivot('Year')
        self.pivot_channel = _pivot('Channel')
        self.pivot_mobile = _pivot('Tnx Mo No')

        return {
            "pivot_year_rows": len(self.pivot_year),
            "pivot_channel_rows": len(self.pivot_channel),
            "pivot_mobile_rows": len(self.pivot_mobile),
        }
