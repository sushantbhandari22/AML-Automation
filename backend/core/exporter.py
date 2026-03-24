"""
core/exporter.py — Excel Report Generation (Annexes, TreeMap, Audit sheets).

Responsible for writing all data to a single multi-sheet Excel workbook.
Does not handle any styling — that is delegated to core.styler.
"""
import os
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from openpyxl.styles import Font, Border, Side
from openpyxl.utils import get_column_letter

from core.styler import ExcelStyler


class ReportExporter:
    """Generates the Final AML Report workbook."""

    def __init__(self, output_dir: str, meta: dict):
        self.output_dir = output_dir
        self.meta = meta
        os.makedirs(output_dir, exist_ok=True)

    # ── Annex Header Block ───────────────────────────────────────────
    def _write_header(self, writer, sheet_name: str, title: str, start_date=None, end_date=None) -> int:
        """Write 2-column metadata header; return the data start row."""
        rows = [
            [title, ""],
            ["Bank Name", self.meta.get('Bank Name', '')],
            ["Branch Name", self.meta.get('Branch Name', '')],
            ["Account Name", self.meta.get('Account Name', '')],
            ["Account Number", self.meta.get('Account Number', '')],
            ["Account Type", self.meta.get('Account Type', '')],
            ["Nature of Account", self.meta.get('Nature of Account', '')],
            ["Currency", self.meta.get('Currency', '')],
            ["Start Date", start_date if start_date else self.meta.get('Start Date', '')],
            ["End Date", end_date if end_date else self.meta.get('End Date', '')],
            ["", ""],
        ]
        pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False, header=False)
        return len(rows) + 1

    # ── Time-Window Filter ───────────────────────────────────────────
    def _filter_date_range(self, df, start_dt, end_dt):
        """Return all rows inclusively within [start_dt, end_dt].

        end_dt is extended to 23:59:59 so ALL transactions on the end
        date are included (guards against partial-day cutoffs).
        """
        # Normalize to date (floor start to 00:00:00, ceil end to 23:59:59)
        start_dt = pd.Timestamp(start_dt).normalize()  # midnight at start
        end_dt = pd.Timestamp(end_dt).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        return df[(df['Tran Date Raw'] >= start_dt) & (df['Tran Date Raw'] <= end_dt)].copy()

    # ── Main Export ──────────────────────────────────────────────────
    def generate(self, main_df, working_df, pivot_year, pivot_channel, pivot_mobile,
                 annex_list=None) -> str:
        """Write all Annexes, TreeMap, and Audit sheets into one workbook."""

        if annex_list is None:
            annex_list = ["I", "II", "III", "IV", "TREEMAP"]

        path = os.path.join(self.output_dir, 'Final_AML_Report.xlsx')

        # ── Date Resolution ──────────────────────────────────────────────
        user_start = str(self.meta.get('Start Date', '')).strip()
        user_end = str(self.meta.get('End Date', '')).strip()

        # Resolve Global End Date (Priority: User > Data Max)
        try:
            a_end = pd.to_datetime(user_end)
            if pd.isna(a_end):
                a_end = pd.to_datetime(main_df['Tran Date Raw']).max()
        except:
            a_end = pd.to_datetime(main_df['Tran Date Raw']).max()

        # Resolve Global Start Date (Priority: User > Data Min)
        try:
            a_start = pd.to_datetime(user_start)
            if pd.isna(a_start):
                a_start = pd.to_datetime(main_df['Tran Date Raw']).min()
        except:
            a_start = pd.to_datetime(main_df['Tran Date Raw']).min()

        # Update meta with the resolved range for the summary cover
        self.meta['Start Date'] = a_start.strftime('%Y-%m-%d')
        self.meta['End Date'] = a_end.strftime('%Y-%m-%d')

        # Calculate Compliance Windows (Relative to a_end)
        # Annex I: Last 2 Years
        a1_start_auto = a_end - pd.DateOffset(years=2)
        # Annex III/IV: Last 1 Year
        a34_start_auto = a_end - pd.DateOffset(years=1)

        # If user explicitly provided a start date, we use it as a strict lower bound for everything
        # Otherwise, we use the best-available data min.
        # However, for the specific annexes, we apply the 1y/2y logic relative to the End Date.
        # If the user wants "One Click", they leave dates blank or use the pre-filled data range.
        
        # We define specific windows for the annexes:
        a1_final_start = max(a_start, a1_start_auto)
        a34_final_start = max(a_start, a34_start_auto)

        # Date strings for headers
        start_str = a_start.strftime('%Y-%m-%d')
        end_str = a_end.strftime('%Y-%m-%d')
        a1_start_str = a1_final_start.strftime('%Y-%m-%d')
        a34_start_str = a34_final_start.strftime('%Y-%m-%d')

        # ── Pre-compute Summary Stats (outside writer, reused inside) ────────
        # Use the SAME filtered window as Annex I so Total Debit/Credit
        # and Closing Balance match what the accountant sees in Annex I.
        filtered_wdf = self._filter_date_range(working_df, a1_final_start, a_end)
        if filtered_wdf.empty:
            filtered_wdf = working_df  # safe fallback to full dataset
        sort_for_close = (['Tran Date Raw', '_file_order']
                          if '_file_order' in filtered_wdf.columns
                          else ['Tran Date Raw'])
        total_debit  = round(float(filtered_wdf['Debit'].sum()), 2)
        total_credit = round(float(filtered_wdf['Credit'].sum()), 2)

        closing_balance = round(total_credit - total_debit, 2)

        # ── ANNEX REPORT ─────────────────────────────────────────────
        annex_name = f"Annex_Report_{os.path.basename(self.output_dir)}.xlsx"
        annex_path = os.path.join(self.output_dir, annex_name)

        with pd.ExcelWriter(annex_path, engine='openpyxl') as writer:
            # ── 0. Report Summary ────────────────────────────────────
            summary = [
                ["AML Account Review Report", ""],
                ["", ""],
                ["Account Name",   self.meta.get('Account Name', '')],
                ["Account Number", self.meta.get('Account Number', '')],
                ["Date Range",     f"{a1_start_str} to {end_str}"],
                ["Total Debit",    total_debit],
                ["Total Credit",   total_credit],
                ["Closing Balance", closing_balance],
            ]
            pd.DataFrame(summary).to_excel(writer, sheet_name="REPORT_SUMMARY", index=False, header=False)

            # ── 1. Annex I — Account Statement ───────────────────────
            if "I" in annex_list:
                a1 = main_df[['Tran Date', 'Desc1', 'Debit', 'Credit', 'Balance', 'Recalc Balance', 'Tran Id', 'Channel', 'Tran Date Raw']].copy()
                a1 = self._filter_date_range(a1, a1_final_start, a_end).drop(columns=['Tran Date Raw'])
                a1.insert(0, "S.N", range(1, len(a1) + 1))
                a1.rename(columns={
                    'Tran Date': 'Transaction Date', 'Desc1': 'Description',
                    'Debit': 'Debit Amount (NPR)', 'Credit': 'Credit Amount (NPR)',
                    'Balance': 'Reported Balance (NPR)', 'Recalc Balance': 'Recalculated Balance (NPR)',
                    'Tran Id': 'Transaction ID', 'Channel': 'Transaction Channel',
                }, inplace=True)
                sr = self._write_header(writer, "Annex-I", "Annex-I Account Statement",
                                        start_date=a1_start_str, end_date=end_str)
                a1.to_excel(writer, sheet_name="Annex-I", startrow=sr, index=False)

            # ── 2. Annex II — Annual Summary (all time) ──────────────
            if "II" in annex_list:
                a2 = pivot_year.copy().sort_values("Year").reset_index(drop=True)
                a2.insert(0, 'Account No', self.meta.get('Account Number', ''))
                a2.rename(columns={
                    'No_of_Debit': 'No. of Debit Transactions',
                    'Sum_of_Debit': 'Total Debit Amount (NPR)',
                    'No_of_Credit': 'No. of Credit Transactions',
                    'Sum_of_Credit': 'Total Credit Amount (NPR)',
                }, inplace=True)

                # User wants per-year balance as (Total Credit - Total Debit) for that year
                a2['Closing Balance (NPR)'] = (
                    a2['Total Credit Amount (NPR)'] - a2['Total Debit Amount (NPR)']
                ).round(2)
                sr = self._write_header(writer, "Annex-II", "Annex-II Annual Summary of Account Statement",
                                        start_date=start_str, end_date=end_str)
                a2.to_excel(writer, sheet_name="Annex-II", startrow=sr, index=False)

            # ── 3. Annex III — Top 10 Deposits ───────────────────────
            if "III" in annex_list:
                w1 = self._filter_date_range(working_df, a34_final_start, a_end)
                a3 = w1[w1['Credit'] > 0].nlargest(10, 'Credit')
                # Sort by date after selecting top 10 by amount (Fix #SortByDate)
                sort_cols = ["Tran Date Raw", "_file_order"] if "_file_order" in a3.columns else ["Tran Date Raw"]
                a3 = a3.sort_values(by=sort_cols).reset_index(drop=True)
                a3 = a3[['Tran Date', 'Desc1', 'Credit', 'Tran Id', 'Channel']]
                a3.insert(0, "Rank", range(1, len(a3) + 1))
                a3.rename(columns={
                    'Tran Date': 'Transaction Date', 'Desc1': 'Description',
                    'Credit': 'Credit Amount (NPR)', 'Tran Id': 'Transaction ID',
                    'Channel': 'Transaction Channel',
                }, inplace=True)
                sr = self._write_header(writer, "Annex-III", "Annex-III Top 10 Deposit within the year",
                                        start_date=a34_start_str, end_date=end_str)
                a3.to_excel(writer, sheet_name="Annex-III", startrow=sr, index=False)

            # ── 4. Annex IV — Top 10 Withdrawals ─────────────────────
            if "IV" in annex_list:
                w1 = self._filter_date_range(working_df, a34_final_start, a_end)
                a4 = w1[w1['Debit'] > 0].nlargest(10, 'Debit')
                # Sort by date after selecting top 10 by amount (Fix #SortByDate)
                sort_cols = ["Tran Date Raw", "_file_order"] if "_file_order" in a4.columns else ["Tran Date Raw"]
                a4 = a4.sort_values(by=sort_cols).reset_index(drop=True)
                a4 = a4[['Tran Date', 'Desc1', 'Debit', 'Tran Id', 'Channel']]
                a4.insert(0, "Rank", range(1, len(a4) + 1))
                a4.rename(columns={
                    'Tran Date': 'Transaction Date', 'Desc1': 'Description',
                    'Debit': 'Debit Amount (NPR)', 'Tran Id': 'Transaction ID',
                    'Channel': 'Transaction Channel',
                }, inplace=True)
                sr = self._write_header(writer, "Annex-IV", "Annex-IV Top 10 Withdrawal within the year",
                                        start_date=a34_start_str, end_date=end_str)
                a4.to_excel(writer, sheet_name="Annex-IV", startrow=sr, index=False)

            # ── 5. TreeMap ───────────────────────────────────────────
            if "TREEMAP" in annex_list:
                tree = [
                    ["", "", "Transaction Tree or Map", ""],
                    ["", "", self.meta.get('Account Number', ''), ""],
                    ["", "", f"{a1_start_str} to {end_str}", ""],
                    ["", "", "", ""],
                    ["Debit Transaction", "", "", "Credit Transaction"],
                    ["", "", "", ""],
                ]
                t_dr, t_cr = 0.0, 0.0
                for _, r in pivot_channel.iterrows():
                    dr = float(r.get('Sum_of_Debit', 0) or 0)
                    cr = float(r.get('Sum_of_Credit', 0) or 0)
                    t_dr += dr
                    t_cr += cr
                    tree.append([r['Channel'], "", "", r['Channel']])
                    tree.append([dr if dr > 0 else "", "", "", cr if cr > 0 else ""])
                    tree.append(["", "", "", ""])
                tree.append(["TOTAL", "", "", "TOTAL"])
                tree.append([round(t_dr, 2), "", "", round(t_cr, 2)])
                pd.DataFrame(tree).to_excel(writer, sheet_name="TreeMap", index=False, header=False)


        # ── BANK REPORT ──────────────────────────────────────────────
        bank_name = f"Bank_Report_{os.path.basename(self.output_dir)}.xlsx"
        bank_path = os.path.join(self.output_dir, bank_name)

        with pd.ExcelWriter(bank_path, engine='openpyxl') as writer:
            main_df.to_excel(writer, sheet_name="MAIN_DATASET", index=False)
            working_df.to_excel(writer, sheet_name="WORKING_DATASET", index=False)
            pivot_year.to_excel(writer, sheet_name="PIVOT_YEAR", index=False)
            pivot_channel.to_excel(writer, sheet_name="PIVOT_CHANNEL", index=False)
            pivot_mobile.to_excel(writer, sheet_name="PIVOT_MOBILE", index=False)

        # ── Apply Styling ────────────────────────────────────────────
        ExcelStyler.style_workbook(annex_path)
        ExcelStyler.style_workbook(bank_path)

        return [annex_name, bank_name]

