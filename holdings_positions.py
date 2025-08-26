import streamlit as st
import pandas as pd
from utils import integrate_get

def app():
    st.header("📊 Holdings & Positions Tracker")
    st.markdown(
        """
        <style>
        .big-font {font-size:26px !important;}
        .metric-box {background: #fafaff; border-radius: 12px; box-shadow: 1px 1px 8px #eee; padding: 22px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Fetch Holdings ---
    holdings_resp = integrate_get("/holdings")
    holdings = holdings_resp.get("data", []) if holdings_resp else []

    # --- Fetch Positions ---
    positions_resp = integrate_get("/positions")
    positions = positions_resp.get("data", []) if positions_resp else []

    # --- Holdings Table ---
    st.subheader("💼 Current Holdings")
    if holdings:
        holdings_df = pd.DataFrame([
            {
                "Symbol": h["tradingsymbol"][0]["tradingsymbol"] if h.get("tradingsymbol") else "",
                "Exchange": h["tradingsymbol"][0]["exchange"] if h.get("tradingsymbol") else "",
                "ISIN": h["tradingsymbol"][0].get("isin", ""),
                "Qty": h.get("dp_qty", 0),
                "Avg. Buy Price": h.get("avg_buy_price", 0),
                "Current Value": h.get("dp_qty", 0) * h.get("avg_buy_price", 0),
            }
            for h in holdings
        ])
        st.dataframe(holdings_df.style.format({"Avg. Buy Price": "{:.2f}", "Current Value": "{:.2f}"}))
        st.metric("Total Holdings Value", f"₹ {holdings_df['Current Value'].sum():,.2f}")
    else:
        st.info("No holdings found.")

    # --- Positions Table ---
    st.subheader("📈 Open Positions")
    if positions:
        positions_df = pd.DataFrame([
            {
                "Symbol": p.get("tradingsymbol", ""),
                "Exchange": p.get("exchange", ""),
                "Qty": p.get("netqty", 0),
                "Buy Avg": p.get("buyavgprice", 0),
                "Sell Avg": p.get("sellavgprice", 0),
                "Net P&L": p.get("rpnl", 0),
                "Unrealized P&L": p.get("urmtom", 0),
            }
            for p in positions
        ])
        st.dataframe(positions_df.style.format({"Buy Avg": "{:.2f}", "Sell Avg": "{:.2f}", "Net P&L": "{:.2f}", "Unrealized P&L": "{:.2f}"}))
        st.metric("Total Net P&L", f"₹ {positions_df['Net P&L'].sum():,.2f}")
    else:
        st.info("No open positions found.")

    # --- Summary Cards ---
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="metric-box big-font">💰 Holdings Value<br><b>₹ {holdings_df["Current Value"].sum():,.2f}</b></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-box big-font">📈 Net P&L<br><b>₹ {positions_df["Net P&L"].sum():,.2f}</b></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="metric-box big-font">📊 Holdings Count<br><b>{len(holdings_df) if holdings else 0}</b></div>', unsafe_allow_html=True)

    # --- Download Buttons ---
    st.markdown("---")
    st.download_button("Download Holdings CSV", holdings_df.to_csv(index=False), "holdings.csv")
    st.download_button("Download Positions CSV", positions_df.to_csv(index=False), "positions.csv")
