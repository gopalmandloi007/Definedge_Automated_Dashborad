import streamlit as st
import pandas as pd
from utils import integrate_get

def app():
    st.header("=========== Positions Dashboard Pro ===========")

    # Fetch positions data
    data = integrate_get("/positions")
    raw = data.get('positions', [])

    if not raw:
        st.info("No positions found.")
        st.write("RAW RESPONSE:", data)
        return

    # Find all unique keys in the first row for dynamic columns (like Colab)
    important_cols = [
        ("tradingsymbol", "Symbol"),
        ("net_averageprice", "Avg. Buy"),
        ("net_quantity", "Qty"),
        ("unrealized_pnl", "Unrealised P&L"),
        ("realized_pnl", "Realized P&L"),
        ("percent_change", "% Change"),
        ("product_type", "Product Type"),
    ]
    all_keys = set()
    for row in raw:
        all_keys.update(row.keys())
    rest_keys = [k for k in all_keys if k not in [col[0] for col in important_cols]]
    headers = [col[1] for col in important_cols] + rest_keys

    # Build DataFrame rows
    table = []
    total_unrealized = 0.0
    total_realized = 0.0
    for p in raw:
        # Calculate % Change if not present
        try:
            last_price = float(p.get("lastPrice", 0))
            avg_price = float(p.get("net_averageprice", 0))
            if avg_price:
                percent_change = round((last_price - avg_price) / avg_price * 100, 2)
            else:
                percent_change = "N/A"
        except Exception:
            percent_change = "N/A"

        row = [
            p.get("tradingsymbol", ""),
            p.get("net_averageprice", ""),
            p.get("net_quantity", ""),
            p.get("unrealized_pnl", ""),
            p.get("realized_pnl", ""),
            p.get("percent_change", percent_change),
            p.get("product_type", ""),
        ]
        row += [p.get(k, "") for k in rest_keys]
        table.append(row)

        # Summary totals
        try:
            total_unrealized += float(p.get("unrealized_pnl", 0) or 0)
        except Exception:
            pass
        try:
            total_realized += float(p.get("realized_pnl", 0) or 0)
        except Exception:
            pass

    # Summary
    summary_table = [
        ["Total Realized P&L", round(total_realized, 2)],
        ["Total Unrealized P&L", round(total_unrealized, 2)],
        ["Total Net P&L", round(total_realized + total_unrealized, 2)]
    ]
    st.subheader("P&L Summary")
    st.table(summary_table)
    st.write(f"Total NSE Positions: {len(table)}")

    df = pd.DataFrame(table, columns=headers)
    st.dataframe(df, use_container_width=True)
