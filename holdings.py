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
        return None  # gracefully handle chart API error
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
    # Fallback to 0 if API fails/401
    return 0.0

def get_prev_close(exchange, token, api_session_key):
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
    try:
        position_size = (row['Current'] / portfolio_value) * 100 if portfolio_value else 0
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
    except Exception:
        pass
    return insights

def minervini_sell_signals(df, lookback_days=15):
    if df is None or len(df) < lookback_days:
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

def app():
    st.header("📊 Holdings Intelligence Dashboard")
    st.caption("Actionable insights for portfolio decisions - Hold, Add, Reduce, or Exit")

    try:
        data = integrate_get("/holdings")
        holdings = data.get("data", [])
        if not holdings:
            st.info("No holdings found.")
            return
        active_holdings = []
        for h in holdings:
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
            tsym = h.get("tradingsymbol", "N/A")
            avg_buy = safe_float(h.get("avg_buy_price", 0))
            qty = safe_float(h.get("dp_qty", 0))
            invested = avg_buy * qty
            ltp = 0.0  # fallback 0, since API fails
            prev_close = 0.0
            current = ltp * qty
            today_pnl = 0.0
            overall_pnl = current - invested
            pct_chg = 0.0
            pct_chg_avg = ((ltp - avg_buy) / avg_buy * 100) if avg_buy else -100
            realized_pnl = 0.0
            total_today_pnl += today_pnl
            total_overall_pnl += overall_pnl
            total_invested += invested
            total_current += current
            rows.append([
                tsym,
                ltp,
                avg_buy,
                int(qty),
                prev_close,
                pct_chg,
                today_pnl,
                overall_pnl,
                realized_pnl,
                pct_chg_avg,
                invested,
                current,
                h.get("exchange", "NSE"),
                h.get("isin", ""),
            ])
            symbol_segment_dict[tsym] = h.get("exchange", "NSE")
        headers = [
            "Symbol", "LTP", "Avg Buy", "Qty", "P.Close", "%Chg", "Today P&L", "Overall P&L",
            "Realized P&L", "%Chg Avg", "Invested", "Current", "Exchange", "ISIN"
        ]
        df = pd.DataFrame(rows, columns=headers)
        for col in ["LTP", "Avg Buy", "P.Close", "%Chg", "Today P&L", "Overall P&L", "Realized P&L", "%Chg Avg", "Invested", "Current"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        portfolio_value = df['Current'].sum()
        df['Portfolio %'] = (df['Current'] / portfolio_value * 100).round(2) if portfolio_value else 0
        df['Action'] = "HOLD"
        df.loc[df['%Chg Avg'] == -100, 'Action'] = "REVIEW STOP LOSS"  # fallback
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
        st.dataframe(
            df[["Symbol", "LTP", "Avg Buy", "%Chg", "%Chg Avg", "Today P&L", "Overall P&L", "Portfolio %", "Action"]],
            use_container_width=True,
            hide_index=True
        )

        st.info("LTP, P&L, technicals unavailable due to price API error. Table is fallback mode.")
        # The rest of the code (charts, technicals, etc) can be enabled if live price API is available.
    except Exception as e:
        st.error(f"Error loading holdings: {e}")

if __name__ == "__main__":
    app()
