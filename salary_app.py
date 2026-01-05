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
    """Process the raw DataFrame and return the cleaned data and summary tables."""
    # Drop total or grand total rows
    is_total = (
        df["Fiscal Year & Fiscal Period (Combined)"].str.contains("Total", na=False)
        | df["Funds Center Name"].str.contains("Total", na=False)
        | df["Funds Center"].str.contains("Total", na=False)
        | df["Employment Status & Description (Combined)"].str.contains(
            "Total", na=False
        )
    )
    df = df[~is_total].copy()
    # Create Full Name and drop original name columns
    df["Full Name"] = df["First Name"].fillna("") + " " + df["Last Name"].fillna("")
    df.drop(columns=["First Name", "Last Name"], inplace=True)
    # Determine Payment Type based on GL account
    def payment_type(gl_account: str) -> str:
        account = str(gl_account).lstrip("0") if gl_account is not None else ""
        if account.startswith("51"):
            return "Salary"
        elif account.startswith("52"):
            return "Benefit"
        else:
            return "Other"
    df["Payment Type"] = df["Gl Account"].apply(payment_type)
    # Reorder columns: Full Name at position 6 (0-index) and Payment Type before Amount
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
    df = df[desired_columns]
    # Convert Amount for numeric summary
    df["Amount_numeric"] = (
        df["Amount"].str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )
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

    # Format the aggregated amounts as US currency strings (e.g., "$1,234.56").
    # This ensures the tables and downloadable summary clearly show monetary values.
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
