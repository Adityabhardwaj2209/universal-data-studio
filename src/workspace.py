from io import BytesIO
import hashlib
import pandas as pd
import altair as alt
import streamlit as st

from .report import excel_safe


@st.cache_data(show_spinner=False, max_entries=16, ttl=600)
def build_downloads(data):
    export = data.copy()
    export["Date"] = export["Date"].dt.strftime("%Y-%m-%d")

    monthly = (
        data.assign(Month=data["Date"].dt.strftime("%Y-%m"))
        .groupby("Month", as_index=False)
        .agg(
            Revenue=("Revenue", "sum"),
            Units=("Quantity", "sum"),
            Orders=("Order_ID", "nunique"),
        )
    )
    products = (
        data.groupby("Product", as_index=False)
        .agg(
            Revenue=("Revenue", "sum"),
            Units=("Quantity", "sum"),
            Orders=("Order_ID", "nunique"),
        )
        .sort_values("Revenue", ascending=False)
    )
    summary = pd.DataFrame({
        "Metric": ["Orders", "Units", "Revenue", "Average order value"],
        "Value": [
            data["Order_ID"].nunique(),
            data["Quantity"].sum(),
            round(data["Revenue"].sum(), 2),
            round(data["Revenue"].sum() / data["Order_ID"].nunique(), 2),
        ],
    })

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in {
            "Summary": summary,
            "Monthly Sales": monthly,
            "Products": products,
            "Filtered Data": export,
        }.items():
            excel_safe(frame).to_excel(
                writer, sheet_name=name, index=False
            )
            sheet = writer.sheets[name]
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            from openpyxl.styles import Font, PatternFill
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="8756AC")
            for column in sheet.columns:
                sheet.column_dimensions[
                    column[0].column_letter
                ].width = min(
                    45,
                    max(14, max(
                        len(str(cell.value or "")) for cell in column
                    ) + 2),
                )

    csv = excel_safe(export).to_csv(index=False).encode("utf-8-sig")
    return csv, buffer.getvalue()


def render_workspace(clean, issues):
    from .history import history_panel
    clean, issues = history_panel(clean, issues)

    identity = hashlib.sha256(
        pd.util.hash_pandas_object(clean, index=True)
        .values.tobytes()
    ).hexdigest()[:12]
    prefix = "workspace_" + identity

    st.subheader("Explore your sales")
    st.caption("Filters update every metric, graph, table and download below.")

    with st.expander("Filter your data", expanded=True):
        with st.form(prefix + "_filters"):
            left, right = st.columns(2)
            dates = left.date_input(
                "Date range",
                value=(
                    clean["Date"].min().date(),
                    clean["Date"].max().date(),
                ),
                min_value=clean["Date"].min().date(),
                max_value=clean["Date"].max().date(),
            )
            categories = right.multiselect(
                "Categories",
                sorted(clean["Category"].unique()),
                help="Leave empty to include all categories.",
            )
            products = st.multiselect(
                "Products",
                sorted(clean["Product"].unique()),
                help="Leave empty to include all products.",
            )
            apply = st.form_submit_button("Apply filters")

        defaults = {
            "dates": (
                clean["Date"].min().date(),
                clean["Date"].max().date(),
            ),
            "categories": [],
            "products": [],
        }
        if prefix not in st.session_state:
            st.session_state[prefix] = defaults

        if apply:
            if not isinstance(dates, (list, tuple)) or len(dates) != 2:
                st.warning("Select both start and end dates.")
            else:
                st.session_state[prefix] = {
                    "dates": dates,
                    "categories": categories,
                    "products": products,
                }

    selected = st.session_state[prefix]
    start, end = selected["dates"]
    data = clean.loc[
        clean["Date"].dt.date.between(start, end)
    ].copy()
    if selected["categories"]:
        data = data[data["Category"].isin(selected["categories"])]
    if selected["products"]:
        data = data[data["Product"].isin(selected["products"])]

    st.caption(f"Selected period: {start} to {end}")
    if data.empty:
        st.info("No sales match these filters. Broaden the selection.")
        return

    a, b, c, d = st.columns(4)
    a.metric("Revenue", f"INR {data['Revenue'].sum():,.2f}")
    b.metric("Orders", data["Order_ID"].nunique())
    c.metric("Units sold", f"{data['Quantity'].sum():,.0f}")
    d.metric("Average order", f"INR {(data['Revenue'].sum() / data['Order_ID'].nunique()):,.2f}")


    from .insights import render_insights, render_comparison, render_target

    overview, comparison, targets = st.tabs(
        ["Business insights", "Period comparison", "Revenue target"]
    )
    with overview:
        render_insights(data, start, end, prefix)
    with comparison:
        render_comparison(
            clean, start, end,
            selected["categories"], selected["products"], prefix
        )
    with targets:
        render_target(data, start, end, prefix)

    charts, records, downloads = st.tabs(
        ["Chart studio", "Sales table", "Downloads"]
    )

    with charts:
        a, b, c = st.columns(3)
        kind = a.selectbox(
            "Chart format",
            ["Bar", "Line", "Area", "Pie", "Donut", "Scatter", "Histogram"],
            key=prefix + "_kind",
        )
        group = b.selectbox(
            "Group by", ["Month", "Product", "Category"],
            key=prefix + "_group",
        )
        metric = c.selectbox(
            "Measure", ["Revenue", "Units", "Orders"],
            key=prefix + "_metric",
        )
        colour = st.selectbox(
            "Chart colour",
            ["Lavender", "Rose", "Teal", "Blue"],
            key=prefix + "_colour",
        )
        palette = {
            "Lavender": "#8756AC", "Rose": "#B05D96",
            "Teal": "#16867D", "Blue": "#4776B4",
        }
        accent = palette[colour]

        grouped = (
            data.assign(Month=data["Date"].dt.strftime("%Y-%m"))
            .groupby(group, as_index=False)
            .agg(
                Revenue=("Revenue", "sum"),
                Units=("Quantity", "sum"),
                Orders=("Order_ID", "nunique"),
            )
        )

        if kind in ("Pie", "Donut"):
            ranked = grouped.sort_values(metric, ascending=False)
            visible = ranked.head(8).copy()
            if len(ranked) > 8:
                other = pd.DataFrame([{
                    group: "Other categories combined",
                    "Revenue": ranked.iloc[8:]["Revenue"].sum(),
                    "Units": ranked.iloc[8:]["Units"].sum(),
                    "Orders": ranked.iloc[8:]["Orders"].sum(),
                }])
                visible = pd.concat([visible, other], ignore_index=True)
            if visible[metric].sum() <= 0:
                st.info("Choose a measure with a positive total for this chart.")
                chart = None
            else:
                chart = alt.Chart(visible).mark_arc(
                    innerRadius=85 if kind == "Donut" else 0
                ).encode(
                    theta=alt.Theta(field=metric, type="quantitative"),
                    color=alt.Color(
                        field=group, type="nominal",
                        scale=alt.Scale(scheme="tableau10"),
                    ),
                    tooltip=[group, metric],
                )
        elif kind == "Scatter":
            st.caption("Each point is a sales row: quantity versus revenue.")
            chart = alt.Chart(data).mark_circle(
                size=100, opacity=.75, color=accent
            ).encode(
                x=alt.X("Quantity:Q", title="Units per order"),
                y=alt.Y("Revenue:Q", title="Sales-row revenue (INR)"),
                tooltip=["Order_ID", "Product", "Quantity", "Revenue"],
            ).interactive()
        elif kind == "Histogram":
            st.caption("Distribution of individual sales-row revenue.")
            chart = alt.Chart(data).mark_bar(color=accent).encode(
                x=alt.X(
                    "Revenue:Q", bin=alt.Bin(maxbins=20),
                    title="Sales-row revenue (INR)",
                ),
                y=alt.Y("count():Q", title="Number of sales rows"),
                tooltip=[alt.Tooltip("count():Q", title="Sales rows")],
            )
        else:
            ordered = grouped.sort_values(
                group if group == "Month" else metric,
                ascending=group == "Month",
            )
            if group != "Month":
                limit = st.selectbox(
                    "Show top groups", [5, 10, 20, 50],
                    index=1, key=prefix + "_limit",
                )
                ordered = ordered.head(limit)
            chart = alt.Chart(ordered)
            if kind == "Bar":
                chart = chart.mark_bar(
                    color=accent, cornerRadiusTopLeft=5,
                    cornerRadiusTopRight=5,
                )
            elif kind == "Line":
                chart = chart.mark_line(
                    color=accent, strokeWidth=4, point=True
                )
            else:
                chart = chart.mark_area(
                    color=accent, opacity=.65, line=True
                )
            chart = chart.encode(
                x=alt.X(field=group, type="nominal", sort=None),
                y=alt.Y(field=metric, type="quantitative"),
                tooltip=[group, metric],
            )

        if chart is not None:
            chart = chart.properties(height=380).configure_axis(
                labelFontSize=14, labelFontWeight="bold",
                titleFontSize=16, titleFontWeight="bold",
                labelColor="#43205F", titleColor="#43205F",
            ).configure_legend(
                labelFontSize=13, titleFontSize=14,
                labelFontWeight="bold",
            ).configure_view(strokeWidth=0)
            st.altair_chart(chart, use_container_width=True)

        with st.expander("View grouped values"):
            st.dataframe(grouped, hide_index=True)

    with records:
        query = st.text_input(
            "Search orders, products or categories",
            key=prefix + "_search",
        ).strip()
        table = data
        if query:
            mask = data[
                ["Order_ID", "Product", "Category"]
            ].apply(
                lambda column: column.str.contains(
                    query, case=False, regex=False, na=False
                )
            ).any(axis=1)
            table = data.loc[mask]
        a, b = st.columns(2)
        sort_by = a.selectbox(
            "Sort by", ["Date", "Revenue", "Quantity", "Product"],
            key=prefix + "_sort",
        )
        descending = b.checkbox(
            "Descending order", value=True, key=prefix + "_descending"
        )
        st.caption(
            f"{len(table)} matching rows. Search affects this table only."
        )
        st.dataframe(
            table.sort_values(sort_by, ascending=not descending),
            hide_index=True,
        )

    with downloads:
        st.write("Export all valid rows within your applied filters.")
        st.caption(
            "Table search and chart display limits do not change these exports. "
            "The Excel workbook contains data and summary tables."
        )
        csv, workbook = build_downloads(data)
        from .branded_reports import render_branded_exports
        render_branded_exports(data, workbook)

        a, b = st.columns(2)
        a.download_button(
            "Download filtered CSV", csv, "filtered_sales.csv", "text/csv"
        )
        b.download_button(
            "Download filtered Excel",
            workbook,
            "filtered_sales.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        if not issues.empty:
            st.caption("Validation issues cover the original uploaded file.")
            st.download_button(
                "Download original validation issues",
                excel_safe(issues).to_csv(index=False).encode("utf-8-sig"),
                "validation_issues.csv",
                "text/csv",
            )
