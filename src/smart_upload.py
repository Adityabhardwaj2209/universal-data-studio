from io import BytesIO
from pathlib import Path
import hashlib

import pandas as pd
import streamlit as st


ALIASES = {
    "Order_ID": ["orderid", "orderno", "invoiceid", "invoiceno", "invoice"],
    "Date": ["date", "orderdate", "invoicedate", "salesdate"],
    "Product": ["product", "productname", "item", "itemname"],
    "Category": ["category", "department", "productcategory"],
    "Quantity": ["quantity", "qty", "units"],
    "Unit_Price": ["unitprice", "price", "rate", "sellingprice"],
    "Amount": ["amount", "sales", "revenue", "total", "linetotal"],
}


def normalized(value):
    return "".join(c for c in str(value).lower() if c.isalnum())


def suggest(columns, field):
    aliases = ALIASES[field]
    for column in columns:
        if normalized(column) in aliases:
            return column
    return None


@st.cache_data(show_spinner=False, max_entries=8, ttl=600)
def read_source(payload, extension, sheet, separator, encoding):
    if extension == ".xlsx":
        return pd.read_excel(
            BytesIO(payload),
            sheet_name=sheet,
            dtype=str,
            keep_default_na=False,
        )
    return pd.read_csv(
        BytesIO(payload),
        sep=separator,
        encoding=encoding,
        dtype=str,
        keep_default_na=False,
    )


def prepare_upload():
    mode = st.radio(
        "Choose your data",
        ["Upload my file", "Try demo"],
        horizontal=True,
        key="source_mode",
    )

    if mode == "Try demo":
        demo = Path("data/sample_sales.csv")
        if not demo.exists():
            st.error("Demo file is missing.")
            st.stop()
        return demo.read_bytes()

    uploaded = st.file_uploader(
        "Upload sales data",
        type=["csv", "xlsx"],
        help="CSV and Excel files up to 20 MB.",
        key="smart_sales_upload",
    )
    if uploaded is None:
        st.info("Upload a file or choose Try demo.")
        st.stop()

    payload = uploaded.getvalue()
    if len(payload) > 20 * 1024 * 1024:
        st.error("Please upload a file smaller than 20 MB.")
        st.stop()
    if not payload:
        st.error("This file is empty.")
        st.stop()

    extension = Path(uploaded.name).suffix.lower()
    identity = hashlib.sha256(payload).hexdigest()[:12]
    sheet = 0
    separator = ","
    encoding = "utf-8-sig"

    try:
        if extension == ".xlsx":
            with pd.ExcelFile(BytesIO(payload)) as workbook:
                names = workbook.sheet_names
            sheet = st.selectbox(
                "Select Excel sheet", names, key="sheet_" + identity
            )
        else:
            with st.expander("CSV reading options"):
                delimiter = st.selectbox(
                    "Separator",
                    ["Comma", "Semicolon", "Tab"],
                    key="separator_" + identity,
                )
                separator = {
                    "Comma": ",", "Semicolon": ";", "Tab": "\t"
                }[delimiter]
                encoding = st.selectbox(
                    "File encoding",
                    ["utf-8-sig", "cp1252", "latin1"],
                    key="encoding_" + identity,
                )

        with st.spinner("Reading your file..."):
            frame = read_source(
                payload, extension, sheet, separator, encoding
            ).copy()

        frame.columns = [str(c).strip() for c in frame.columns]
        if frame.empty:
            st.warning("This sheet has no data rows.")
            st.stop()
        if frame.columns.duplicated().any():
            st.error("Column names must be unique.")
            st.stop()
        if len(frame) > 100000:
            st.error("This version supports up to 100,000 rows per file.")
            st.stop()

        st.caption(
            f"{len(frame):,} rows and {len(frame.columns)} columns found."
        )
        with st.expander("Preview original data"):
            st.dataframe(frame.head(20), hide_index=True)

        revenue_mode = st.radio(
            "How is revenue provided?",
            ["Quantity x Unit price", "Existing sales amount"],
            horizontal=True,
            key="revenue_mode_" + identity,
        )
        fields = ["Order_ID", "Date", "Product", "Category", "Quantity"]
        fields += (
            ["Unit_Price"]
            if revenue_mode == "Quantity x Unit price"
            else ["Amount"]
        )
        choices = ["-- Select --"] + list(frame.columns)
        mapping = {}

        st.subheader("Match your columns")
        st.caption(
            "Confirm the suggested matches. Dates must use YYYY-MM-DD. "
            "An Order ID may contain multiple product rows."
        )
        with st.form("mapping_" + identity):
            for field in fields:
                guessed = suggest(frame.columns, field)
                mapping[field] = st.selectbox(
                    field.replace("_", " "),
                    choices,
                    index=choices.index(guessed) if guessed else 0,
                    key=identity + "_map_" + field,
                )
            ready = st.form_submit_button("Use these columns")

        mapping_key = (
            "confirmed_mapping_" + identity + "_"
            + str(sheet) + "_" + revenue_mode
            + "_" + separator + "_" + encoding
        )
        if ready:
            selected = list(mapping.values())
            if "-- Select --" in selected:
                st.error("Select a column for every field.")
            elif len(selected) != len(set(selected)):
                st.error("Each field must use a different source column.")
            else:
                st.session_state[mapping_key] = mapping.copy()

        confirmed = st.session_state.get(mapping_key)
        if confirmed is None:
            st.info("Confirm the column mapping to open your dashboard.")
            st.stop()

        result = pd.DataFrame({
            field: frame[column]
            for field, column in confirmed.items()
        })

        if revenue_mode == "Existing sales amount":
            quantity = pd.to_numeric(
                result["Quantity"], errors="coerce"
            )
            amount = pd.to_numeric(result.pop("Amount"), errors="coerce")
            result["Unit_Price"] = amount / quantity.where(quantity.gt(0))
            st.caption(
                "Unit price is derived from sales amount / quantity. "
                "Invalid amounts or quantities will appear in validation."
            )

        return result.to_csv(index=False).encode("utf-8-sig")

    except (ValueError, OSError, UnicodeError, ImportError) as error:
        st.error(f"Unable to read this file: {error}")
        st.stop()
