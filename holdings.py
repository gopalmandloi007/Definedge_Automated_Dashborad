import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import io
import numpy as np
from utils import integrate_get

# ==== CONFIG ====
TOTAL_CAPITAL = 1400000

# ==== API HELPERS ====
def get_api_key():
    return st.secrets.get("integrate_api_session_key", "")

def safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default

def get_ltp(exchange, token, api_key):
    url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exchange}/{token}"
    headers = {"Authorization": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return safe_float(data.get("ltp", 0))
    except Exception:
        pass
    return 0.0

def get_prev_close(exchange, token, api_key):
    # Handles weekends/holidays automatically
    today = datetime.now()
    max_lookback = 7
    for i in range(1, max_lookback+1):
        prev_day = today - timedelta(days=i)
        if prev_day.weekday() < 5:  # Weekday
            break
    from_str = prev_day.strftime("%d%m%Y0000")
    to_str = today.strftime("%d%m%Y1530")
    url = f"https://data.definedgesecurities.com/sds/history/{exchange}/{token}/day/{from_str}/{to_str}"
    headers = {"Authorization": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200 and resp.text.strip():
            rows = resp.text.strip().split("\n")
            # Use last close before today (NOT today's incomplete candle)
            if len(rows) >= 2:
                prev_row = rows[-2]
                prev_close = safe_float(prev_row.split(",")[4])
                return prev_close
            elif len(rows) == 1:
                prev_close = safe_float(rows[0].split(",")[4])
                return prev_close
    except Exception:
        pass
    return 0.0

def get_positions(api_key):
    url = "https://integrate.definedgesecurities.com/dart/v1/positions"
    headers = {"Authorization": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=7)
        if resp.status_code == 200:
            return resp.json().get("positions", [])
    except Exception:
        pass
    return []

def resolve_symbol_info(h):
    # Always prefer NSE if available
    tslist = h.get("tradingsymbol")
    if isinstance(tslist, list):
        for s in tslist:
            if isinstance(s, dict) and s.get("exchange", "").upper() == "NSE":
                return s
        # fallback to first available
        if tslist and isinstance(tslist[0], dict):
            return tslist[0]
    elif isinstance(tslist, dict):
        return tslist
    return {}

def highlight_pnl(val):
    try:
        v = float(val)
        if v > 0: return 'background-color:#c6f5c6'
        if v < 0: return 'background-color:#ffcccc'
    except: pass
    return ''

def app():
    st.title("Holdings Details Dashboard")
    st.caption("Detailed, real-time portfolio analytics and allocation")

    api_key = get_api_key()
    master_df = None  # If you want to use for token lookup etc

    # Fetch all data
    holdings_data = integrate_get("/holdings")
    holdings = holdings_data.get("data", [])

    positions = get_positions(api_key)
    # Map (exchange, token/isin) to realized/unrealized P&L, net qty, etc.
    pos_map = {}
    for p in positions:
        ex = p.get("exchange", "").upper()
        token = str(p.get("token", ""))
        isin = p.get("isin", "")
        k = (ex, token)
        pos_map[k] = p

    rows = []
    total_invested = 0
    total_current = 0
    total_today_pnl = 0
    total_overall_pnl = 0
    total_realized_pnl = 0

    for h in holdings:
        s = resolve_symbol_info(h)
        symbol = s.get("tradingsymbol", "N/A")
        exchange = s.get("exchange", "NSE")
        token = str(s.get("token", ""))
        isin = s.get("isin", "")
        qty = safe_float(h.get("dp_qty", 0)) + safe_float(h.get("t1_qty", 0))
        avg_buy = safe_float(h.get("avg_buy_price", 0))
        invested = qty * avg_buy

        ltp = get_ltp(exchange, token, api_key)
        prev_close = get_prev_close(exchange, token, api_key)
        current_value = qty * ltp
        today_chg_pct = ((ltp - prev_close) / prev_close * 100) if prev_close else 0
        today_pnl = (ltp - prev_close) * qty if prev_close else 0
        overall_pnl = (ltp - avg_buy) * qty if avg_buy else 0

        # Realized P&L logic (partial sell case) - using positions API
        # Try by token+exchange, fallback to 0 if not found
        realized_pnl = 0.0
        pos = pos_map.get((exchange.upper(), token))
        if pos:
            realized_pnl = safe_float(pos.get("realized_pnl", 0))
        total_qty = qty
        total_invested += invested
        total_current += current_value
        total_today_pnl += today_pnl
        total_overall_pnl += overall_pnl
        total_realized_pnl += realized_pnl

        rows.append({
            "Symbol": symbol,
            "Exchange": exchange,
            "ISIN": isin,
            "Avg Buy": avg_buy,
            "Total Qty": total_qty,
            "LTP": ltp,
            "Prev Close": prev_close,
            "Invested": invested,
            "Current Value": current_value,
            "Today % Chg": today_chg_pct,
            "Today P&L": today_pnl,
            "Overall P&L": overall_pnl,
            "Realized P&L": realized_pnl,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("Invested", ascending=False)
    # Portfolio percent allocation
    df["Portfolio %"] = (df["Invested"] / TOTAL_CAPITAL * 100).round(2)
    cash_in_hand = TOTAL_CAPITAL - total_invested
    cash_percent = (cash_in_hand / TOTAL_CAPITAL * 100) if TOTAL_CAPITAL else 0

    # Action logic
    df["Action"] = np.where(df["Today % Chg"] < -5, "MONITOR CLOSELY",
                    np.where(df["Overall P&L"] < 0, "REVIEW STOP LOSS",
                    np.where(df["Portfolio %"] > 15, "CONSIDER REDUCE",
                    np.where(df["Overall P&L"] > 0, "HOLD", ""))))

    # ==== SUMMARY ====
    st.subheader("Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Capital", f"₹{TOTAL_CAPITAL:,.0f}")
    c2.metric("Invested", f"₹{total_invested:,.0f}")
    c3.metric("Current Value", f"₹{total_current:,.0f}")
    c4.metric("Cash in Hand", f"₹{cash_in_hand:,.0f}")
    c5.metric("Today P&L", f"₹{total_today_pnl:,.0f}")
    c6.metric("Overall P&L", f"₹{total_overall_pnl:,.0f}")

    # ==== PIE CHART ====
    st.subheader("Portfolio Allocation")
    pie_df = pd.concat([
        df[["Symbol", "Invested"]],
        pd.DataFrame([{"Symbol": "Cash in Hand", "Invested": cash_in_hand}])
    ], ignore_index=True)
    fig = go.Figure(data=[go.Pie(labels=pie_df["Symbol"], values=pie_df["Invested"], hole=0.3)])
    fig.update_traces(textinfo='label+percent')
    st.plotly_chart(fig, use_container_width=True)

    # ==== TABLE ====
    st.subheader("Holdings Table")
    show_cols = ["Symbol", "Exchange", "ISIN", "Avg Buy", "Total Qty", "LTP", "Prev Close",
                "Invested", "Current Value", "Today % Chg", "Today P&L", "Overall P&L", "Realized P&L", "Portfolio %", "Action"]
    st.dataframe(
        df[show_cols]
            .style.applymap(highlight_pnl, subset=["Today P&L", "Overall P&L"])
            .format({"Avg Buy": "{:.2f}", "LTP": "{:.2f}", "Prev Close": "{:.2f}",
                    "Invested": "{:.2f}", "Current Value": "{:.2f}", "Today % Chg": "{:.2f}",
                    "Today P&L": "{:.2f}", "Overall P&L": "{:.2f}", "Realized P&L": "{:.2f}", "Portfolio %": "{:.2f}"})
        , use_container_width=True
    )

    st.caption("**Note:** All calculations are live. Realized P&L is fetched from Positions API, partial sells handled. Cash in hand is based on default total capital.")

if __name__ == "__main__":
    app()
