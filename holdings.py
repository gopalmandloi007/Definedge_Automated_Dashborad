import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
import numpy as np
from utils import integrate_get

TOTAL_CAPITAL = 1400000

def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def get_ltp(exchange, token):
    path = f"/quotes/{exchange}/{token}"
    st.write(f"Fetching LTP for: {exchange}/{token}") # Add for debugging
    data = integrate_get(path)
    st.write(f"API Response for LTP {token}: {data}") # Log the full response
    if data and data.get("status") == "SUCCESS":
        return safe_float(data.get("ltp", 0))
    st.write(f"Failed to get LTP for {token}. Response status: {data.get('status', 'N/A')}")
    return 0.0

def get_prev_close(exchange, token, api_key):
    today = datetime.now()
    max_lookback = 7
    prev_close = 0
    for i in range(1, max_lookback+1):
        prev_day = today - timedelta(days=i)
        if prev_day.weekday() < 5:
            from_str = prev_day.strftime("%d%m%Y0000")
            to_str = prev_day.strftime("%d%m%Y1530")
            url = f"https://data.definedgesecurities.com/sds/history/{exchange}/{token}/day/{from_str}/{to_str}"
            headers = {"Authorization": api_key}
            try:
                st.write(f"Fetching prev close URL: {url}")
                resp = requests.get(url, headers=headers, timeout=6)
                resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                if resp.text.strip():
                    rows = resp.text.strip().split("\n")
                    if len(rows) >= 2:
                        prev_close = safe_float(rows[-2].split(",")[4])
                    elif len(rows) == 1:
                        prev_close = safe_float(rows[0].split(",")[4])
                    st.write(f"Previous close found: {prev_close}")
                    break
                else:
                    st.write(f"API response empty for {token} on {prev_day}")
            except requests.exceptions.RequestException as e:
                st.write(f"Error fetching prev close for {token} on {prev_day}: {e}")
                continue # Skip this day if error
    return prev_close

def resolve_symbol_info(h):
    tslist = h.get("tradingsymbol")
    if isinstance(tslist, list):
        for s in tslist:
            if s.get("exchange", "").upper() == "NSE":
                return s
        return tslist[0] if tslist else {}
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

    api_key_for_history = st.secrets.get("integrate_api_session_key", "")

    holdings_data = integrate_get("/holdings")
    holdings = holdings_data.get("data", [])

    # Positions map for realized P&L
    pos_map = {}
    positions = integrate_get("/positions").get("positions", [])
    for p in positions:
        k = (p.get("exchange","").upper(), str(p.get("token","")))
        pos_map[k] = p

    rows = []
    total_invested = total_current = total_today_pnl = total_overall_pnl = total_realized_pnl = 0

    for h in holdings:
        s = resolve_symbol_info(h)
        symbol = s.get("tradingsymbol", "N/A")
        exchange = s.get("exchange", "NSE")
        token = str(s.get("token", ""))
        qty = safe_float(h.get("dp_qty",0)) + safe_float(h.get("t1_qty",0))
        avg_buy = safe_float(h.get("avg_buy_price",0))
        invested = qty * avg_buy

        ltp = get_ltp(exchange, token) # Call get_ltp for LTP
        prev_close = get_prev_close(exchange, token, api_key_for_history) # Call get_prev_close
        current_value = qty * ltp
        today_pnl = qty * (ltp - prev_close) if prev_close else 0
        overall_pnl = qty * (ltp - avg_buy) if avg_buy else 0

        realized_pnl = 0.0
        pos = pos_map.get((exchange.upper(), token))
        if pos:
            realized_pnl = safe_float(pos.get("realized_pnl",0))

        total_invested += invested
        total_current += current_value
        total_today_pnl += today_pnl
        total_overall_pnl += overall_pnl
        total_realized_pnl += realized_pnl

        rows.append({
            "Symbol": symbol,
            "Exchange": exchange,
            "Avg Buy": avg_buy,
            "Qty": qty,
            "LTP": ltp,
            "Prev Close": prev_close,
            "Invested": invested,
            "Current Value": current_value,
            "Today P&L": today_pnl,
            "Overall P&L": overall_pnl,
            "Realized P&L": realized_pnl
        })

    df = pd.DataFrame(rows)
    df["Portfolio %"] = df["Invested"]/TOTAL_CAPITAL*100
    cash_in_hand = TOTAL_CAPITAL - total_invested

    st.subheader("Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Capital", f"₹{TOTAL_CAPITAL:,.0f}")
    c2.metric("Invested", f"₹{total_invested:,.0f}")
    c3.metric("Current Value", f"₹{total_current:,.0f}")
    c4.metric("Cash in Hand", f"₹{cash_in_hand:,.0f}")
    c5.metric("Today P&L", f"₹{total_today_pnl:,.0f}")
    c6.metric("Overall P&L", f"₹{total_overall_pnl:,.0f}")

    st.subheader("Portfolio Allocation")
    pie_df = pd.concat([
        df[["Symbol","Invested"]],
        pd_DataFrame([{"Symbol":"Cash in Hand","Invested":cash_in_hand}])
    ], ignore_index=True)
    fig = go.Figure(data=[go.Pie(labels=pie_df["Symbol"], values=pie_df["Invested"], hole=0.3)])
    fig.update_traces(textinfo='label+percent')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Holdings Table")
    st.dataframe(
        df.style.applymap(highlight_pnl, subset=["Today P&L","Overall P&L"])
        .format({"Avg Buy":"{:.2f}", "LTP":"{:.2f}", "Prev Close":"{:.2f}",
                 "Invested":"{:.2f}", "Current Value":"{:.2f}",
                 "Today P&L":"{:.2f}", "Overall P&L":"{:.2f}",
                 "Realized P&L":"{:.2f}
        })
    )
