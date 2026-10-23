from pathlib import Path
import sys
import pandas as pd

REQUIRED = ["Order_ID", "Date", "Product", "Category", "Quantity", "Unit_Price"]

def validate_sales(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif path.suffix.lower() == ".xlsx":
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        raise ValueError("Use a CSV or XLSX file.")

    df.columns = df.columns.str.strip()
    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names found.")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    if df.empty:
        raise ValueError("File contains no sales rows.")

    df = df[REQUIRED].copy()
    for column in REQUIRED:
        df[column] = df[column].str.strip()
    df.insert(0, "Source_Row", range(2, len(df) + 2))
    reasons = pd.Series("", index=df.index)

    def flag(mask, message):
        reasons.loc[mask] += message + "; "

    for column in REQUIRED:
        flag(df[column].eq(""), column + " is missing")
    flag(df.duplicated(subset=REQUIRED), "Duplicate sales row")

    dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    flag(dates.isna(), "Invalid date: use YYYY-MM-DD")

    quantity = pd.to_numeric(df["Quantity"], errors="coerce")
    price = pd.to_numeric(df["Unit_Price"], errors="coerce")
    flag(
        quantity.isna() | quantity.isin([float("inf"), -float("inf")])
        | quantity.le(0) | quantity.mod(1).ne(0),
        "Quantity must be a positive whole number"
    )
    flag(
        price.isna() | price.isin([float("inf"), -float("inf")]) | price.lt(0),
        "Unit_Price must be finite and non-negative"
    )

    invalid = reasons.ne("")
    issues = df.loc[invalid].copy()
    issues["Issues"] = reasons.loc[invalid].str.rstrip("; ")
    clean = df.loc[~invalid].copy()
    clean["Date"] = dates.loc[~invalid]
    clean["Quantity"] = quantity.loc[~invalid]
    clean["Unit_Price"] = price.loc[~invalid]
    clean["Revenue"] = (clean["Quantity"] * clean["Unit_Price"]).round(2)
    return clean, issues

if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "data/sample_sales.csv"
    try:
        clean, issues = validate_sales(source)
        Path("output").mkdir(exist_ok=True)
        clean.to_csv("output/cleaned_sales.csv", index=False)
        issues.to_csv("output/validation_issues.csv", index=False)
        print("VALIDATION COMPLETE")
        print("Valid rows:", len(clean))
        print("Rows needing review:", len(issues))
        print("Total revenue: INR", round(clean["Revenue"].sum(), 2))
    except (ValueError, OSError) as error:
        print("ERROR:", error)
        sys.exit(1)
