"""
core/validator.py — Non-blocking integrity checks for the AML pipeline.

All checks emit warnings rather than raising exceptions, ensuring
that reports are always generated even when data has minor issues.
"""


class DataValidator:
    """Run integrity checks between pipeline stages."""

    @staticmethod
    def validate_row_integrity(raw_df, main_df, working_df) -> dict:
        """Verify row counts across pipeline stages."""
        raw = len(raw_df)
        main = len(main_df)
        working = len(working_df)
        removed = raw - working

        if raw != main:
            print(f"⚠ WARNING: Row mismatch! Raw={raw}, Main={main}")

        print(f"✔ Raw Rows: {raw}")
        print(f"✔ Main Rows: {main}")
        print(f"✔ Working Rows: {working}")
        print(f"✔ Removed Summary Rows: {removed}")

        return {"raw": raw, "main": main, "working": working, "removed": removed}

    @staticmethod
    def validate_balance(working_df) -> dict:
        """Verify: Opening + Credits − Debits == Closing."""
        if working_df.empty:
            return {}

        df = working_df.sort_values("Tran Date Raw")
        total_credit = df['Credit'].sum()
        total_debit = df['Debit'].sum()

        opening = df.iloc[0]['Balance'] + df.iloc[0]['Debit'] - df.iloc[0]['Credit']
        closing = df.iloc[-1]['Recalc Balance']
        calculated = opening + total_credit - total_debit

        if round(calculated, 2) != round(closing, 2):
            print(f"⚠ WARNING: Balance mismatch! Expected {closing}, Calculated {calculated}")
        else:
            print("✔ Balance validation passed")

        return {"opening": opening, "closing": closing, "calculated": calculated}

    @staticmethod
    def validate_pivots(working_df, pivot_channel) -> dict:
        """Confirm pivot totals equal working totals."""
        pivot_dr = pivot_channel['Sum_of_Debit'].fillna(0).sum()
        pivot_cr = pivot_channel['Sum_of_Credit'].fillna(0).sum()
        wrk_dr = working_df['Debit'].sum()
        wrk_cr = working_df['Credit'].sum()

        if abs(pivot_dr - wrk_dr) > 0.01:
            print(f"⚠ WARNING: Pivot Debit mismatch! Pivot={pivot_dr}, Working={wrk_dr}")
        elif abs(pivot_cr - wrk_cr) > 0.01:
            print(f"⚠ WARNING: Pivot Credit mismatch! Pivot={pivot_cr}, Working={wrk_cr}")
        else:
            print("✔ Pivot totals match working data")

        return {"pivot_dr": pivot_dr, "wrk_dr": wrk_dr}

    @staticmethod
    def validate_financial_integrity(working_df, pivot_channel) -> None:
        """Assert-based check with non-blocking warning."""
        try:
            assert round(working_df['Debit'].sum(), 2) == round(pivot_channel['Sum_of_Debit'].sum(), 2), \
                "Debit mismatch between Working and Pivot"
            assert round(working_df['Credit'].sum(), 2) == round(pivot_channel['Sum_of_Credit'].sum(), 2), \
                "Credit mismatch between Working and Pivot"
            print("✔ Financial integrity verified")
        except AssertionError as e:
            print(f"⚠ WARNING (Financial): {e}")

    @staticmethod
    def validate_rows(raw_df, main_df, working_df) -> None:
        """Assert-based row count check with non-blocking warning."""
        try:
            assert len(raw_df) == len(main_df), "Row mismatch in MAIN"
            removed = len(raw_df) - len(working_df)
            print("✔ Row integrity verified")
            print(f"  Raw rows: {len(raw_df)}")
            print(f"  Working rows: {len(working_df)}")
            print(f"  Removed summary rows: {removed}")
        except AssertionError as e:
            print(f"⚠ WARNING (Row): {e}")
