"""
core/metadata.py — Extract and lookup account metadata from raw files.

Provides regex-based header scanning and CSV-based account lookup
for zero-touch metadata population.
"""
import os
import re
import pandas as pd


class MetadataExtractor:
    """Extract bank account metadata from raw file headers."""

    PATTERNS = {
        "bank_name": [r"Bank Name[:,\s]+([^,\n\r]+)", r"Bank[:,\s]+([^,\n\r]+)"],
        "branch_name": [r"Branch Name[:,\s]+([^,\n\r]+)", r"Branch[:,\s]+([^,\n\r]+)"],
        "account_name": [r"Account Name[:,\s]+([^,\n\r]+)", r"Customer Name[:,\s]+([^,\n\r]+)", r"Name[:,\s]+([^,\n\r]+)"],
        "account_number": [r"Account Number[:,\s]+([^,\n\r]+)", r"Account No[:,\s]+([^,\n\r]+)", r"A/C No[:,\s]+([^,\n\r]+)"],
        "account_type": [r"Account Type[:,\s]+([^,\n\r]+)", r"A/C Type[:,\s]+([^,\n\r]+)"],
        "nature_of_account": [r"Nature of Account[:,\s]+([^,\n\r]+)", r"Product[:,\s]+([^,\n\r]+)"],
        "currency": [r"Currency[:,\s]+([^,\n\r]+)", r"CCY[:,\s]+([^,\n\r]+)"],
    }

    @staticmethod
    def extract_from_file(file_path: str) -> dict:
        """Scan the first 50 lines of a file for metadata patterns."""
        metadata = {}
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = "".join([f.readline() for _ in range(50)])

            for key, patterns in MetadataExtractor.PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        val = match.group(1).strip().strip('"').strip("'")
                        if val and key not in metadata:
                            metadata[key] = val
                            break

            # Detect date range
            date_matches = re.findall(
                r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})|(\d{1,2}[-/]\d{1,2}[-/]\d{4})", content
            )
            if date_matches:
                dates = [d[0] or d[1] for d in date_matches]
                if len(dates) >= 2:
                    metadata['start_date'] = dates[0]
                    metadata['end_date'] = dates[-1]

            # Zero-Touch Enhancement: Lookup from CSV
            account_number = metadata.get("account_number")
            if account_number:
                lookup_path = os.path.join(os.path.dirname(os.path.abspath(file_path)), "account_lookup.csv")
                if os.path.exists(lookup_path):
                    try:
                        lookup_df = pd.read_csv(lookup_path, dtype=str)
                        lookup_df.columns = [c.strip().lower().replace(' ', '_') for c in lookup_df.columns]
                        target = str(account_number).strip()
                        match_row = lookup_df[lookup_df['account_number'].str.strip() == target]
                        if not match_row.empty:
                            for k, v in match_row.iloc[0].to_dict().items():
                                if pd.notna(v) and str(v).strip():
                                    metadata[k] = str(v).strip()
                    except Exception as e:
                        print(f"Lookup Error: {e}")
        except Exception:
            pass
        return metadata

    @staticmethod
    def lookup_account(account_number: str) -> dict:
        """Retrieve full metadata for a specific account number from the lookup CSV."""
        if not account_number:
            return {}

        lookup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "account_lookup.csv")
        if not os.path.exists(lookup_path):
            return {}

        try:
            lookup_df = pd.read_csv(lookup_path, dtype=str)
            lookup_df.columns = [c.strip().lower().replace(' ', '_') for c in lookup_df.columns]
            target = str(account_number).strip()
            match_row = lookup_df[lookup_df['account_number'].str.strip() == target]
            if not match_row.empty:
                mapping = {
                    "bank_name": "Bank Name", "branch_name": "Branch Name",
                    "account_name": "Account Name", "account_number": "Account Number",
                    "account_type": "Account Type", "nature_of_account": "Nature of Account",
                    "currency": "Currency",
                }
                return {mapping.get(k, k): str(v).strip() for k, v in match_row.iloc[0].to_dict().items() if pd.notna(v)}
        except Exception as e:
            print(f"Manual Lookup Error: {e}")

        return {}
