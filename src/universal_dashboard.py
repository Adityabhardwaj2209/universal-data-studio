import pandas as pd
import altair as alt
import streamlit as st


def calculate(series, operation):
    if operation == "Count":
        return int(series.count())
    if operation == "Distinct":
        return int(series.nunique())
    if series.dropna().empty:
        return None
    if operation == "Sum":
        return series.sum(min_count=1)
    methods = {
        "Mean": "mean", "Median": "median",
        "Min": "min", "Max": "max",
    }
    return getattr(series, methods[operation])()


def render_dashboard(data, schema, identity):
    st.divider()
    st.header("Your dataset dashboard")
    key = "ud_" + identity
    specs = schema.set_index("Column")
    fields = list(data.columns)
    measures = [
        column for column in fields
        if specs.loc[column, "Role"] == "Measure"
        and specs.loc[column, "Type"] == "Number"
    ]
    dates = [
        column for column in fields
        if specs.loc[column, "Type"] == "Date"
    ]

    filtered = data.copy()

    with st.expander("Dashboard filters"):
        filter_fields = st.multiselect(
            "Fields to filter",
            fields,
            key=key + "_filter_fields",
        )
        for position, column in enumerate(filter_fields):
            series = filtered[column]
            kind = specs.loc[column, "Type"]
            widget_key = key + "_filter_" + str(position) + "_" + column

            if kind == "Date":
                valid = series.dropna()
                if valid.empty:
                    st.caption(column + ": no valid dates.")
                    continue
                bounds = st.date_input(
                    column,
                    value=(valid.min().date(), valid.max().date()),
                    key=widget_key,
                )
                if isinstance(bounds, (tuple, list)) and len(bounds) == 2:
                    filtered = filtered[
                        series.dt.date.between(bounds[0], bounds[1])
                    ]
            elif kind == "Number":
                valid = series.dropna()
                if valid.empty:
                    st.caption(column + ": no valid numbers.")
                    continue
                a, b = st.columns(2)
                lower = a.number_input(
                    column + " minimum",
                    value=float(valid.min()),
                    key=widget_key + "_min",
                )
                upper = b.number_input(
                    column + " maximum",
                    value=float(valid.max()),
                    key=widget_key + "_max",
                )
                if lower > upper:
                    st.warning("Minimum must not exceed maximum.")
                    return
                filtered = filtered[series.between(lower, upper)]
            else:
                query = st.text_input(
                    column + " contains",
                    key=widget_key,
                    help="Case-insensitive literal text search.",
                )
                if query:
                    mask = series.astype("string").str.contains(
                        query, case=False, regex=False, na=False
                    )
                    filtered = filtered[mask]

    st.caption(
        f"{len(filtered):,} of {len(data):,} rows selected. "
        "Active field filters exclude missing values in those fields."
    )
    if filtered.empty:
        st.info("No records match. Adjust your filters.")
        return

    a, b, c = st.columns(3)
    a.metric("Selected rows", f"{len(filtered):,}")
    b.metric("Available fields", len(fields))
    c.metric("Missing cells", f"{int(filtered.isna().sum().sum()):,}")

    st.subheader("KPI cards")
    chosen = st.multiselect(
        "Choose up to four measures",
        measures,
        default=measures[:min(2, len(measures))],
        max_selections=4,
        key=key + "_kpis",
    )

    operations = ["Sum", "Mean", "Median", "Count", "Distinct", "Min", "Max"]
    if chosen:
        for position, (column, card) in enumerate(
            zip(chosen, st.columns(len(chosen)))
        ):
            with card:
                suggested = specs.loc[column, "Aggregation"]
                default = operations.index(suggested) if suggested in operations else 1
                operation = st.selectbox(
                    column + " calculation",
                    operations,
                    index=default,
                    key=key + "_kpi_op_" + column,
                )
                value = calculate(filtered[column], operation)
                display = "No values" if value is None else f"{value:,.2f}"
                st.metric(column + " / " + operation, display)

    st.caption(
        "Missing numeric values are excluded. Count means nonmissing values; "
        "Distinct counts unique nonmissing values. Choose calculations "
        "appropriate to the meaning of your fields."
    )

    chart_tab, table_tab = st.tabs(["Chart builder", "Filtered table"])

    with chart_tab:
        a, b = st.columns(2)
        kind = a.selectbox(
            "Chart format",
            ["Bar", "Line", "Area", "Donut", "Scatter", "Histogram"],
            key=key + "_chart",
        )
        measure = b.selectbox(
            "Y / measure",
            ["Row count"] + measures,
            key=key + "_y",
        )
        chart = None
        grouped = None

        if kind in ("Scatter", "Histogram"):
            if measure == "Row count":
                st.info("Select a numeric measure for this chart.")
            elif kind == "Scatter":
                x = st.selectbox(
                    "Numeric X field", measures, key=key + "_scatter_x"
                )
                points = filtered[[x, measure]].dropna().drop_duplicates()
                if points.empty:
                    st.info("No complete numeric pairs available.")
                else:
                    plot = pd.DataFrame({
                        "X": points[x],
                        "Y": points[measure],
                    })
                    chart = alt.Chart(plot).mark_circle(
                        size=75, opacity=.65, color="#8756AC"
                    ).encode(
                        x=alt.X("X:Q", title=x),
                        y=alt.Y("Y:Q", title=measure),
                        tooltip=["X:Q", "Y:Q"],
                    ).interactive()
                    st.caption("Overlapping identical pairs share a point.")
            else:
                plot = pd.DataFrame({"Value": filtered[measure].dropna()})
                if plot.empty:
                    st.info("No valid numeric values available.")
                else:
                    chart = alt.Chart(plot).mark_bar(
                        color="#8756AC"
                    ).encode(
                        x=alt.X(
                            "Value:Q", bin=alt.Bin(maxbins=25),
                            title=measure,
                        ),
                        y=alt.Y("count():Q", title="Rows"),
                    )
        else:
            group = st.selectbox(
                "Group / X field", fields, key=key + "_x"
            )
            working = filtered.copy()
            if group in dates:
                interval = st.selectbox(
                    "Time grouping", ["Day", "Month", "Year"],
                    key=key + "_interval",
                )
                formats = {
                    "Day": "%Y-%m-%d", "Month": "%Y-%m", "Year": "%Y"
                }
                working["_Group"] = working[group].dt.strftime(
                    formats[interval]
                )
            else:
                working["_Group"] = working[group].astype("string")

            if measure == "Row count":
                grouped = working.groupby(
                    "_Group", dropna=True
                ).size().reset_index(name="Value")
                description = "Row count"
            else:
                suggested = specs.loc[measure, "Aggregation"]
                operation = st.selectbox(
                    "Chart calculation",
                    operations,
                    index=operations.index(suggested) if suggested in operations else 1,
                    key=key + "_chart_op_" + measure,
                )
                grouped = (
                    working.groupby("_Group", dropna=True)[measure]
                    .agg(lambda values: calculate(values, operation))
                    .reset_index(name="Value")
                )
                description = operation + " of " + measure

            grouped = grouped.dropna(subset=["Value"])
            grouped = grouped.rename(columns={"_Group": "Group"})
            if grouped.empty:
                st.info("No values available for these fields.")
            else:
                limit = st.selectbox(
                    "Maximum groups", [10, 20, 50, 100],
                    key=key + "_limit",
                )
                if group in dates or kind in ("Line", "Area"):
                    visible = grouped.sort_values("Group").head(limit)
                else:
                    visible = grouped.sort_values(
                        "Value", ascending=False
                    ).head(limit)

                st.caption(
                    f"{len(visible)} of {len(grouped)} groups displayed. "
                    "Missing group values are excluded."
                )
                plot = alt.Chart(visible)
                if kind == "Donut":
                    if (visible["Value"] < 0).any() or visible["Value"].sum() <= 0:
                        st.warning("Donut requires non-negative values and a positive total.")
                    else:
                        chart = plot.mark_arc(innerRadius=80).encode(
                            theta="Value:Q",
                            color=alt.Color(
                                "Group:N", scale=alt.Scale(scheme="tableau10")
                            ),
                            tooltip=["Group:N", "Value:Q"],
                        )
                        st.caption("Shares refer to displayed groups only.")
                else:
                    if kind == "Bar":
                        plot = plot.mark_bar(color="#8756AC")
                    elif kind == "Line":
                        plot = plot.mark_line(
                            color="#8756AC", strokeWidth=4, point=True
                        )
                    else:
                        plot = plot.mark_area(
                            color="#8756AC", opacity=.6, line=True
                        )
                    chart = plot.encode(
                        x=alt.X("Group:N", title=group, sort=None),
                        y=alt.Y("Value:Q", title=description),
                        tooltip=["Group:N", "Value:Q"],
                    )

        if chart is not None:
            st.altair_chart(
                chart.properties(height=380).configure_axis(
                    labelFontWeight="bold",
                    titleFontWeight="bold",
                    labelFontSize=13,
                    titleFontSize=15,
                ),
                use_container_width=True,
            )
        if grouped is not None:
            with st.expander("Chart values"):
                st.dataframe(grouped, hide_index=True)

    from .universal_profiles import save_profile_panel
    save_profile_panel(schema, identity)

    with table_tab:
        visible_fields = st.multiselect(
            "Visible columns", fields,
            default=fields[:min(12, len(fields))],
            key=key + "_visible",
        )
        sort_field = st.selectbox(
            "Sort table by", ["Original order"] + fields,
            key=key + "_sort",
        )
        descending = st.checkbox("Descending", key=key + "_descending")
        table = filtered
        if sort_field != "Original order":
            table = table.sort_values(
                sort_field, ascending=not descending, na_position="last"
            )
        if visible_fields:
            st.dataframe(table[visible_fields], hide_index=True)

        from .report import excel_safe
        st.download_button(
            "Download all filtered fields",
            excel_safe(filtered).to_csv(index=False).encode("utf-8-sig"),
            "filtered_dataset.csv", "text/csv",
            key=key + "_download",
        )
