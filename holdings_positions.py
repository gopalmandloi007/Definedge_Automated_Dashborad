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
    holdings = holdings_resp.get("data", []) if holdings_resp and holdings_resp.get("status") == "SUCCESS" else []

    # --- Fetch Positions ---
    positions_resp = integrate_get("/positions")
    positions = positions_resp.get("positions", []) if positions_resp and positions_resp.get("status") == "SUCCESS" else []

    # --- Holdings Table ---
    st.subheader("💼 Current Holdings")
    if holdings:
        holdings_df = pd.DataFrame([
            {
                "Symbol": h["tradingsymbol"][0]["tradingsymbol"] if h.get("tradingsymbol") else "",
                "Exchange": h["tradingsymbol"][0]["exchange"] if h.get("tradingsymbol") else "",
                "ISIN": h["tradingsymbol"][0].get("isin", ""),
                "DP Qty": int(h.get("dp_qty", 0)),
                "T1 Qty": int(h.get("t1_qty", 0)),
                "Avg. Buy Price": float(h.get("avg_buy_price", 0)),
                "Current Value": (int(h.get("dp_qty", 0)) + int(h.get("t1_qty", 0))) * float(h.get("avg_buy_price", 0))
            }
            for h in holdings
        ])
        st.dataframe(holdings_df.style.format({"Avg. Buy Price": "{:.2f}", "Current Value": "{:.2f}"}))
    else:
        st.info("No holdings found.")
        holdings_df = pd.DataFrame(columns=["Symbol", "Exchange", "ISIN", "DP Qty", "T1 Qty", "Avg. Buy Price", "Current Value"])

    # --- Positions Table ---
    st.subheader("📈 Open Positions")
    if positions:
        positions_df = pd.DataFrame([
            {
                "Symbol": p.get("tradingsymbol", ""),
                "Exchange": p.get("exchange", ""),
                "Product": p.get("product_type", ""),
                "Net Qty": int(p.get("net_quantity", 0)),
                "Net Avg": float(p.get("net_averageprice", 0)),
                "Realized P&L": float(p.get("realized_pnl", 0)),
                "Unrealized P&L": float(p.get("unrealized_pnl", 0)),
            }
            for p in positions
        ])
        st.dataframe(positions_df.style.format({"Net Avg": "{:.2f}", "Realized P&L": "{:.2f}", "Unrealized P&L": "{:.2f}"}))
    else:
        st.info("No open positions found.")
        positions_df = pd.DataFrame(columns=["Symbol", "Exchange", "Product", "Net Qty", "Net Avg", "Realized P&L", "Unrealized P&L"])

    # --- Summary Cards ---
    col1, col2, col3 = st.columns(3)
    col1.markdown(f'<div class="metric-box big-font">💰 Holdings Value<br><b>₹ {holdings_df["Current Value"].sum():,.2f}</b></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-box big-font">📈 Realized P&L<br><b>₹ {positions_df["Realized P&L"].sum():,.2f}</b></div>', unsafe_allow_html=True)
    col3.markdown(f'<div class="metric-box big-font">📊 Holdings Count<br><b>{len(holdings_df)}</b></div>', unsafe_allow_html=True)

    # --- Download Buttons ---
    st.markdown("---")
    st.download_button("Download Holdings CSV", holdings_df.to_csv(index=False), "holdings.csv")
    st.download_button("Download Positions CSV", positions_df.to_csv(index=False), "positions.csv")
