import streamlit as st
import pandas as pd
import csv
import io

# Title of the app
st.title("Labor Distribution Summary App")
st.write(
    "Upload your monthly labor distribution CSV file (UTF-16LE, tab-delimited) "
    "and the app will remove totals, construct a Full Name column, determine "
    "payment types (Salary or Benefit) based on the GL account, and generate "
    "summary tables for each individual’s total salary and total benefits."
)

# File uploader for CSV files
uploaded_file = st.file_uploader(
    "Choose a CSV file", type=["csv"], accept_multiple_files=False
)

def process_dataframe(df: pd.DataFrame):
    """Process the raw DataFrame and return the cleaned data and summary tables.

    The function is resilient to missing columns: if any of the expected columns
    used to detect total rows (e.g., "Fiscal Year & Fiscal Period (Combined)")
    are absent, they are simply ignored when filtering out totals. It also
    reorders columns only if they exist in the provided DataFrame.
    """
    # Identify and remove rows that represent totals or grand totals. Some files
    # may not include all of these columns, so we build a mask only from
    # existing columns. We also handle datasets where summary rows may appear
    # across arbitrary columns by scanning the entire DataFrame for the word
    # "Total". If "Total" appears anywhere in a row, that row is dropped.
    total_mask = pd.Series(False, index=df.index)
    # First, check specific columns when present to catch typical totals rows
    total_check_cols = [
        "Fiscal Year & Fiscal Period (Combined)",
        "Funds Center Name",
        "Funds Center",
        "Employment Status & Description (Combined)",
    ]
    for col in total_check_cols:
        if col in df.columns:
            total_mask |= df[col].astype(str).str.contains("Total", case=False, na=False)
    # Additionally, drop any row where any cell contains "Total" (case-insensitive).
    # This handles files with different formats where totals appear in varied columns.
    try:
        # Convert the DataFrame to string for robust checking
        global_total_mask = df.astype(str).apply(lambda col: col.str.contains("Total", case=False, na=False))
        total_mask |= global_total_mask.any(axis=1)
    except Exception:
        # Fallback: if conversion fails (e.g., due to mixed types), skip global check
        pass
    # Filter out total rows
    df = df[~total_mask].copy()

    # Create Full Name column and drop original name columns if they exist
    first_name_col = "First Name"
    last_name_col = "Last Name"
    if first_name_col in df.columns and last_name_col in df.columns:
        df["Full Name"] = df[first_name_col].fillna("") + " " + df[last_name_col].fillna("")
        df.drop(columns=[first_name_col, last_name_col], inplace=True)
    elif "Full Name" not in df.columns:
        # If we cannot derive a full name, ensure the column exists (empty)
        df["Full Name"] = ""

    # Determine Payment Type based on GL account (prefixes 51=Salary, 52=Benefit)
    def payment_type(gl_account: str) -> str:
        account = str(gl_account).lstrip("0") if gl_account is not None else ""
        if account.startswith("51"):
            return "Salary"
        elif account.startswith("52"):
            return "Benefit"
        else:
            return "Other"

    if "Gl Account" in df.columns:
        df["Payment Type"] = df["Gl Account"].apply(payment_type)
    else:
        # If GL Account column is missing, classify all as Other
        df["Payment Type"] = "Other"

    # Define desired column order. Some columns may not exist in the uploaded file,
    # so we include only those that are present.
    desired_columns = [
        "Funds Center",
        "Funds Center Name",
        "Grant_Number",
        "Fund",
        "Person Id",
        "Pernr",
        "Full Name",
        "Employment Status & Description (Combined)",
        "Position Id",
        "Wage Type",
        "Symbolic Account",
        "Gl Account",
        "Org Unit Department",
        "Fiscal Year & Fiscal Period (Combined)",
        "In Period Date",
        "For Period Date",
        "Hours",
        "Payment Type",
        "Amount",
    ]
    # Only keep columns that exist in df and preserve their order
    columns_in_df = [col for col in desired_columns if col in df.columns]
    # Ensure "Full Name" and "Payment Type" are included even if they were added later
    for col in ["Full Name", "Payment Type"]:
        if col not in columns_in_df and col in df.columns:
            columns_in_df.append(col)
    # Reorder DataFrame by including desired columns first and appending any
    # remaining columns that weren't specified. This preserves extra columns in
    # unfamiliar datasets rather than dropping them.
    remaining_cols = [col for col in df.columns if col not in columns_in_df]
    df = df[columns_in_df + remaining_cols]

    # Convert Amount for numeric summary. If Amount is not present or not string,
    # skip conversion and set numeric amount to zero.
    if "Amount" in df.columns:
        # Remove currency symbols/commas and cast to float; invalid values become NaN
        df["Amount_numeric"] = (
            df["Amount"].astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .astype(float)
        )
    else:
        df["Amount_numeric"] = 0.0

    # Summarize salary and benefits
    salary_summary = (
        df[df["Payment Type"] == "Salary"]
        .groupby("Full Name")["Amount_numeric"]
        .sum()
        .reset_index()
        .rename(columns={"Amount_numeric": "Total Salary"})
    )
    benefit_summary = (
        df[df["Payment Type"] == "Benefit"]
        .groupby("Full Name")["Amount_numeric"]
        .sum()
        .reset_index()
        .rename(columns={"Amount_numeric": "Total Benefits"})
    )

    # Format aggregated amounts as US currency strings (e.g., "$1,234.56")
    salary_summary["Total Salary"] = salary_summary["Total Salary"].apply(
        lambda x: f"${x:,.2f}"
    )
    benefit_summary["Total Benefits"] = benefit_summary["Total Benefits"].apply(
        lambda x: f"${x:,.2f}"
    )

    return df, salary_summary, benefit_summary

# If a file is uploaded, process it
if uploaded_file is not None:
    # Read the uploaded file as a DataFrame
    raw_df = pd.read_csv(uploaded_file, encoding="utf-16le", sep="\t", dtype=str)
    processed_df, salary_table, benefit_table = process_dataframe(raw_df)

    # Display the processed data tables and summaries
    st.subheader("Processed Data (first 10 rows)")
    st.dataframe(processed_df.head(10))

    st.subheader("Total Salary by Individual")
    st.dataframe(salary_table)

    st.subheader("Total Benefits by Individual")
    st.dataframe(benefit_table)

    # Provide a downloadable summary CSV file
    # Create a CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    # Write salary table header and rows
    writer.writerow(["Full Name", "Total Salary"])
    for _, row in salary_table.iterrows():
        writer.writerow([row["Full Name"], row["Total Salary"]])
    # Add a blank row to separate tables
    writer.writerow([])
    # Write benefits table header and rows
    writer.writerow(["Full Name", "Total Benefits"])
    for _, row in benefit_table.iterrows():
        writer.writerow([row["Full Name"], row["Total Benefits"]])
    # Get CSV value and encode to bytes for download
    csv_data = output.getvalue().encode("utf-8")
    st.download_button(
        label="Download Summary CSV",
        data=csv_data,
        file_name="summary.csv",
        mime="text/csv",
    )

    # Optionally: Provide processed dataset for download as well
    processed_output = io.StringIO()
    processed_df.drop(columns=["Amount_numeric"], inplace=False).to_csv(
        processed_output, index=False
    )
    st.download_button(
        label="Download Processed Data",
        data=processed_output.getvalue().encode("utf-8"),
        file_name="processed_data.csv",
        mime="text/csv",
    )
