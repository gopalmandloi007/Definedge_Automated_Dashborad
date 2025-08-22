import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import io
from utils import integrate_get

def is_number(val):
    try:
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    except Exception:
        return False

@st.cache_data
def load_master():
    df = pd.read_csv("master.csv", sep="\t", header=None)
    if df.shape[1] == 15:
        df.columns = [
            "segment", "token", "symbol", "symbol_series", "series", "unknown1",
            "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
            "isin", "unknown7", "company"
        ]
        return df[["segment", "token", "symbol", "symbol_series", "series"]]
    else:
        df.columns = [
            "segment", "token", "symbol", "instrument", "series", "isin1",
            "facevalue", "lot", "something", "zero1", "two1", "one1", "isin", "one2"
        ]
        return df[["segment", "token", "symbol", "instrument", "series"]]

def get_token(symbol, segment, master_df):
    symbol = str(symbol).strip().upper()
    segment = str(segment).strip().upper()
    row = master_df[(master_df['symbol'].str.upper() == symbol) & (master_df['segment'].str.upper() == segment)]
    if not row.empty:
        return row.iloc[0]['token']
    if "symbol_series" in master_df.columns:
        row2 = master_df[(master_df['symbol_series'].str.upper() == symbol) & (master_df['segment'].str.upper() == segment)]
        if not row2.empty:
            return row2.iloc[0]['token']
    if "instrument" in master_df.columns:
        row3 = master_df[(master_df['instrument'].str.upper() == symbol) & (master_df['segment'].str.upper() == segment)]
        if not row3.empty:
            return row3.iloc[0]['token']
    return None

def get_ltp(exchange, token, api_session_key):
    if not exchange or not token:
        return None
    url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exchange}/{token}"
    headers = {"Authorization": api_session_key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            ltp = resp.json().get("ltp", None)
            try:
                return float(ltp) if ltp is not None else None
            except Exception:
                return None
    except Exception:
        pass
    return None

def get_prev_close(exchange, token, api_session_key):
    today = datetime.now()
    for i in range(1, 5):
        prev_day = today - timedelta(days=i)
        if prev_day.weekday() < 5:
            break
    else:
        prev_day = today - timedelta(days=1)
    from_str = prev_day.strftime("%d%m%Y0000")
    to_str = today.strftime("%d%m%Y%H%M")
    url = f"https://data.definedgesecurities.com/sds/history/{exchange}/{token}/day/{from_str}/{to_str}"
    headers = {"Authorization": api_session_key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            rows = resp.text.strip().split("\n")
            if len(rows) >= 2:
                prev_row = rows[-2]
                try:
                    prev_close = float(prev_row.split(",")[4])
                    return prev_close
                except Exception:
                    return None
            elif len(rows) == 1:
                try:
                    prev_close = float(rows[0].split(",")[4])
                    return prev_close
                except Exception:
                    return None
    except Exception:
        pass
    return None

def fetch_candles_definedge(segment, token, from_dt, to_dt, api_key):
    url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/day/{from_dt}/{to_dt}"
    headers = {"Authorization": api_key}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"API error: {resp.status_code} {resp.text}")
    cols = ["Dateandtime", "Open", "High", "Low", "Close", "Volume", "OI"]
    df = pd.read_csv(io.StringIO(resp.text), header=None, names=cols)
    df = df[df["Dateandtime"].notnull()]
    df = df[df["Dateandtime"].astype(str).str.strip() != ""]
    df["Date"] = pd.to_datetime(df["Dateandtime"], format="%d%m%Y%H%M", errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df[df["Date"] <= pd.Timestamp.now()]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def get_time_range(days, endtime="1530"):
    now = datetime.now()
    to = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if to > now:
        to = now
    frm = to - timedelta(days=days)
    return frm.strftime("%d%m%Y%H%M"), to.strftime("%d%m%Y%H%M")

def compute_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    avg_loss = avg_loss.replace(0, 1e-10)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(data, slow=26, fast=12, signal=9):
    ema_slow = data['Close'].ewm(span=slow, adjust=False).mean()
    ema_fast = data['Close'].ewm(span=fast, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def highlight_pnl(val):
    try:
        val = float(val)
        if val > 0:
            return 'background-color:#c6f5c6'
        elif val < 0:
            return 'background-color:#ffcccc'
    except:
        pass
    return ''

def minervini_sell_signals(df, lookback_days=15):
    if len(df) < lookback_days:
        return {"error": "Insufficient data for analysis"}
    recent = df.tail(lookback_days).copy()
    recent['change'] = recent['Close'].pct_change() * 100
    recent['spread'] = recent['High'] - recent['Low']
    signals = {
        'up_days': 0,
        'down_days': 0,
        'up_day_percent': 0,
        'largest_up_day': 0,
        'largest_spread': 0,
        'exhaustion_gap': False,
        'high_volume_reversal': False,
        'churning': False,
        'heavy_volume_down': False,
        'warnings': []
    }
    for i in range(1, len(recent)):
        if recent['Close'].iloc[i] > recent['Close'].iloc[i-1]:
            signals['up_days'] += 1
        elif recent['Close'].iloc[i] < recent['Close'].iloc[i-1]:
            signals['down_days'] += 1
    signals['up_day_percent'] = (signals['up_days'] / lookback_days) * 100
    signals['largest_up_day'] = recent['change'].max()
    signals['largest_spread'] = recent['spread'].max()
    recent['gap_up'] = recent['Open'] > recent['High'].shift(1)
    recent['gap_down'] = recent['Open'] < recent['Low'].shift(1)
    recent['gap_filled'] = False
    for i in range(1, len(recent)):
        if recent['gap_up'].iloc[i]:
            if recent['Low'].iloc[i] <= recent['High'].shift(1).iloc[i]:
                recent.at[recent.index[i], 'gap_filled'] = True
                signals['exhaustion_gap'] = True
    avg_volume = recent['Volume'].mean()
    for i in range(1, len(recent)):
        if recent['Volume'].iloc[i] > avg_volume * 1.5:
            range_ = recent['High'].iloc[i] - recent['Low'].iloc[i]
            if (recent['High'].iloc[i] > recent['High'].iloc[i-1] and
                (recent['Close'].iloc[i] - recent['Low'].iloc[i]) < range_ * 0.25):
                signals['high_volume_reversal'] = True
                break
    if recent['Volume'].iloc[-1] > avg_volume * 1.8:
        price_change = abs(recent['Close'].iloc[-1] - recent['Open'].iloc[-1])
        if price_change < recent['spread'].iloc[-1] * 0.15:
            signals['churning'] = True
    if recent['Volume'].iloc[-1] > avg_volume * 1.5 and recent['change'].iloc[-1] < -3:
        signals['heavy_volume_down'] = True
    if signals['up_day_percent'] >= 70:
        signals['warnings'].append(
            f"⚠️ {signals['up_day_percent']:.0f}% up days ({signals['up_days']}/{lookback_days}) - "
            "Consider selling into strength"
        )
    if signals['largest_up_day'] > 5:
        signals['warnings'].append(
            f"⚠️ Largest up day: {signals['largest_up_day']:.2f}% - "
            "Potential climax run"
        )
    if signals['exhaustion_gap']:
        signals['warnings'].append("⚠️ Exhaustion gap detected - Potential reversal signal")
    if signals['high_volume_reversal']:
        signals['warnings'].append("⚠️ High-volume reversal - Institutional selling")
    if signals['churning']:
        signals['warnings'].append("⚠️ Churning detected (high volume, low progress) - Distribution likely")
    if signals['heavy_volume_down']:
        signals['warnings'].append("⚠️ Heavy volume down day - Consider exiting position")
    return signals

def open_risk_status(open_risk):
    if open_risk <= 0:
        return "Risk Free (Profit Locked)"
    else:
        return "At Risk"

def minervini_high_vs_ema20_interpretation(high, ema20):
    if not is_number(ema20) or ema20 == 0 or pd.isnull(high) or pd.isnull(ema20):
        return "", ""
    diff_pct = ((high - ema20) / ema20) * 100
    diff_pct_rounded = round(diff_pct, 2)
    if diff_pct >= 50:
        interp = "🚨 Immediate Sell: High is 50%+ above 20 EMA"
    elif diff_pct >= 40:
        interp = "⚠️ Ready to Sell: High is 40%+ above 20 EMA"
    elif diff_pct >= 20:
        interp = "⚠️ Caution: High is 20%+ above 20 EMA"
    else:
        interp = "✅ Healthy: High is within reasonable range of 20 EMA"
    return diff_pct_rounded, interp

def app():
    st.title("Holdings Details Dashboard")

    api_session_key = st.secrets.get("integrate_api_session_key", "")
    master_df = load_master()
    data = integrate_get("/holdings")
    holdings = data.get("data", [])
    if not holdings:
        st.warning("No holdings found.")
        return

    rows = []
    for h in holdings:
        ts = h.get("tradingsymbol")
        if isinstance(ts, list):
            if ts:
                if isinstance(ts[0], dict):
                    tsym = ts[0].get("tradingsymbol", "N/A")
                    exch = ts[0].get("exchange", h.get("exchange", "NSE"))
                    segment = ts[0].get("segment", exch)
                else:
                    tsym = str(ts[0])
                    exch = h.get("exchange", "NSE")
                    segment = exch
            else:
                tsym = "N/A"
                exch = h.get("exchange", "NSE")
                segment = exch
        elif isinstance(ts, dict):
            tsym = ts.get("tradingsymbol", "N/A")
            exch = ts.get("exchange", h.get("exchange", "NSE"))
            segment = ts.get("segment", exch)
        else:
            tsym = str(ts) if ts is not None else "N/A"
            exch = h.get("exchange", "NSE")
            segment = exch

        isin = h.get("isin", "")
        product = h.get("product", "")
        try:
            qty = float(h.get("dp_qty", 0) or 0)
        except Exception:
            qty = 0.0
        try:
            entry = float(h.get("avg_buy_price", 0) or 0)
        except Exception:
            entry = 0.0
        invested = entry * qty

        token = get_token(tsym, segment, master_df)
        ltp = get_ltp(exch, token, api_session_key) if token else None
        if not (is_number(ltp) and ltp > 0):
            ltp = get_prev_close(exch, token, api_session_key) if token else None

        if is_number(ltp) and ltp > 0:
            current_value = ltp * qty
            pnl = current_value - invested
        else:
            current_value = ""
            pnl = ""

        initial_sl = round(entry * 0.98, 2)
        status = "Initial SL"
        trailing_sl = initial_sl
        if is_number(ltp) and ltp > 0 and is_number(entry) and entry > 0:
            change_pct = 100 * (ltp - entry) / entry if entry else 0
            if change_pct >= 30:
                trailing_sl = round(entry * 1.20, 2)
                status = "Excellent Profit (SL at Entry +20%)"
            elif change_pct >= 20:
                trailing_sl = round(entry * 1.10, 2)
                status = "Good Profit (SL at Entry +10%)"
            elif change_pct >= 10:
                trailing_sl = round(entry, 2)
                status = "Safe (Breakeven SL)"
        else:
            change_pct = ""

        open_risk = (trailing_sl - entry) * qty
        open_risk_label = open_risk_status(open_risk)

        rows.append({
            "Symbol": tsym,
            "Exchange": exch,
            "ISIN": isin,
            "Product": product,
            "Qty": qty,
            "Entry": entry,
            "Invested": invested,
            "Current Price": ltp if is_number(ltp) and ltp > 0 else "",
            "Current Value": current_value,
            "P&L": pnl,
            "Change %": round(change_pct, 2) if change_pct != "" else "",
            "Status": status,
            "Stop Loss": trailing_sl,
            "Open Risk": open_risk,
            "Open Risk Status": open_risk_label,
            "DP Free Qty": h.get("dp_free_qty", ""),
            "Pledge Qty": h.get("pledge_qty", ""),
            "Collateral Qty": h.get("collateral_qty", ""),
            "T1 Qty": h.get("t1_qty", ""),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("No active holdings with quantity > 0.")
        return

    TOTAL_CAPITAL = 1200000.0
    total_invested = df["Invested"].sum()
    cash_in_hand = max(TOTAL_CAPITAL - total_invested, 0)
    allocation_percent = (total_invested / TOTAL_CAPITAL * 100) if TOTAL_CAPITAL else 0

    st.subheader("💰 Capital Management")
    colA, colB, colC = st.columns(3)
    colA.metric("Total Capital", f"₹{TOTAL_CAPITAL:,.0f}")
    colB.metric("Invested", f"₹{total_invested:,.0f}", f"{allocation_percent:.1f}%")
    colC.metric("Cash in Hand", f"₹{cash_in_hand:,.0f}")

    df_pie = df[["Symbol", "Invested"]].copy()
    df_pie = pd.concat([
        df_pie,
        pd.DataFrame([{"Symbol": "Cash in Hand", "Invested": cash_in_hand}])
    ], ignore_index=True)

    st.subheader("Portfolio Allocation Pie (with Cash)")
    fig = px.pie(
        df_pie,
        names="Symbol",
        values="Invested",
        title="Allocation by Stock & Cash",
        hole=0.3
    )
    fig.update_traces(textinfo='label+percent')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Risk Exposure (Size & Performance)")
    risk_df = df.copy()
    # Fix: Convert to numeric before np.where!
    for col in ['P&L', 'Open Risk', 'Invested', 'Current Value']:
        risk_df[col] = pd.to_numeric(risk_df[col], errors='coerce')
    risk_df['Risk Score'] = np.where(
        risk_df['Open Risk'] > 0, 2,
        np.where(risk_df['P&L'] < 0, 2, 1)
    )
    risk_df['Performance %'] = np.where(
        risk_df['Invested'] > 0, risk_df['P&L'] / risk_df['Invested'] * 100, 0
    ).round(1)
    fig_risk = px.bar(
        risk_df, x='Symbol', y='Current Value',
        color='Risk Score',
        color_continuous_scale="RdYlGn_r",
        title="Risk Exposure by Size & Performance",
        hover_data=['Performance %', 'Open Risk', 'P&L']
    )
    fig_risk.update_layout(xaxis_title="Stock", yaxis_title="Current Value (₹)")
    st.plotly_chart(fig_risk, use_container_width=True)

    show_table = st.toggle("Show Holdings Table", value=False)
    if show_table:
        st.subheader("Holdings Details Table (with Trailing SL & Open Risk)")
        st.dataframe(
            df.style.applymap(
                highlight_pnl,
                subset=["P&L", "Open Risk"]
            ),
            use_container_width=True,
        )
        st.write("#### 🟢 Open Risk Status: If **'Risk Free (Profit Locked)'** hai, toh stoploss pe bhi minimum profit locked hai!")
        st.dataframe(
            df[["Symbol", "Entry", "Stop Loss", "Open Risk", "Open Risk Status"]],
            use_container_width=True
        )

    st.subheader("Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Invested", f"₹{df['Invested'].sum():,.0f}")
    col2.metric("Total Current Value", f"₹{df['Current Value'].replace('', 0).sum():,.0f}")
    col3.metric("Total P&L", f"₹{df['P&L'].replace('', 0).sum():,.0f}")
    col4.metric("Total Qty", f"{df['Qty'].sum():,.0f}")
    col5.metric("Total Open Risk", f"₹{df['Open Risk'].sum():,.0f}")

    st.info(
        "Trailing Stop Loss logic: "
        "Initial SL = Entry - 2%. "
        "If gain >10%, SL moves to Entry (Safe). "
        "If gain >20%, SL = Entry +10% (Good Profit). "
        "If gain >30%, SL = Entry +20% (Excellent Profit)."
    )

    st.subheader("📈 Technical Analysis & Minervini Sell Signals")
    holding_symbols = df["Symbol"].unique()
    if len(holding_symbols):
        selected_symbol = st.selectbox("Select Holding for Chart", sorted(holding_symbols))
        segment = df[df["Symbol"] == selected_symbol]["Exchange"].values[0] if not df[df["Symbol"] == selected_symbol].empty else "NSE"
        token = get_token(selected_symbol, segment, master_df)
        show_ema = st.checkbox("Show EMAs", value=True)
        show_rsi = st.checkbox("Show RSI", value=True)
        show_macd = st.checkbox("Show MACD", value=True)
        days_back = st.slider("Chart Days", 30, 365, 90)
        if token:
            from_dt, to_dt = get_time_range(days_back)
            try:
                chart_df = fetch_candles_definedge(segment, token, from_dt, to_dt, api_key=api_session_key)
                chart_df = chart_df.sort_values("Date")
                chart_df = chart_df[chart_df["Date"] <= pd.Timestamp.now()]
                chart_df['EMA20'] = chart_df['Close'].ewm(span=20, adjust=False).mean()
                if show_ema:
                    chart_df['EMA50'] = chart_df['Close'].ewm(span=50, adjust=False).mean()
                if show_rsi:
                    chart_df['RSI'] = compute_rsi(chart_df)
                if show_macd:
                    macd, signal = compute_macd(chart_df)
                    chart_df['MACD'] = macd
                    chart_df['Signal'] = signal

                rows_chart = 1
                row_heights = [1.0]
                specs = [[{"secondary_y": True}]]
                if show_rsi and show_macd:
                    rows_chart = 3
                    row_heights = [0.6, 0.2, 0.2]
                    specs = [[{"secondary_y": True}], [{}], [{}]]
                elif show_rsi or show_macd:
                    rows_chart = 2
                    row_heights = [0.7, 0.3]
                    specs = [[{"secondary_y": True}], [{}]]
                fig = make_subplots(
                    rows=rows_chart, 
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=row_heights,
                    specs=specs
                )
                fig.add_trace(
                    go.Candlestick(
                        x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                        open=chart_df["Open"],
                        high=chart_df["High"],
                        low=chart_df["Low"],
                        close=chart_df["Close"],
                        name="Price"
                    ),
                    row=1, col=1
                )
                if show_ema:
                    fig.add_trace(
                        go.Scatter(
                            x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                            y=chart_df["EMA20"],
                            mode="lines",
                            name="20 EMA",
                            line=dict(color="blue", width=1.5)
                        ),
                        row=1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                            y=chart_df["EMA50"],
                            mode="lines",
                            name="50 EMA",
                            line=dict(color="orange", width=1.5)
                        ),
                        row=1, col=1
                    )
                if show_rsi:
                    rsi_row = 2 if not show_macd else 2
                    fig.add_trace(
                        go.Scatter(
                            x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                            y=chart_df["RSI"],
                            mode="lines",
                            name="RSI",
                            line=dict(color="purple", width=1.5)
                        ),
                        row=rsi_row, col=1
                    )
                    fig.add_hline(
                        y=30, line_dash="dash", line_color="green",
                        row=rsi_row, col=1
                    )
                    fig.add_hline(
                        y=70, line_dash="dash", line_color="red",
                        row=rsi_row, col=1
                    )
                if show_macd:
                    macd_row = 2 if not show_rsi else 3
                    fig.add_trace(
                        go.Bar(
                            x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                            y=chart_df["MACD"],
                            name="MACD",
                            marker_color=np.where(chart_df['MACD'] > 0, 'green', 'red')
                        ),
                        row=macd_row, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=chart_df["Date"].dt.strftime('%Y-%m-%d'),
                            y=chart_df["Signal"],
                            mode="lines",
                            name="Signal",
                            line=dict(color="blue", width=1.5)
                        ),
                        row=macd_row, col=1
                    )
                fig.update_layout(
                    height=600,
                    title=f"{selected_symbol} Technical Analysis",
                    showlegend=True,
                    xaxis=dict(type="category"),
                    xaxis_rangeslider_visible=False
                )
                st.plotly_chart(fig, use_container_width=True)

                minervini_lookback = st.slider("Analysis Lookback (days)", 7, 30, 15, key="minervini_lookback")
                signals = minervini_sell_signals(chart_df, minervini_lookback)
                if signals.get('error'):
                    st.warning(signals['error'])
                else:
                    st.markdown(f"#### Minervini Sell Signals Analysis ({selected_symbol})")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Up Days", f"{signals['up_days']}/{minervini_lookback}")
                    col2.metric("Up Day %", f"{signals['up_day_percent']:.1f}%")
                    col3.metric("Largest Up Day", f"{signals['largest_up_day']:.2f}%")
                    col4, col5, col6 = st.columns(3)
                    col4.metric("Largest Spread", f"₹{signals['largest_spread']:.2f}")
                    col5.metric("Exhaustion Gap", "Yes" if signals['exhaustion_gap'] else "No")
                    col6.metric("Volume Reversal", "Yes" if signals['high_volume_reversal'] else "No")
                    
                    latest = chart_df.iloc[-1]
                    ema20 = latest['EMA20']
                    high = latest['High']
                    diff_pct, high_interp = minervini_high_vs_ema20_interpretation(high, ema20)
                    col7, col8 = st.columns(2)
                    col7.metric("Current High vs 20 EMA", f"{diff_pct:+.2f}%")
                    col8.markdown(f"**{high_interp}**")

                    if signals['warnings']:
                        st.error(f"🚨 Sell Signals Detected for {selected_symbol} stock")
                        for warning in signals['warnings']:
                            st.write(f"- {warning}")
                        st.markdown("""
**Minervini's Sell Recommendations:**
- Sell into strength when these signals appear
- Consider partial profits on large gains
- Exit completely if multiple signals confirm
                        """)
                    else:
                        st.success("No strong sell signals detected")
                        st.markdown("""
**Minervini's Strength Indicators:**
- Stock is showing healthy price action
- Continue monitoring for sell signals
- Consider holding until signals appear
                        """)
                    st.markdown("""
---
📋 **Position Management Guide**
- **HOLD**: Fundamentals intact, technicals neutral/positive  
- **CONSIDER PARTIAL PROFIT**: Significant gains (>25%), consider taking some profits  
- **REVIEW STOP LOSS**: Significant unrealized loss (>15%), review risk management  
- **CONSIDER REDUCE**: Position >15% of portfolio, high concentration risk  
- **MONITOR CLOSELY**: Negative momentum and negative performance  
""")

            except Exception as e:
                st.error(f"Error fetching chart data: {e}")
