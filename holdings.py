import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from utils import integrate_get
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import numpy as np

# ========== Enhanced Chart Utils ==========
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
    else:  # legacy 14-column
        df.columns = [
            "segment", "token", "symbol", "instrument", "series", "isin1",
            "facevalue", "lot", "something", "zero1", "two1", "one1", "isin", "one2"
        ]
        return df[["segment", "token", "symbol", "instrument", "series"]]

def get_token(symbol, segment, master_df):
    symbol = symbol.strip().upper()
    segment = segment.strip().upper()
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

def compute_relative_strength(stock_df, index_df):
    merged = pd.merge(
        stock_df[["Date", "Close"]],
        index_df[["Date", "Close"]].rename(columns={"Close": "IndexClose"}),
        on="Date",
        how="inner"
    ).dropna()
    if len(merged) < 10:
        return pd.Series(dtype="float64")
    rs_series = merged["Close"] / merged["IndexClose"]
    rs_series.index = merged["Date"]
    return rs_series

def safe_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def get_ltp(exchange, token, api_session_key):
    if not exchange or not token:
        return 0.0
    url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exchange}/{token}"
    headers = {"Authorization": api_session_key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return safe_float(resp.json().get("ltp", 0))
        else:
            return None
    except Exception:
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
    to_str = today.strftime("%d%m%Y1530")
    url = f"https://data.definedgesecurities.com/sds/history/{exchange}/{token}/day/{from_str}/{to_str}"
    headers = {"Authorization": api_session_key}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            rows = resp.text.strip().split("\n")
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

def highlight_pnl(val):
    try:
        val = float(val)
        if val > 0:
            return 'color: green'
        elif val < 0:
            return 'color: red'
    except:
        pass
    return 'color: black'

def generate_insights(row, portfolio_value):
    insights = []
    position_size = (row['Current'] / portfolio_value) * 100
    if position_size > 15:
        insights.append("⚠️ Position too large (>15% of portfolio)")
    elif position_size < 3:
        insights.append("⚖️ Position too small (<3% of portfolio)")
    if row['Overall P&L'] > 0:
        if row['%Chg Avg'] > 25:
            insights.append("💰 Consider taking partial profits (gains >25%)")
    else:
        if row['%Chg Avg'] < -15:
            insights.append("❗ Significant unrealized loss (>15%)")
    if row['%Chg'] > 5:
        insights.append("📈 Strong positive momentum today")
    elif row['%Chg'] < -5:
        insights.append("📉 Strong negative momentum today")
    return insights

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

def show():
    st.header("📊 Holdings Intelligence Dashboard")
    st.caption("Actionable insights for portfolio decisions - Hold, Add, Reduce, or Exit")

    api_session_key = st.secrets.get("integrate_api_session_key", "")
    auto_refresh = st.checkbox("Auto-refresh every 30 seconds", value=False)
    master_df = load_master()

    try:
        data = integrate_get("/holdings")
        holdings = data.get("data", [])
        if not holdings:
            st.info("No holdings found.")
            return
        active_holdings = []
        for h in holdings:
            qty = 0.0
            ts = h.get("tradingsymbol")
            if isinstance(ts, list) and len(ts) > 0 and isinstance(ts[0], dict):
                qty = safe_float(ts[0].get("dp_qty", h.get("dp_qty", 0)))
            else:
                qty = safe_float(h.get("dp_qty", 0))
            if qty > 0:
                active_holdings.append(h)
        rows = []
        total_today_pnl = 0.0
        total_overall_pnl = 0.0
        total_invested = 0.0
        total_current = 0.0
        symbol_segment_dict = {}
        for h in active_holdings:
            ts = h.get("tradingsymbol")
            exch = h.get("exchange", "NSE")
            token = None
            isin = ""
            if isinstance(ts, list) and len(ts) > 0 and isinstance(ts[0], dict):
                tsym = ts[0].get("tradingsymbol", "N/A")
                exch = ts[0].get("exchange", exch)
                token = ts[0].get("token")
                isin = ts[0].get("isin", "")
                qty = safe_float(ts[0].get("dp_qty", h.get("dp_qty", 0)))
            else:
                tsym = ts if isinstance(ts, str) else "N/A"
                token = h.get("token")
                isin = h.get("isin", "")
                qty = safe_float(h.get("dp_qty", 0))
            avg_buy = safe_float(h.get("avg_buy_price", 0))
            ltp = get_ltp(exch, token, api_session_key) if token else None
            prev_close = get_prev_close(exch, token, api_session_key) if token else None
            invested = avg_buy * qty if avg_buy is not None else 0.0
            current = ltp * qty if ltp is not None else 0.0
            today_pnl = (ltp - prev_close) * qty if (ltp is not None and prev_close) else 0.0
            overall_pnl = (ltp - avg_buy) * qty if (ltp is not None and avg_buy) else 0.0
            pct_chg = ((ltp - prev_close) / prev_close * 100) if (ltp is not None and prev_close and prev_close != 0) else 0.0
            pct_chg_avg = ((ltp - avg_buy) / avg_buy * 100) if (ltp is not None and avg_buy and avg_buy != 0) else 0.0
            realized_pnl = 0.0
            total_today_pnl += today_pnl
            total_overall_pnl += overall_pnl
            total_invested += invested
            total_current += current
            rows.append([
                tsym,
                round(ltp, 2) if ltp is not None else "N/A",
                round(avg_buy, 2) if avg_buy is not None else "N/A",
                int(qty),
                round(prev_close, 2) if prev_close is not None else "N/A",
                round(pct_chg, 2) if ltp is not None else "N/A",
                round(today_pnl, 2) if ltp is not None else "N/A",
                round(overall_pnl, 2) if ltp is not None else "N/A",
                round(realized_pnl, 2) if realized_pnl else "",
                round(pct_chg_avg, 2) if ltp is not None else "N/A",
                round(invested, 2) if invested else "N/A",
                round(current, 2) if current else "N/A",
                exch,
                isin,
            ])
            symbol_segment_dict[tsym] = exch
        headers = [
            "Symbol", "LTP", "Avg Buy", "Qty", "P.Close", "%Chg", "Today P&L", "Overall P&L",
            "Realized P&L", "%Chg Avg", "Invested", "Current", "Exchange", "ISIN"
        ]
        df = pd.DataFrame(rows, columns=headers)
        df = df.sort_values("Invested", ascending=False)
        portfolio_value = df['Current'].sum()
        df['Portfolio %'] = (df['Current'] / portfolio_value * 100).round(2)
        df['Action'] = "HOLD"
        df.loc[df['%Chg Avg'] > 25, 'Action'] = "CONSIDER PARTIAL PROFIT"
        df.loc[df['%Chg Avg'] < -15, 'Action'] = "REVIEW STOP LOSS"
        df.loc[df['Portfolio %'] > 15, 'Action'] = "CONSIDER REDUCE"
        df.loc[(df['%Chg'] < -5) & (df['%Chg Avg'] < -10), 'Action'] = "MONITOR CLOSELY"
        df['Insights'] = df.apply(lambda row: generate_insights(row, portfolio_value), axis=1)
        search = st.text_input("🔍 Search Symbol (filter):")
        if search.strip():
            df = df[df['Symbol'].str.contains(search.strip(), case=False, na=False)]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Value", f"₹{portfolio_value:,.0f}")
        col2.metric("Total P&L", f"₹{total_overall_pnl:,.0f}", 
                   f"{total_overall_pnl/total_invested*100:.1f}%" if total_invested else "0%")
        col3.metric("Today's P&L", f"₹{total_today_pnl:,.0f}")
        col4.metric("Holdings", len(df))
        col1, col2 = st.columns(2)
        with col1:
            fig = go.Figure(
                data=[go.Pie(labels=df["Symbol"], values=df["Current"], hole=0.3, name="Portfolio Allocation")],
                layout=go.Layout(title="Portfolio Allocation")
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            risk_df = df.copy()
            risk_df['Risk Score'] = np.where(
                risk_df['%Chg Avg'] < -10, 3, 
                np.where(risk_df['Portfolio %'] > 10, 2, 1)
            )
            fig = go.Figure(
                data=[go.Bar(x=risk_df['Symbol'], y=risk_df['Current'], marker_color=risk_df['Risk Score'],
                             name="Risk Exposure (Size & Performance)")],
                layout=go.Layout(title="Risk Exposure (Size & Performance)")
            )
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("Holdings Analysis")
        def color_action(val):
            if "PROFIT" in val: return 'background-color: #4CAF50; color: white'
            if "REDUCE" in val: return 'background-color: #FF9800'
            if "REVIEW" in val: return 'background-color: #F44336; color: white'
            if "MONITOR" in val: return 'background-color: #FFEB3B'
            return ''
        styled_df = df.style.applymap(highlight_pnl, 
            subset=["Today P&L", "Overall P&L", "%Chg", "%Chg Avg"]
        ).applymap(color_action, subset=["Action"])
        st.dataframe(
            styled_df,
            use_container_width=True,
            column_order=["Symbol", "LTP", "Avg Buy", "%Chg", "%Chg Avg", 
                          "Today P&L", "Overall P&L", "Portfolio %", "Action"]
        )
        # === TECHNICAL ANALYSIS CHART SECTION, FULL WIDTH, NO GAPS, RS ===
        st.subheader("📈 Technical Analysis for Decision Support")
        holding_symbols = list(symbol_segment_dict.keys())
        if holding_symbols:
            col1, col2 = st.columns([1, 2])
            with col1:
                selected_symbol = st.selectbox("Select Holding", sorted(holding_symbols))
                segment = symbol_segment_dict[selected_symbol]
                token = get_token(selected_symbol, segment, master_df)
                st.subheader("Technical Settings")
                show_ema = st.checkbox("Moving Averages", value=True)
                show_rsi = st.checkbox("RSI Indicator", value=True)
                show_macd = st.checkbox("MACD", value=True)
                days_back = st.slider("Days to Show", 30, 365, 90)

                st.markdown("### Relative Strength Settings")
                rs_index_option = st.selectbox(
                    "Relative Strength vs Index",
                    ["Nifty 500", "Nifty 50"],
                    index=0
                )
                # Identify index symbol and series
                index_row = None
                index_symbol = None
                index_series = "IDX"
                for idx, row in master_df.iterrows():
                    sym = row["symbol"].strip().lower()
                    if (rs_index_option == "Nifty 500" and sym == "nifty 500") or \
                       (rs_index_option == "Nifty 50" and sym == "nifty 50"):
                        index_row = row
                        index_symbol = row["symbol"]
                        if "series" in row and pd.notnull(row["series"]):
                            index_series = row["series"]
                        break

                if token:
                    from_dt, to_dt = get_time_range(days_back)
                    try:
                        chart_df = fetch_candles_definedge(segment, token, from_dt, to_dt, api_key=api_session_key)
                        chart_df = chart_df.sort_values("Date")
                        if show_ema:
                            chart_df['EMA20'] = chart_df['Close'].ewm(span=20, adjust=False).mean()
                            chart_df['EMA50'] = chart_df['Close'].ewm(span=50, adjust=False).mean()
                        if show_rsi:
                            chart_df['RSI'] = compute_rsi(chart_df)
                        if show_macd:
                            macd, signal = compute_macd(chart_df)
                            chart_df['MACD'] = macd
                            chart_df['Signal'] = signal

                        # Fetch index candles for RS
                        if index_row is not None:
                            index_token = index_row["token"]
                            index_segment = index_row["segment"]
                            try:
                                index_df = fetch_candles_definedge(index_segment, index_token, from_dt, to_dt, api_key=api_session_key)
                            except Exception as e:
                                st.warning(f"Error fetching {rs_index_option} candles: {e}")
                                index_df = None
                        else:
                            index_df = None

                        # Compute RS
                        if index_df is not None and not index_df.empty:
                            rs_series = compute_relative_strength(chart_df, index_df)
                        else:
                            rs_series = None

                        # --- Plotly Chart with NO GAPS and RS subplot ---
                        nrows = 1
                        row_heights = [0.7]
                        specs = [[{"secondary_y": True}]]
                        row_map = {"candle": 1}
                        if show_rsi:
                            nrows += 1
                            row_heights.append(0.15)
                            specs.append([{}])
                            row_map["rsi"] = nrows
                        if show_macd:
                            nrows += 1
                            row_heights.append(0.15)
                            specs.append([{}])
                            row_map["macd"] = nrows
                        if rs_series is not None and not rs_series.empty:
                            nrows += 1
                            row_heights.append(0.15)
                            specs.append([{}])
                            row_map["rs"] = nrows

                        fig = make_subplots(
                            rows=nrows,
                            cols=1,
                            shared_xaxes=True,
                            vertical_spacing=0.04,
                            row_heights=row_heights,
                            specs=specs,
                        )

                        # Candle chart (no gaps)
                        fig.add_trace(
                            go.Candlestick(
                                x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                open=chart_df["Open"],
                                high=chart_df["High"],
                                low=chart_df["Low"],
                                close=chart_df["Close"],
                                name="Price"
                            ),
                            row=row_map["candle"], col=1
                        )
                        if show_ema:
                            fig.add_trace(
                                go.Scatter(
                                    x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                    y=chart_df["EMA20"],
                                    mode="lines",
                                    name="20 EMA",
                                    line=dict(color="blue", width=1.5)
                                ),
                                row=row_map["candle"], col=1
                            )
                            fig.add_trace(
                                go.Scatter(
                                    x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                    y=chart_df["EMA50"],
                                    mode="lines",
                                    name="50 EMA",
                                    line=dict(color="orange", width=1.5)
                                ),
                                row=row_map["candle"], col=1
                            )
                        # RSI panel
                        if show_rsi:
                            fig.add_trace(
                                go.Scatter(
                                    x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                    y=chart_df["RSI"],
                                    mode="lines",
                                    name="RSI",
                                    line=dict(color="purple", width=1.5)
                                ),
                                row=row_map["rsi"], col=1
                            )
                            fig.add_hline(y=30, line_dash="dash", line_color="green",
                                          row=row_map["rsi"], col=1)
                            fig.add_hline(y=70, line_dash="dash", line_color="red",
                                          row=row_map["rsi"], col=1)
                        # MACD panel
                        if show_macd:
                            fig.add_trace(
                                go.Bar(
                                    x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                    y=chart_df["MACD"],
                                    name="MACD",
                                    marker_color=np.where(chart_df['MACD'] > 0, 'green', 'red')
                                ),
                                row=row_map["macd"], col=1
                            )
                            fig.add_trace(
                                go.Scatter(
                                    x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
                                    y=chart_df["Signal"],
                                    mode="lines",
                                    name="Signal",
                                    line=dict(color="blue", width=1.5)
                                ),
                                row=row_map["macd"], col=1
                            )
                        # RS panel
                        if rs_series is not None and not rs_series.empty:
                            fig.add_trace(
                                go.Scatter(
                                    x=rs_series.index.strftime("%Y-%m-%d"),
                                    y=rs_series,
                                    mode="lines",
                                    name=f"RS vs {rs_index_option}",
                                    line=dict(color="black", width=1.5)
                                ),
                                row=row_map["rs"], col=1
                            )

                        # Remove gaps for all rows
                        for i in range(1, nrows+1):
                            fig.update_xaxes(type="category", row=i, col=1)

                        fig.update_layout(
                            height=180*nrows+300,
                            title=f"{selected_symbol} Technical Analysis",
                            showlegend=True,
                            xaxis_rangeslider_visible=False,
                            margin=dict(l=10, r=10, t=30, b=10),
                        )

                        st.plotly_chart(fig, use_container_width=True)

                        last_row = chart_df.iloc[-1]
                        insights = []
                        if show_ema:
                            if 'EMA20' in chart_df.columns and 'EMA50' in chart_df.columns:
                                if last_row['Close'] > last_row['EMA20'] > last_row['EMA50']:
                                    insights.append("✅ Bullish trend (Price > 20EMA > 50EMA)")
                                elif last_row['Close'] < last_row['EMA20'] < last_row['EMA50']:
                                    insights.append("❌ Bearish trend (Price < 20EMA < 50EMA)")
                        if show_rsi and 'RSI' in chart_df.columns:
                            if last_row['RSI'] > 70:
                                insights.append("⚠️ Overbought (RSI > 70)")
                            elif last_row['RSI'] < 30:
                                insights.append("⚠️ Oversold (RSI < 30)")
                        if show_macd and 'MACD' in chart_df.columns and 'Signal' in chart_df.columns:
                            if last_row['MACD'] > last_row['Signal']:
                                insights.append("↑ Bullish MACD crossover")
                            else:
                                insights.append("↓ Bearish MACD crossover")
                        if insights:
                            st.subheader("Technical Insights")
                            for insight in insights:
                                st.info(insight)
                        st.subheader("🔔 Minervini Sell Signals Analysis")
                        minervini_lookback = st.slider("Analysis Lookback (days)", 7, 30, 15, key="minervini_lookback")
                        try:
                            signals = minervini_sell_signals(chart_df, minervini_lookback)
                            if signals.get('error'):
                                st.warning(signals['error'])
                            else:
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Up Days", f"{signals['up_days']}/{minervini_lookback}")
                                col2.metric("Up Day %", f"{signals['up_day_percent']:.1f}%")
                                col3.metric("Largest Up Day", f"{signals['largest_up_day']:.2f}%")
                                col4, col5, col6 = st.columns(3)
                                col4.metric("Largest Spread", f"₹{signals['largest_spread']:.2f}")
                                col5.metric("Exhaustion Gap", "Yes" if signals['exhaustion_gap'] else "No")
                                col6.metric("Volume Reversal", "Yes" if signals['high_volume_reversal'] else "No")
                                if signals['warnings']:
                                    st.error("## Sell Signals Detected")
                                    for warning in signals['warnings']:
                                        st.error(warning)
                                    st.markdown("""
                                    ### Minervini's Sell Recommendations:
                                    - **Sell into strength** when these signals appear
                                    - Consider **partial profits** on large gains
                                    - **Exit completely** if multiple signals confirm
                                    """)
                                else:
                                    st.success("No strong sell signals detected")
                                    st.info("""
                                    ### Minervini's Strength Indicators:
                                    - Stock is showing healthy price action
                                    - Continue monitoring for sell signals
                                    - Consider holding until signals appear
                                    """)
                                with st.expander("View Recent Price Action"):
                                    recent = chart_df.tail(minervini_lookback).copy()
                                    recent['Change'] = recent['Close'].pct_change() * 100
                                    recent['Spread'] = recent['High'] - recent['Low']
                                    st.dataframe(recent[['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Change', 'Spread']])
                        except Exception as e:
                            st.error(f"Error in Minervini analysis: {e}")
                    except Exception as e:
                        st.error(f"Error fetching chart data: {e}")
                else:
                    st.warning("Token not found for selected symbol")
        st.subheader("📋 Position Management Guide")
        st.write("""
        - **HOLD**: Fundamentals intact, technicals neutral/positive  
        - **CONSIDER PARTIAL PROFIT**: Significant gains (>25%), consider taking some profits  
        - **REVIEW STOP LOSS**: Significant unrealized loss (>15%), review risk management  
        - **CONSIDER REDUCE**: Position >15% of portfolio, high concentration risk  
        - **MONITOR CLOSELY**: Negative momentum and negative performance  
        """)
    except Exception as e:
        st.error(f"Error loading holdings: {e}")

if __name__ == "__main__":
    show()
