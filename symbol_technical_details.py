import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
from datetime import datetime, timedelta

@st.cache_data
def load_master():
    df = pd.read_csv("master.csv", sep="\t", header=None)
    df.columns = [
        "segment", "token", "symbol", "symbol_series", "series", "unknown1",
        "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
        "isin", "unknown7", "company"
    ]
    return df[["segment", "token", "symbol", "symbol_series", "series", "company"]]

def get_token(symbol, segment, series, master_df):
    candidates = master_df[
        (master_df['segment'].str.upper() == segment.upper()) &
        ((master_df['symbol'].str.upper() == symbol.upper()) | (master_df['symbol_series'].str.upper() == symbol.upper()))
    ]
    if not candidates.empty:
        row = candidates[candidates['series'].str.upper() == series.upper()]
        if not row.empty:
            return row.iloc[0]['token']
        return candidates.iloc[0]['token']
    return None

def fetch_candles_definedge(segment, token, timeframe, from_dt, to_dt, api_key):
    url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/{timeframe}/{from_dt}/{to_dt}"
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
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=period, min_periods=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return pd.Series(rsi, index=series.index)

def count_updays(df, window=15):
    highs = df["High"].values
    count = 0
    for i in range(-window, 0):
        if i - 1 < -len(highs):
            continue
        if highs[i] > highs[i-1]:
            count += 1
    return count

def count_downdays(df, window=15):
    lows = df["Low"].values
    count = 0
    for i in range(-window, 0):
        if i - 1 < -len(lows):
            continue
        if lows[i] < lows[i-1]:
            count += 1
    return count

def get_time_range(days, endtime="1530"):
    to = datetime.now()
    to = to.replace(hour=int(endtime[:2]), minute=int(endtime[2:]), second=0, microsecond=0)
    frm = to - timedelta(days=days)
    return frm.strftime("%d%m%Y%H%M"), to.strftime("%d%m%Y%H%M")

def display_metric(label, value):
    st.metric(label, "N/A" if pd.isna(value) else f"{value:.2f}")

def show():
    st.header("Symbol Technical Details")

    api_key = st.secrets.get("integrate_api_session_key", "")
    master_df = load_master()

    # Auto select: Segment, then Symbol, then Series
    col1, col2, col3 = st.columns(3)
    with col1:
        segment_options = sorted(master_df["segment"].str.upper().unique())
        segment = st.selectbox("Segment", segment_options, index=0)
    with col2:
        df_segment = master_df[master_df["segment"].str.upper() == segment]
        df_segment["display_name"] = df_segment.apply(
            lambda r: f"{r['symbol']} ({r['series']})" if pd.notnull(r['series']) else r['symbol'], axis=1
        )
        df_segment = df_segment.drop_duplicates(subset=["symbol", "series"])
        symbol_display_list = df_segment["display_name"].tolist()
        symbol_display = st.selectbox("Symbol", symbol_display_list, index=0)
        selected_row = df_segment[df_segment["display_name"] == symbol_display].iloc[0]
        symbol = selected_row["symbol"]
    with col3:
        possible_series = df_segment[df_segment["symbol"] == symbol]["series"].unique()
        if len(possible_series) == 1:
            series = possible_series[0]
        else:
            series = st.selectbox("Series", possible_series, index=0)
        st.caption("EMAs/RSI are for daily timeframe.")

    token = get_token(symbol, segment, series, master_df)
    if not token:
        st.warning("Symbol-token mapping not found in master file. Try exact symbol or instrument code.")
        return

    try:
        from_dt, to_dt = get_time_range(420)
        daily = fetch_candles_definedge(segment, token, "day", from_dt, to_dt, api_key)
        week_df = daily.copy().set_index("Date").resample("W").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna().reset_index()
        month_df = daily.copy().set_index("Date").resample("M").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna().reset_index()
    except Exception as e:
        st.error(f"Error fetching candles: {e}")
        return

    daily["EMA20"] = compute_ema(daily["Close"], 20)
    daily["EMA50"] = compute_ema(daily["Close"], 50)
    daily["EMA200"] = compute_ema(daily["Close"], 200)
    daily["RSI"] = compute_rsi(daily["Close"], 14)
    week_df["RSI"] = compute_rsi(week_df["Close"], 14)
    month_df["RSI"] = compute_rsi(month_df["Close"], 14)

    ltp = daily["Close"].iloc[-1]
    ema20 = daily["EMA20"].iloc[-1]
    ema50 = daily["EMA50"].iloc[-1]
    ema200 = daily["EMA200"].iloc[-1]
    rsi_daily = daily["RSI"].dropna().iloc[-1] if daily["RSI"].notna().any() else np.nan
    rsi_weekly = week_df["RSI"].dropna().iloc[-1] if week_df["RSI"].notna().any() else np.nan
    rsi_monthly = month_df["RSI"].dropna().iloc[-1] if month_df["RSI"].notna().any() else np.nan

    ema20_ltp = ema20 / ltp if ltp else np.nan
    ema50_ema20 = ema50 / ema20 if ema20 else np.nan
    updays = count_updays(daily, 15)
    downdays = count_downdays(daily, 15)

    colm = st.columns(3)
    with colm[0]:
        display_metric("Monthly RSI", rsi_monthly)
        st.metric("LTP", f"{ltp:.2f}")
        st.metric("20 EMA", f"{ema20:.2f}")
        st.metric("Updays (15d)", updays)
    with colm[1]:
        display_metric("Weekly RSI", rsi_weekly)
        st.metric("50 EMA", f"{ema50:.2f}")
        st.metric("50 EMA / 20 EMA", f"{ema50_ema20:.4f}")
        st.metric("Downdays (15d)", downdays)
    with colm[2]:
        display_metric("Daily RSI", rsi_daily)
        st.metric("200 EMA", f"{ema200:.2f}")
        st.metric("20 EMA / LTP", f"{ema20_ltp:.4f}")

    st.markdown("#### Recent Daily Candles")
    st.dataframe(daily.tail(15)[["Date", "Open", "High", "Low", "Close", "EMA20", "EMA50", "EMA200", "RSI"]])

    st.info("All data is fetched from Definedge Historical Data API using your master file.")

if __name__ == "__main__":
    show()
