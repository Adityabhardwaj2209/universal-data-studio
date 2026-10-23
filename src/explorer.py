from io import BytesIO
import json

import altair as alt
import pandas as pd
import streamlit as st


def render_explorer():
    st.header("Any-data explorer")
    st.caption(
        "Explore sports, sales or other tabular datasets. "
        "Choose fields and calculations explicitly."
    )
    uploads = st.file_uploader(
        "Upload CSV, Excel or JSON files",
        type=["csv", "xlsx", "json"],
        accept_multiple_files=True,
        key="explorer_uploads",
    )
    if not uploads:
        st.info("Upload one or more files to begin.")
        return

    index = st.selectbox(
        "Choose file",
        range(len(uploads)),
        format_func=lambda i: uploads[i].name,
    )
    upload = uploads[index]
    payload = upload.getvalue()
    if len(payload) > 20 * 1024 * 1024:
        st.error("Choose a file smaller than 20 MB.")
        return

    try:
        if upload.name.lower().endswith(".json"):
            content = json.loads(payload.decode("utf-8-sig"))
            st.subheader("JSON contents")
            st.json(content)
            st.caption(
                "Metadata JSON describes a dataset; it is not a sales table."
            )
            return
        elif upload.name.lower().endswith(".xlsx"):
            with pd.ExcelFile(BytesIO(payload)) as book:
                sheet = st.selectbox("Worksheet", book.sheet_names)
                frame = pd.read_excel(
                    book, sheet_name=sheet, dtype=str,
                    keep_default_na=False,
                )
        else:
            a, b = st.columns(2)
            separator = a.selectbox(
                "CSV separator", [",", ";", "\t"],
                format_func=lambda s: "Tab" if s == "\t" else s,
            )
            encoding = b.selectbox(
                "Encoding", ["utf-8-sig", "cp1252", "latin1"]
            )
            frame = pd.read_csv(
                BytesIO(payload), sep=separator, encoding=encoding,
                dtype=str, keep_default_na=False,
            )

        if frame.empty:
            st.warning("This table has no records.")
            return

        if "source_stat_category" in frame.columns:
            st.warning(
                "This file contains multiple statistics rows per entity. "
                "Prefer the matching summary CSV for player/team rankings. "
                "Summing repeated statistics can double-count results."
            )
            sources = st.multiselect(
                "Source categories",
                sorted(frame["source_stat_category"].unique()),
            )
            if sources:
                frame = frame[
                    frame["source_stat_category"].isin(sources)
                ]

        st.caption(
            "Files are explored separately. Related files are not "
            "automatically joined or concatenated."
        )

        numeric = []
        for column in frame.columns:
            name = column.lower()
            if name == "id" or name.endswith("_id") or name.endswith("_code"):
                continue
            present = frame[column].str.strip().ne("")
            if present.any():
                parsed = pd.to_numeric(
                    frame.loc[present, column], errors="coerce"
                )
                if parsed.notna().mean() >= .95:
                    numeric.append(column)

        a, b, c = st.columns(3)
        a.metric("Rows", len(frame))
        b.metric("Columns", len(frame.columns))
        c.metric(
            "Blank cells",
            int(frame.apply(
                lambda col: col.str.strip().eq("")
            ).sum().sum()),
        )

        with st.expander("Filter table"):
            filter_column = st.selectbox(
                "Filter column", ["No filter"] + list(frame.columns)
            )
            if filter_column != "No filter":
                values = st.multiselect(
                    "Keep values",
                    sorted(frame[filter_column].unique()),
                )
                if values:
                    frame = frame[frame[filter_column].isin(values)]

        st.dataframe(frame, hide_index=True)
        if frame.empty:
            st.info("No rows match the filter.")
            return

        st.subheader("Build a graph")
        if not numeric:
            st.info(
                "No numeric measure detected. "
                "You can still chart row counts by a category."
            )

        a, b, c = st.columns(3)
        group = a.selectbox("Group / X field", list(frame.columns))
        measure = b.selectbox("Measure", ["Row count"] + numeric)
        operation = c.selectbox(
            "Calculation",
            ["Mean", "Sum", "Maximum", "Minimum", "Unique values"],
            disabled=measure == "Row count",
        )
        kind = st.selectbox(
            "Graph format", ["Bar", "Line", "Area", "Donut"]
        )

        if measure == "Row count":
            grouped = frame.groupby(
                group, dropna=False
            ).size().reset_index(name="Value")
        else:
            working = frame[[group]].copy()
            working["_measure"] = pd.to_numeric(
                frame[measure], errors="coerce"
            ).replace([float("inf"), -float("inf")], float("nan"))
            missing = int(working["_measure"].isna().sum())
            if missing:
                st.caption(
                    f"{missing} rows have missing/non-finite numeric values; "
                    "these are excluded, not replaced with zero."
                )
            working = working.dropna(subset=["_measure"])
            methods = {
                "Mean": "mean", "Sum": "sum", "Maximum": "max",
                "Minimum": "min", "Unique values": "nunique",
            }
            grouped = (
                working.groupby(group, dropna=False)["_measure"]
                .agg(methods[operation]).reset_index(name="Value")
            )

        if grouped.empty:
            st.info("No numeric values available for this selection.")
            return

        limit = st.selectbox("Maximum displayed groups", [10, 20, 50, 100])
        order = st.radio(
            "Order groups", ["Highest value", "Group name"], horizontal=True
        )
        grouped = grouped.sort_values(
            "Value" if order == "Highest value" else group,
            ascending=order != "Highest value",
        )
        visible = grouped.head(limit)

        st.caption(
            f"Showing {len(visible)} of {len(grouped)} groups. "
            "The complete grouped table is downloadable below."
        )

        chart = alt.Chart(visible)
        if kind == "Donut":
            if (visible["Value"] < 0).any() or visible["Value"].sum() <= 0:
                st.warning("Donut charts require non-negative values and a positive total.")
                chart = None
            else:
                chart = chart.mark_arc(innerRadius=75).encode(
                    theta="Value:Q",
                    color=alt.Color(
                        field=group, type="nominal",
                        scale=alt.Scale(scheme="tableau10"),
                    ),
                    tooltip=[group, "Value"],
                )
                st.caption("Shares refer only to the displayed groups.")
        else:
            if kind == "Bar":
                chart = chart.mark_bar(color="#8756AC")
            elif kind == "Line":
                chart = chart.mark_line(
                    color="#8756AC", strokeWidth=4, point=True
                )
            else:
                chart = chart.mark_area(
                    color="#8756AC", opacity=.6, line=True
                )
            chart = chart.encode(
                x=alt.X(field=group, type="nominal", sort=None),
                y=alt.Y("Value:Q", title=measure),
                tooltip=[group, "Value"],
            )

        if chart is not None:
            st.altair_chart(
                chart.properties(height=380).configure_axis(
                    labelFontWeight="bold", titleFontWeight="bold",
                    labelFontSize=13, titleFontSize=15,
                ),
                use_container_width=True,
            )

        from .report import excel_safe
        st.download_button(
            "Download grouped values",
            excel_safe(grouped).to_csv(index=False).encode("utf-8-sig"),
            "grouped_values.csv", "text/csv",
        )

    except Exception as error:
        st.error(f"Unable to explore this file: {error}")
