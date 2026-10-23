from pathlib import Path
if __package__:
    from .processor import validate_sales
else:
    from processor import validate_sales

def analyze_sales(clean):
    if clean.empty:
        raise ValueError("No valid sales rows available for analysis.")

    summary = {
        "Valid orders": clean["Order_ID"].nunique(),
        "Units sold": int(clean["Quantity"].sum()),
        "Total revenue": round(clean["Revenue"].sum(), 2),
        "Average order value": round(clean["Revenue"].sum() / clean["Order_ID"].nunique(), 2),
    }

    monthly = (
        clean.assign(Month=clean["Date"].dt.strftime("%Y-%m"))
        .groupby("Month", as_index=False)
        .agg(
            Orders=("Order_ID", "nunique"),
            Units=("Quantity", "sum"),
            Revenue=("Revenue", "sum"),
        )
        .sort_values("Month")
    )

    products = (
        clean.groupby("Product", as_index=False)
        .agg(Units=("Quantity", "sum"), Revenue=("Revenue", "sum"))
        .sort_values("Revenue", ascending=False)
    )

    categories = (
        clean.groupby("Category", as_index=False)
        .agg(Units=("Quantity", "sum"), Revenue=("Revenue", "sum"))
        .sort_values("Revenue", ascending=False)
    )

    return summary, monthly, products, categories

if __name__ == "__main__":
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else "data/sample_sales.csv"
    try:
        clean, issues = validate_sales(source)
        summary, monthly, products, categories = analyze_sales(clean)
        Path("output").mkdir(exist_ok=True)

        monthly.to_csv("output/monthly_sales.csv", index=False)
        products.to_csv("output/product_sales.csv", index=False)
        categories.to_csv("output/category_sales.csv", index=False)

        print("SALES SUMMARY")
        for name, value in summary.items():
            print(f"{name}: {value}")
        print("Rows excluded for review:", len(issues))
        print("\nMONTHLY SALES")
        print(monthly.to_string(index=False))
        print("\nPRODUCT SALES")
        print(products.to_string(index=False))
        print("\nCATEGORY SALES")
        print(categories.to_string(index=False))
    except (ValueError, OSError) as error:
        print("ERROR:", error)
        sys.exit(1)
