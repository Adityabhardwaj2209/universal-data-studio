from io import BytesIO
import hashlib
import re

import pandas as pd
import streamlit as st

TYPES = ["Text", "Number", "Date", "Boolean"]
ROLES = ["Identifier", "Category", "Measure", "Date", "Ignore"]
AGGREGATIONS = ["None", "Sum", "Mean", "Median", "Count", "Distinct", "Min", "Max"]
FORMATS = ["1234.56", "1,234.56", "1.234,56", "12.5%"]
BOOLEAN_VALUES = {
    "true": True, "false": False,
    "yes": True, "no": False,
    "1": True, "0": False,
}


def parse_numbers(series, number_format):
    values = series.astype("string").str.strip()
    if number_format == "1,234.56":
        values = values.str.replace(",", "", regex=False)
    elif number_format == "1.234,56":
        values = (
            values.str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
    elif number_format == "12.5%":
        values = values.str.replace("%", "", regex=False)
    parsed = pd.to_numeric(values, errors="coerce")
    parsed = parsed.replace(
        [float("inf"), -float("inf")], float("nan")
    )
    if number_format == "12.5%":
        parsed = parsed / 100
    return parsed


def profile(frame):
    rows = []
    specifications = []

    for column in frame.columns:
        values = frame[column].astype("string").str.strip()
        present = values[values.notna() & values.ne("")]
        missing = len(values) - len(present)
        unique = int(present.nunique())
        name = column.lower()
        identifier = (
            name == "id"
            or name.endswith("_id")
            or name.endswith("_code")
            or name in ("postal_code", "zip", "phone", "mobile")
        )

        kind = "Text"
        role = "Identifier" if identifier else "Category"
        aggregation = "None"
        number_format = "1234.56"
        date_format = "%Y-%m-%d"
        confidence = "Review"

        if len(present) and not identifier:
            lower = present.str.lower()
            percentage = present.str.endswith("%").mean() >= .95
            numeric = parse_numbers(
                present, "12.5%" if percentage else "1234.56"
            )
            iso_dates = present.str.fullmatch(
                r"\d{4}-\d{2}-\d{2}"
            ).fillna(False).mean()

            if lower.isin(BOOLEAN_VALUES).all() and not numeric.notna().all():
                kind = "Boolean"
                confidence = "High"
            elif iso_dates >= .95:
                kind = "Date"
                role = "Date"
                confidence = "Suggested"
            elif numeric.notna().mean() >= .95:
                kind = "Number"
                role = "Measure"
                number_format = "12.5%" if percentage else "1234.56"
                rate = any(
                    word in name
                    for word in ("accuracy", "percent", "rate", "average", "speed")
                )
                aggregation = "Mean" if rate or percentage else "Sum"
                confidence = "Suggested"

        rows.append({
            "Column": column,
            "Rows": len(values),
            "Missing": missing,
            "Missing (%)": round(missing / len(values) * 100, 1),
            "Distinct nonblank": unique,
            "Examples": " | ".join(present.drop_duplicates().head(3).tolist())[:180],
            "Suggested type": kind,
            "Detection": confidence,
        })
        specifications.append({
            "Column": column,
            "Type": kind,
            "Role": role,
            "Date format": date_format,
            "Number format": number_format,
            "Aggregation": aggregation,
        })

    return pd.DataFrame(rows), pd.DataFrame(specifications)


def convert(frame, schema):
    converted = pd.DataFrame(index=frame.index)
    issues = []

    for _, spec in schema.iterrows():
        column = spec["Column"]
        if spec["Role"] == "Ignore":
            continue

        original = frame[column].astype("string").str.strip()
        present = original.notna() & original.ne("")
        kind = spec["Type"]

        if kind == "Number":
            result = parse_numbers(original, spec["Number format"])
        elif kind == "Date":
            result = pd.to_datetime(
                original.where(present),
                format=spec["Date format"],
                errors="coerce",
            )
        elif kind == "Boolean":
            result = original.str.lower().map(BOOLEAN_VALUES).astype("boolean")
        else:
            result = original.where(present)

        bad = present & result.isna()
        for index in frame.index[bad]:
            issues.append({
                "Source row": int(index) + 2,
                "Column": column,
                "Original value": original.loc[index],
                "Issue": "Could not convert to " + kind,
            })
        converted[column] = result

    return converted, pd.DataFrame(
        issues,
        columns=["Source row", "Column", "Original value", "Issue"],
    )


def render_universal_legacy():

    workflow = st.radio(
        "Choose workflow",
        ["Profile a dataset", "Connect two datasets"],
        horizontal=True,
        key="universal_workflow",
    )
    if workflow == "Connect two datasets":
        from .relationships import render_relationships
        render_relationships()
        return


    st.header("Universal Data Studio")
    st.caption(
        "Step 1: inspect your dataset. Step 2: confirm field types and roles."
    )

    upload = st.file_uploader(
        "Upload a rectangular CSV or Excel table",
        type=["csv", "xlsx"],
        key="universal_upload",
    )
    if upload is None:
        st.info("Upload a file to generate its field profile.")
        return

    payload = upload.getvalue()
    if not payload or len(payload) > 20 * 1024 * 1024:
        st.error("Choose a non-empty file smaller than 20 MB.")
        return

    try:
        sheet = ""
        separator = ","
        encoding = "utf-8-sig"

        if upload.name.lower().endswith(".xlsx"):
            with pd.ExcelFile(BytesIO(payload)) as book:
                sheet = st.selectbox("Worksheet", book.sheet_names)
                frame = pd.read_excel(
                    book, sheet_name=sheet, dtype=str,
                    keep_default_na=False,
                )
        else:
            with st.expander("CSV options"):
                separator = st.selectbox(
                    "Separator", [",", ";", "\t"],
                    format_func=lambda x: "Tab" if x == "\t" else x,
                )
                encoding = st.selectbox(
                    "Encoding", ["utf-8-sig", "cp1252", "latin1"]
                )
            frame = pd.read_csv(
                BytesIO(payload),
                sep=separator,
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
            )

        frame.columns = [str(c).strip() for c in frame.columns]
        frame = frame.reset_index(drop=True)

        if frame.empty:
            st.warning("This table has no data rows.")
            return
        if frame.columns.duplicated().any():
            st.error("Column names must be unique after trimming spaces.")
            return
        if len(frame) > 100000 or len(frame.columns) > 300:
            st.warning("This version supports 100,000 rows and 300 columns.")
            return

        identity = hashlib.sha256(
            payload + str((sheet, separator, encoding)).encode()
        ).hexdigest()[:16]

        a, b, c = st.columns(3)
        a.metric("Rows", f"{len(frame):,}")
        b.metric("Fields", len(frame.columns))
        c.metric("Exact duplicate rows", int(frame.duplicated().sum()))

        summary, suggested = profile(frame)
        from .universal_profiles import choose_profile
        suggested = choose_profile(suggested, identity)
        st.subheader("Dataset profile")
        st.dataframe(summary, hide_index=True)

        if "source_stat_category" in frame.columns:
            st.warning(
                "Multiple source categories detected. Repeated entity rows "
                "must be reviewed before aggregating statistics."
            )

        with st.expander("Original data preview"):
            st.dataframe(frame.head(100), hide_index=True)

        st.subheader("Schema editor")
        st.caption(
            "Suggested types need confirmation. Date formats use Python "
            "patterns: %Y-%m-%d or %d/%m/%Y. Percentage format converts "
            "12.5% to 0.125. Aggregations are defaults for later analysis."
        )

        with st.form("schema_form_" + identity):
            edited = st.data_editor(
                suggested,
                hide_index=True,
                num_rows="fixed",
                disabled=["Column"],
                key="schema_editor_" + identity,
                column_config={
                    "Type": st.column_config.SelectboxColumn(
                        options=TYPES, required=True
                    ),
                    "Role": st.column_config.SelectboxColumn(
                        options=ROLES, required=True
                    ),
                    "Number format": st.column_config.SelectboxColumn(
                        options=FORMATS, required=True
                    ),
                    "Aggregation": st.column_config.SelectboxColumn(
                        options=AGGREGATIONS, required=True
                    ),
                },
            )
            submitted = st.form_submit_button("Confirm schema and convert")

        if submitted:
            errors = []
            for _, spec in edited.iterrows():
                if spec["Role"] == "Measure" and spec["Type"] != "Number":
                    errors.append(spec["Column"] + ": Measure requires Number type.")
                if spec["Role"] == "Date" and spec["Type"] != "Date":
                    errors.append(spec["Column"] + ": Date role requires Date type.")
                if spec["Role"] in ("Identifier", "Category", "Ignore") and spec["Aggregation"] not in ("None", "Count", "Distinct"):
                    errors.append(
                        spec["Column"] + ": use None, Count or Distinct for this role."
                    )
                if spec["Type"] == "Date" and not str(spec["Date format"]).strip():
                    errors.append(spec["Column"] + ": enter a date format.")
            if edited["Role"].eq("Ignore").all():
                errors.append("Keep at least one field.")
            if errors:
                for message in errors:
                    st.error(message)
            else:
                with st.spinner("Converting fields..."):
                    converted, issues = convert(frame, edited)
                st.session_state["confirmed_schema_" + identity] = (
                    edited.copy(), converted, issues
                )

        result = st.session_state.get("confirmed_schema_" + identity)
        if result is None:
            return

        schema, converted, issues = result
        from .universal_dashboard import render_dashboard
        render_dashboard(converted, schema, identity)

        st.success("Schema confirmed. Typed dataset is ready.")
        st.caption(
            "Preview and downloads reflect the last confirmed schema. "
            "Submit again after changing the editor."
        )
        st.write("Converted data preview")
        st.dataframe(converted.head(200), hide_index=True)

        if issues.empty:
            st.success("All nonblank values converted successfully.")
        else:
            st.warning(
                f"{len(issues):,} values could not be converted. "
                "They appear as missing values; original data is preserved."
            )
            st.dataframe(issues.head(200), hide_index=True)

        from .report import excel_safe
        a, b = st.columns(2)
        a.download_button(
            "Download confirmed schema",
            schema.to_json(orient="records", indent=2).encode("utf-8"),
            "dataset_schema.json", "application/json",
        )
        b.download_button(
            "Download converted CSV",
            excel_safe(converted).to_csv(index=False).encode("utf-8-sig"),
            "converted_dataset.csv", "text/csv",
        )
        if not issues.empty:
            st.download_button(
                "Download conversion issues",
                excel_safe(issues).to_csv(index=False).encode("utf-8-sig"),
                "conversion_issues.csv", "text/csv",
            )

    except Exception as error:
        st.error(f"Unable to profile this dataset: {error}")


def render_universal():
    from .studio_app import render
    try:
        render()
    except (ValueError, KeyError, TypeError, OSError) as error:
        st.error(str(error))
