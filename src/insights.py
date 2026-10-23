import pandas as pd
import streamlit as st


def render_insights(data, start, end, key_prefix):
    st.subheader("Business insights")
    revenue = float(data["Revenue"].sum())
    products = data.groupby("Product")["Revenue"].sum()
    categories = data.groupby("Category")["Revenue"].sum()
    top_product = products.idxmax()
    top_category = categories.idxmax()

    a, b = st.columns(2)
    a.info(
        f"Top product: {top_product} — "
        f"INR {products[top_product]:,.2f}"
    )
    share = categories[top_category] / revenue * 100 if revenue else 0
    b.info(
        f"Leading category: {top_category} — "
        f"{share:.1f}% of revenue"
    )
    st.caption(
        f"{len(data):,} sales rows and "
        f"{data['Order_ID'].nunique():,} unique orders. "
        f"Selected period: {start} to {end}."
    )


def render_comparison(full_data, start, end, categories, products, key_prefix):
    st.subheader("Period comparison")
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    days = (end - start).days + 1
    previous_end = start - pd.Timedelta(days=1)
    previous_start = previous_end - pd.Timedelta(days=days - 1)

    eligible = full_data.copy()
    if categories:
        eligible = eligible[eligible["Category"].isin(categories)]
    if products:
        eligible = eligible[eligible["Product"].isin(products)]

    dates = eligible["Date"].dt.normalize()
    current = eligible[dates.between(start, end)]
    previous = eligible[dates.between(previous_start, previous_end)]

    st.caption(
        f"Current: {start.date()} to {end.date()} | "
        f"Previous: {previous_start.date()} to {previous_end.date()}"
    )
    if previous.empty:
        st.info("No matching records in the previous period.")
        return

    st.caption(
        "Comparison uses uploaded records. Confirm the file covers "
        "both full periods; missing dates may mean missing data."
    )

    def metrics(frame):
        orders = frame["Order_ID"].nunique()
        revenue = float(frame["Revenue"].sum())
        return {
            "Revenue": revenue,
            "Orders": orders,
            "Units": float(frame["Quantity"].sum()),
            "Average order": revenue / orders if orders else 0,
        }

    now = metrics(current)
    before = metrics(previous)
    rows = []

    for column, metric in zip(st.columns(4), now):
        value = now[metric]
        prior = before[metric]
        change = (value - prior) / prior * 100 if prior else None
        money = metric in ("Revenue", "Average order")
        column.metric(
            metric,
            f"INR {value:,.2f}" if money else f"{value:,.0f}",
            delta=f"{change:+.1f}%" if change is not None else None,
        )
        rows.append({
            "Metric": metric,
            "Current": round(value, 2),
            "Previous": round(prior, 2),
            "Change (%)": round(change, 2) if change is not None else None,
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption(
        "Percentage change is unavailable when the previous value is zero."
    )


def render_target(data, start, end, key_prefix):
    st.subheader("Revenue target")
    st.caption(f"Target applies to selected filters: {start} to {end}.")
    target = st.number_input(
        "Target revenue (INR)",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        key=key_prefix + "_target",
    )
    if target <= 0:
        st.info("Enter a positive target to track progress.")
        return

    actual = float(data["Revenue"].sum())
    a, b, c = st.columns(3)
    a.metric("Actual revenue", f"INR {actual:,.2f}")
    b.metric("Achieved", f"{actual / target * 100:.1f}%")
    c.metric("Remaining", f"INR {max(target - actual, 0):,.2f}")
    st.progress(min(max(actual / target, 0.0), 1.0))
    if actual >= target:
        st.success("Revenue target achieved.")
    st.caption("Target is saved for this session only.")
