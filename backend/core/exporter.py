"""
core/exporter.py — Excel Report Generation (Annexes, TreeMap, Audit sheets).

Responsible for writing all data to a single multi-sheet Excel workbook.
Does not handle any styling — that is delegated to core.styler.
"""
import os
import pandas as pd
import numpy as np
import xlsxwriter
from openpyxl import load_workbook
from openpyxl.styles import Font as OXFont, Border as OXBorder, Side as OXSide
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

        # ── ANNEX REPORT (XlsxWriter) ────────────────────────────────
        annex_name = f"Annex_Report_{os.path.basename(self.output_dir)}.xlsx"
        annex_path = os.path.join(self.output_dir, annex_name)

        with pd.ExcelWriter(annex_path, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
            workbook = writer.book
            
            # Common Formats (Legacy Style Replication)
            fmt_title = workbook.add_format({'font_name': 'Calibri', 'font_size': 16, 'bold': True, 'font_color': '#1F4E78', 'align': 'center'})
            fmt_header_lbl = workbook.add_format({'bold': True, 'font_name': 'Calibri'})
            fmt_table_hdr = workbook.add_format({
                'bold': True, 'bg_color': '#1F4E78', 'font_color': '#FFFFFF',
                'border': 1, 'border_color': '#CCCCCC', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                'font_name': 'Calibri'
            })
            fmt_border = workbook.add_format({'border': 1, 'border_color': '#CCCCCC', 'font_name': 'Calibri'})
            fmt_alt = workbook.add_format({'border': 1, 'border_color': '#CCCCCC', 'bg_color': '#F2F2F2', 'font_name': 'Calibri'})
            fmt_money = workbook.add_format({'border': 1, 'border_color': '#CCCCCC', 'num_format': '#,##0.00;[Red]-#,##0.00', 'align': 'right', 'font_name': 'Calibri'})
            fmt_money_alt = workbook.add_format({'border': 1, 'border_color': '#CCCCCC', 'bg_color': '#F2F2F2', 'num_format': '#,##0.00;[Red]-#,##0.00', 'align': 'right', 'font_name': 'Calibri'})

            def _write_header_xlsx(ws, title, s_dt=None, e_dt=None):
                # Title Row
                ws.merge_range(0, 0, 0, 8, title, fmt_title)
                # Metadata (Legacy style: Bold labels on left)
                header_data = [
                    ("Bank Name", self.meta.get('Bank Name', '')),
                    ("Branch Name", self.meta.get('Branch Name', '')),
                    ("Account Name", self.meta.get('Account Name', '')),
                    ("Account Number", self.meta.get('Account Number', '')),
                    ("Account Type", self.meta.get('Account Type', '')),
                    ("Nature of Account", self.meta.get('Nature of Account', '')),
                    ("Currency", "NPR"),
                    ("Start Date", s_dt if s_dt else self.meta.get('Start Date', '')),
                    ("End Date", e_dt if e_dt else self.meta.get('End Date', '')),
                ]
                for i, (lbl, val) in enumerate(header_data, 1):
                    ws.write(i, 0, lbl, fmt_header_lbl)
                    ws.write(i, 1, val)
                
                # Fixed row 12 for table headers (11-indexed)
                ws.set_row(11, 28) 
                return 11

            # 0. Report Summary
            ws_sum = workbook.add_worksheet("REPORT_SUMMARY")
            ws_sum.set_column(0, 1, 30)
            ws_sum.write(0, 0, "AML Account Review Report", fmt_title)
            summary_info = [
                ("Account Name", self.meta.get('Account Name', '')),
                ("Account Number", self.meta.get('Account Number', '')),
                ("Date Range", f"{a1_start_str} to {end_str}"),
                ("Total Debit", total_debit if not np.isnan(total_debit) else 0.0),
                ("Total Credit", total_credit if not np.isnan(total_credit) else 0.0),
                ("Closing Balance", closing_balance if not np.isnan(closing_balance) else 0.0),
            ]
            for i, (l, v) in enumerate(summary_info, 2):
                ws_sum.write(i, 0, l, fmt_header_lbl)
                ws_sum.write(i, 1, v)

            # 1. Annex I
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
                
                ws_a1 = workbook.add_worksheet("Annex-I")
                sr = _write_header_xlsx(ws_a1, "Annex-I Account Statement", a1_start_str, end_str)
                
                # Write Table Headers
                for c_idx, col in enumerate(a1.columns):
                    ws_a1.write(sr, c_idx, col, fmt_table_hdr)
                
                # Write Data
                for r_idx, row in enumerate(a1.values, sr + 1):
                    is_alt = (r_idx - sr) % 2 == 0
                    for c_idx, val in enumerate(row):
                        col_name = a1.columns[c_idx].lower()
                        is_num = any(k in col_name for k in ("debit", "credit", "balance", "amount"))
                        curr_fmt = (fmt_money_alt if is_alt else fmt_money) if is_num else (fmt_alt if is_alt else fmt_border)
                        ws_a1.write(r_idx, c_idx, val, curr_fmt)
                ws_a1.set_column(0, 10, 15)
                ws_a1.set_column(2, 2, 40) # Description column wider
                ws_a1.freeze_panes(sr + 1, 0)

            # 2. Annex II
            if "II" in annex_list:
                a2 = pivot_year.copy().sort_values("Year").reset_index(drop=True)
                a2.insert(0, 'Account No', self.meta.get('Account Number', ''))
                a2.rename(columns={
                    'No_of_Debit': 'No. of Debit Transactions', 'Sum_of_Debit': 'Total Debit Amount (NPR)',
                    'No_of_Credit': 'No. of Credit Transactions', 'Sum_of_Credit': 'Total Credit Amount (NPR)',
                }, inplace=True)
                # Clean NaNs before subtraction
                a2['Total Credit Amount (NPR)'] = a2['Total Credit Amount (NPR)'].fillna(0.0)
                a2['Total Debit Amount (NPR)'] = a2['Total Debit Amount (NPR)'].fillna(0.0)
                a2['Closing Balance (NPR)'] = (a2['Total Credit Amount (NPR)'] - a2['Total Debit Amount (NPR)']).round(2)
                
                ws_a2 = workbook.add_worksheet("Annex-II")
                sr = _write_header_xlsx(ws_a2, "Annex-II Annual Summary of Account Statement", start_str, end_str)
                for c_idx, col in enumerate(a2.columns):
                    ws_a2.write(sr, c_idx, col, fmt_table_hdr)
                for r_idx, row in enumerate(a2.values, sr + 1):
                    is_alt = (r_idx - sr) % 2 == 0
                    for c_idx, val in enumerate(row):
                        col_name = a2.columns[c_idx].lower()
                        is_num = any(k in col_name for k in ("debit", "credit", "sum", "total", "balance"))
                        curr_fmt = (fmt_money_alt if is_alt else fmt_money) if is_num else (fmt_alt if is_alt else fmt_border)
                        ws_a2.write(r_idx, c_idx, val, curr_fmt)
                # Totals (Legacy style)
                last_r = sr + len(a2) + 1
                ws_a2.write(last_r, 1, "TOTAL", fmt_header_lbl)
                for ci in (2, 3, 4, 5, 6):
                    cl = chr(ord('A') + ci)
                    ws_a2.write_formula(last_r, ci, f"=SUM({cl}{sr+2}:{cl}{last_r})", fmt_money)
                ws_a2.set_column(0, 6, 20)
                ws_a2.freeze_panes(sr + 1, 0)

            # 3. Annex III
            if "III" in annex_list:
                w1 = self._filter_date_range(working_df, a34_final_start, a_end)
                a3 = w1[w1['Credit'] > 0].nlargest(10, 'Credit')
                sort_cols = ["Tran Date Raw", "_file_order"] if "_file_order" in a3.columns else ["Tran Date Raw"]
                a3 = a3.sort_values(by=sort_cols).reset_index(drop=True)
                a3 = a3[['Tran Date', 'Desc1', 'Credit', 'Tran Id', 'Channel']]
                a3.insert(0, "Rank", range(1, len(a3) + 1))
                a3.rename(columns={'Tran Date': 'Transaction Date', 'Desc1': 'Description', 'Credit': 'Credit Amount (NPR)'}, inplace=True)
                
                ws_a3 = workbook.add_worksheet("Annex-III")
                sr = _write_header_xlsx(ws_a3, "Annex-III Top 10 Deposit within the year", a34_start_str, end_str)
                for c_idx, col in enumerate(a3.columns):
                    ws_a3.write(sr, c_idx, col, fmt_table_hdr)
                for r_idx, row in enumerate(a3.values, sr + 1):
                    is_alt = (r_idx - sr) % 2 == 0
                    for c_idx, val in enumerate(row):
                        is_num = "credit" in a3.columns[c_idx].lower()
                        curr_fmt = (fmt_money_alt if is_alt else fmt_money) if is_num else (fmt_alt if is_alt else fmt_border)
                        ws_a3.write(r_idx, c_idx, val, curr_fmt)
                ws_a3.set_column(0, 5, 20)
                ws_a3.set_column(2, 2, 40)
                ws_a3.freeze_panes(sr + 1, 0)

            # 4. Annex IV
            if "IV" in annex_list:
                w1 = self._filter_date_range(working_df, a34_final_start, a_end)
                a4 = w1[w1['Debit'] > 0].nlargest(10, 'Debit')
                sort_cols = ["Tran Date Raw", "_file_order"] if "_file_order" in a4.columns else ["Tran Date Raw"]
                a4 = a4.sort_values(by=sort_cols).reset_index(drop=True)
                a4 = a4[['Tran Date', 'Desc1', 'Debit', 'Tran Id', 'Channel']]
                a4.insert(0, "Rank", range(1, len(a4) + 1))
                a4.rename(columns={'Tran Date': 'Transaction Date', 'Desc1': 'Description', 'Debit': 'Debit Amount (NPR)'}, inplace=True)
                
                ws_a4 = workbook.add_worksheet("Annex-IV")
                sr = _write_header_xlsx(ws_a4, "Annex-IV Top 10 Withdrawal within the year", a34_start_str, end_str)
                for c_idx, col in enumerate(a4.columns):
                    ws_a4.write(sr, c_idx, col, fmt_table_hdr)
                for r_idx, row in enumerate(a4.values, sr + 1):
                    is_alt = (r_idx - sr) % 2 == 0
                    for c_idx, val in enumerate(row):
                        is_num = "debit" in a4.columns[c_idx].lower()
                        curr_fmt = (fmt_money_alt if is_alt else fmt_money) if is_num else (fmt_alt if is_alt else fmt_border)
                        ws_a4.write(r_idx, c_idx, val, curr_fmt)
                ws_a4.set_column(0, 5, 20)
                ws_a4.set_column(2, 2, 40)
                ws_a4.freeze_panes(sr + 1, 0)

            # 5. Visual TreeMap ─ Cell-Based Layout (Editable, Uniform, Standard)
            if "TREEMAP" in annex_list:
                ws_tree = workbook.add_worksheet("TreeMap")

                # ── Palette (Dark Blue + Blue ONLY) ─────────────────────
                C_HDR_BG   = '#1F4E78'   # Dark navy  — header/title
                C_HDR_FG   = '#FFFFFF'   # White text on dark bg
                C_BOX_BG   = '#DEEAF1'   # Very light blue — data boxes
                C_BOX_BOR  = '#2F75B6'   # Mid blue border
                C_TRUNK    = '#2F75B6'   # Mid blue trunk bar
                C_ARROW    = '#1F4E78'   # Dark navy arrows
                C_TOTAL_BG = '#BDD7EE'   # Slightly deeper blue — totals

                # ── Column Layout ────────────────────────────────
                # Col idx: 0=A(debit box), 1=B(gap), 2=C(arrow),
                #          3=D(trunk),     4=E(arrow), 5=F(gap), 6=G(credit box)
                ws_tree.set_column(0, 0, 28)   # A — Debit boxes
                ws_tree.set_column(1, 1, 4)    # B — narrow gap
                ws_tree.set_column(2, 2, 12)   # C — left arrow
                ws_tree.set_column(3, 3, 4)    # D — trunk
                ws_tree.set_column(4, 4, 12)   # E — right arrow
                ws_tree.set_column(5, 5, 4)    # F — narrow gap
                ws_tree.set_column(6, 6, 28)   # G — Credit boxes

                acc_no_val    = self.meta.get('Account Number', '')
                date_range_val = f"{a1_start_str} to {end_str}"

                # ── Formats ───────────────────────────────────────
                def _fmt(**kw):
                    return workbook.add_format({'font_name': 'Calibri', **kw})

                fmt_title = _fmt(
                    font_size=14, bold=True, font_color=C_HDR_FG,
                    bg_color=C_HDR_BG, align='center', valign='vcenter',
                    text_wrap=True, border=0
                )
                fmt_acct = _fmt(
                    font_size=10, bold=False, font_color=C_HDR_FG,
                    bg_color=C_HDR_BG, align='center', valign='vcenter', border=0
                )
                fmt_trunk = _fmt(bg_color=C_TRUNK, border=0)
                fmt_arrow = _fmt(
                    font_size=14, bold=True, font_color=C_ARROW,
                    align='center', valign='vcenter', border=0
                )
                fmt_box_lbl = _fmt(
                    font_size=10, bold=True, font_color=C_HDR_BG,
                    bg_color=C_BOX_BG, align='center', valign='vcenter',
                    text_wrap=True,
                    left=2, right=2, top=2, bottom=2,
                    left_color=C_BOX_BOR, right_color=C_BOX_BOR,
                    top_color=C_BOX_BOR, bottom_color=C_BOX_BOR
                )
                fmt_box_amt = _fmt(
                    font_size=10, bold=True, font_color=C_TRUNK,
                    bg_color=C_BOX_BG, align='center', valign='vcenter',
                    num_format='#,##0.00',
                    left=2, right=2, top=0, bottom=2,
                    left_color=C_BOX_BOR, right_color=C_BOX_BOR,
                    bottom_color=C_BOX_BOR
                )
                fmt_total_lbl = _fmt(
                    font_size=10, bold=True, font_color=C_HDR_BG,
                    bg_color=C_TOTAL_BG, align='center', valign='vcenter',
                    text_wrap=True,
                    left=2, right=2, top=2, bottom=2,
                    left_color=C_HDR_BG, right_color=C_HDR_BG,
                    top_color=C_HDR_BG, bottom_color=C_HDR_BG
                )
                fmt_total_amt = _fmt(
                    font_size=10, bold=True, font_color=C_HDR_BG,
                    bg_color=C_TOTAL_BG, align='center', valign='vcenter',
                    num_format='#,##0.00',
                    left=2, right=2, top=0, bottom=2,
                    left_color=C_HDR_BG, right_color=C_HDR_BG,
                    bottom_color=C_HDR_BG
                )
                fmt_blank = _fmt(border=0)

                # ── Data ───────────────────────────────────────────
                dr_data = [
                    (r['Channel'], float(r.get('Sum_of_Debit', 0) or 0))
                    for _, r in pivot_channel.iterrows()
                    if float(r.get('Sum_of_Debit', 0) or 0) > 0
                ]
                cr_data = [
                    (r['Channel'], float(r.get('Sum_of_Credit', 0) or 0))
                    for _, r in pivot_channel.iterrows()
                    if float(r.get('Sum_of_Credit', 0) or 0) > 0
                ]
                max_items = max(len(dr_data), len(cr_data), 1)

                # ── Row Heights ────────────────────────────────────────────
                ROW_HDR      = 0   # title row
                ROW_ACNO     = 1   # account number row
                ROW_DATE     = 2   # date range row
                ROW_SPACER   = 3   # empty spacer
                ROW_TRUNK    = 4   # dark blue horizontal bar
                ROW_ARROW    = 5   # down arrows to Debit / Credit
                ROW_SEC_LBL  = 6   # section labels
                ROW_DATA_START = 7 # first channel data row

                ws_tree.set_row(ROW_HDR,     30)
                ws_tree.set_row(ROW_ACNO,    18)
                ws_tree.set_row(ROW_DATE,    18)
                ws_tree.set_row(ROW_SPACER,   6)
                ws_tree.set_row(ROW_TRUNK,    8)
                ws_tree.set_row(ROW_ARROW,   24)
                ws_tree.set_row(ROW_SEC_LBL, 20)

                # Each channel = label row (20px) + amount row (16px)
                for i in range(max_items + 1):  # +1 for totals row
                    ws_tree.set_row(ROW_DATA_START + i * 2,     20)
                    ws_tree.set_row(ROW_DATA_START + i * 2 + 1, 16)

                # ── HEADER BLOCK ──────────────────────────────────────────
                ws_tree.merge_range(ROW_HDR,  0, ROW_HDR,  6, 'TRANSACTION TREE MAP',        fmt_title)
                ws_tree.merge_range(ROW_ACNO, 0, ROW_ACNO, 6, f'Account No: {acc_no_val}',   fmt_acct)
                ws_tree.merge_range(ROW_DATE, 0, ROW_DATE, 6, f'Period: {date_range_val}',    fmt_acct)

                # ── TRUNK BAR (full width, mid-blue) ─────────────────────
                ws_tree.merge_range(ROW_TRUNK, 0, ROW_TRUNK, 6, '', fmt_trunk)

                # ── DOWN ARROWS — identical ↓ on col A and col G only ────
                ws_tree.write(ROW_ARROW, 0, '\u2193', fmt_arrow)
                for c in range(1, 6):
                    ws_tree.write(ROW_ARROW, c, '', fmt_blank)
                ws_tree.write(ROW_ARROW, 6, '\u2193', fmt_arrow)

                # ── SECTION LABELS ────────────────────────────────────────
                ws_tree.write(ROW_SEC_LBL, 0, 'DEBIT CHANNELS',  fmt_total_lbl)
                for c in range(1, 6):
                    ws_tree.write(ROW_SEC_LBL, c, '', fmt_blank)
                ws_tree.write(ROW_SEC_LBL, 6, 'CREDIT CHANNELS', fmt_total_lbl)

                # ── DATA ROWS (paired: label + amount, one row each) ───
                for i in range(max_items):
                    r_lbl = ROW_DATA_START + i * 2
                    r_amt = r_lbl + 1

                    # ─ Debit side
                    dr_lbl = dr_data[i][0] if i < len(dr_data) else ''
                    dr_amt = dr_data[i][1] if i < len(dr_data) else None
                    ws_tree.write(r_lbl, 0, dr_lbl, fmt_box_lbl)
                    if dr_amt is not None:
                        ws_tree.write(r_amt, 0, dr_amt, fmt_box_amt)
                    else:
                        ws_tree.write(r_amt, 0, '', fmt_blank)

                    # ─ Arrow col C (→ into debit from trunk side, ← from debit view)
                    ws_tree.write(r_lbl, 1, '', fmt_blank)
                    ws_tree.write(r_lbl, 2, '←', fmt_arrow)
                    ws_tree.write(r_lbl, 3, '', fmt_blank)
                    ws_tree.write(r_lbl, 4, '→', fmt_arrow)
                    ws_tree.write(r_lbl, 5, '', fmt_blank)

                    ws_tree.write(r_amt, 1, '', fmt_blank)
                    ws_tree.write(r_amt, 2, '', fmt_blank)
                    ws_tree.write(r_amt, 3, '', fmt_blank)
                    ws_tree.write(r_amt, 4, '', fmt_blank)
                    ws_tree.write(r_amt, 5, '', fmt_blank)

                    # ─ Credit side
                    cr_lbl = cr_data[i][0] if i < len(cr_data) else ''
                    cr_amt = cr_data[i][1] if i < len(cr_data) else None
                    ws_tree.write(r_lbl, 6, cr_lbl, fmt_box_lbl)
                    if cr_amt is not None:
                        ws_tree.write(r_amt, 6, cr_amt, fmt_box_amt)
                    else:
                        ws_tree.write(r_amt, 6, '', fmt_blank)

                # ── TOTALS ROW ────────────────────────────────────
                r_tot_lbl = ROW_DATA_START + max_items * 2
                r_tot_amt = r_tot_lbl + 1
                ws_tree.set_row(r_tot_lbl, 22)
                ws_tree.set_row(r_tot_amt, 16)

                ws_tree.write(r_tot_lbl, 0, 'TOTAL DEBIT',  fmt_total_lbl)
                ws_tree.write(r_tot_amt, 0, sum(d[1] for d in dr_data), fmt_total_amt)

                ws_tree.write(r_tot_lbl, 6, 'TOTAL CREDIT', fmt_total_lbl)
                ws_tree.write(r_tot_amt, 6, sum(c[1] for c in cr_data), fmt_total_amt)

                for c in range(1, 6):
                    ws_tree.write(r_tot_lbl, c, '', fmt_blank)
                    ws_tree.write(r_tot_amt, c, '', fmt_blank)


        # ── BANK REPORT (openpyxl - remains same for raw data) ───────
        bank_name = f"Bank_Report_{os.path.basename(self.output_dir)}.xlsx"
        bank_path = os.path.join(self.output_dir, bank_name)

        with pd.ExcelWriter(bank_path, engine='openpyxl') as writer:
            main_df.to_excel(writer, sheet_name="MAIN_DATASET", index=False)
            working_df.to_excel(writer, sheet_name="WORKING_DATASET", index=False)
            pivot_year.to_excel(writer, sheet_name="PIVOT_YEAR", index=False)
            pivot_channel.to_excel(writer, sheet_name="PIVOT_CHANNEL", index=False)
            pivot_mobile.to_excel(writer, sheet_name="PIVOT_MOBILE", index=False)

        # ── Apply Styling (Only for openpyxl workbooks) ──────────────
        # Note: Annex report is already styled via XlsxWriter engine
        ExcelStyler.style_workbook(bank_path)

        return [annex_name, bank_name]

