# Automated AML Report Generator - User Guide

Welcome to the Automated AML Report Generation system. This tool is designed to help you generate compliant Annex reports (I, II, III, IV) and transaction summaries with minimal effort.

## How to Generate Reports in One Click

Generating your reports is designed to be simple and "Zero-Touch". Follow these steps:

### Step 1: Upload Data
1. Drag and drop your bank transaction file (CSV or Excel) into the upload area.
2. The system will automatically scan the file and detect the **Account Number**, **Bank Name**, and the **Date Range** of the transactions.

### Step 2: Verification
1. Once uploaded, click the **"Run Reconciliation"** button.
2. The system will check the recalculation of balances and ensure there are no missing transactions.
3. Review the green status indicators to confirm the data is healthy.

### Step 3: Configure and Generate
1. The **Account Metadata** and **Report Dates** will already be pre-filled for you based on the data in your file.
2. If the pre-filled information is correct, simply click **"Generate Reports"**.
3. **Note on Dates**: You don't need to manually calculate the last 1 or 2 years. The system does this automatically for you!
   - **Annex I** will automatically include the last 2 years.
   - **Annex III & IV** will automatically include the last 1 year.
   - **Annex II** will include all years in your file.

### Step 4: Download
1. Once generated, you will see two separate Excel files available for download:
   - **Annex_Report**: This is your primary report containing the summary, all Annexes (I-IV), and the TreeMap. It is designed for final submission.
   - **Bank_Report**: This contains the supporting data, including the main dataset, working dataset, and all pivot tables. Use this for internal auditing or verifying the calculations.
2. You can download each file individually by clicking the corresponding **"Download"** button.

---

## 🛠 Features You Should Know

### Split Reporting
To help you stay organized, the system automatically separates your "Presentation Reports" from your "Audit Data":
- **Presentation (Annex Report)**: Clean, styled, and ready for your compliance file.
- **Audit (Bank Report)**: Contains the raw transaction logic and pivot tables used to build the reports.
You don't need to worry about the specific requirements for each Annex. The system uses "Smart Compliance Windows":
- **Annex I (Statement)**: Always shows the last 2 years (if data is available).
- **Annex III & IV (Top 10s)**: Always shows the last 1 year.
This allows you to generate compliant reports with a single click regardless of how much data you upload.

### Automatic Filtering (Reversals)
The system is smart enough to ignore reversals. Transactions containing "REV" or "Reversal" are automatically excluded from the Top 10 lists to ensure your reports reflect actual realized movements.

### Professional Formatting
Every report is generated with:
- Professional header blocks.
- Bolded totals and summaries.
- Clean column naming.
- Automatic cell sizing for readability.

---

## Pro Tips
- **Manual Override**: If you need to generate a report for a specific custom date range (e.g., just for the last 3 months), you can manually change the **Start Date** and **End Date** in the Configure step before clicking Generate.
- **Dynamic Selection**: You can uncheck specific Annexes if you only need one particular report.
- **Instant Lookup**: If you enter a known **Account Number**, the system will automatically fetch the Bank and Branch details for you.
