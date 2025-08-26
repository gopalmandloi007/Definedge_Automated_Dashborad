import streamlit as st
import pandas as pd
from utils import integrate_get

def app():
    st.header("📊 Holdings & Positions Tracker (Session-based)")

    # Session check
    if "integrate_session" not in st.session_state:
        st.error("You are not logged in. Please login to view your holdings.")
        return

    # Call API with session headers
    holdings_resp = integrate_get("/holdings")
    st.write("DEBUG: Raw /holdings API response:", holdings_resp)

    # Parse holdings
    holdings = []
    if holdings_resp and isinstance(holdings_resp, dict):
        # Broker may use "data", "holdings", or "result"
        for key in ("data", "holdings", "result"):
            if isinstance(holdings_resp.get(key), list):
                holdings = holdings_resp.get(key, [])
                break

    st.write(f"DEBUG: Found {len(holdings)} holdings in API response.")
    if not holdings:
        st.error("No holdings found. Check the debug output above for API errors or session issues!")
        return

    # Make DataFrame
    rows = []
    for h in holdings:
        ts = h.get("tradingsymbol")
        if isinstance(ts, list) and ts and isinstance(ts[0], dict):
            symbol = ts[0].get("tradingsymbol", "")
            exchange = ts[0].get("exchange", h.get("exchange", ""))
            isin = ts[0].get("isin", h.get("isin", ""))
        elif isinstance(ts, dict):
            symbol = ts.get("tradingsymbol", "")
            exchange = ts.get("exchange", h.get("exchange", ""))
            isin = ts.get("isin", h.get("isin", ""))
        else:
            symbol = ts if ts else h.get("symbol", "")
            exchange = h.get("exchange", "")
            isin = h.get("isin", "")

        qty = h.get("dp_qty", 0)
        t1_qty = h.get("t1_qty", 0)
        avg_buy_price = h.get("avg_buy_price", 0)

        try: qty = float(qty)
        except: qty = 0.0
        try: t1_qty = float(t1_qty)
        except: t1_qty = 0.0
        try: avg_buy_price = float(avg_buy_price)
        except: avg_buy_price = 0.0

        current_value = (qty + t1_qty) * avg_buy_price

        rows.append({
            "Symbol": symbol,
            "Exchange": exchange,
            "ISIN": isin,
            "DP Qty": qty,
            "T1 Qty": t1_qty,
            "Avg. Buy Price": avg_buy_price,
            "Current Value": current_value
        })

    holdings_df = pd.DataFrame(rows)
    st.write("DEBUG: Holdings DataFrame preview:", holdings_df)

    if holdings_df.empty:
        st.error("No valid holdings records found after processing API data.")
        return

    st.dataframe(holdings_df)
    st.download_button("Download Holdings (CSV)", holdings_df.to_csv(index=False), "holdings.csv")
