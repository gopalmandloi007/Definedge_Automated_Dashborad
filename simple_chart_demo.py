import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime, timedelta
import plotly.graph_objs as go
import numpy as np

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
        to = now  # In case running before market close
    frm = to - timedelta(days=days)
    return frm.strftime("%d%m%Y%H%M"), to.strftime("%d%m%Y%H%M")

def compute_relative_strength(stock_df, index_df):
    # Align by date, drop NaN, and calculate RS = stock_return / index_return
    merged = pd.merge(
        stock_df[["Date", "Close"]],
        index_df[["Date", "Close"]].rename(columns={"Close": "IndexClose"}),
        on="Date",
        how="inner"
    ).dropna()
    if len(merged) < 10:
        return pd.Series(dtype="float64")
    # Calculate ratio series (stock / index)
    rs_series = merged["Close"] / merged["IndexClose"]
    rs_series.index = merged["Date"]
    return rs_series

def show():
    st.header("Definedge Simple Candlestick Chart Demo (Daily, Live)")

    api_key = st.secrets.get("integrate_api_session_key", "")
    master_df = load_master()

    segment_options = sorted(master_df["segment"].str.upper().unique())
    segment = st.selectbox("Segment", segment_options, index=0)

    df_segment = master_df[master_df["segment"].str.upper() == segment].copy()
    df_segment["display_name"] = df_segment.apply(
        lambda r: f"{r['symbol']} ({r['series']})" if pd.notnull(r['series']) else r['symbol'], axis=1
    )
    df_segment = df_segment.drop_duplicates(subset=["symbol", "series"])
    symbol_display_list = df_segment["display_name"].tolist()
    symbol_idx = 0
    symbol_display = st.selectbox("Symbol", symbol_display_list, index=symbol_idx)

    selected_row = df_segment[df_segment["display_name"] == symbol_display].iloc[0]
    symbol = selected_row["symbol"]
    possible_series = df_segment[df_segment["symbol"] == symbol]["series"].unique()
    if len(possible_series) == 1:
        series = possible_series[0]
    else:
        series = st.selectbox("Series", possible_series, index=0)

    st.write("Selected:", segment, symbol, series)

    col3, col4 = st.columns(2)
    with col3:
        show_ema20 = st.checkbox("Show 20 EMA", value=True)
    with col4:
        show_ema50 = st.checkbox("Show 50 EMA", value=True)

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

    token = get_token(symbol, segment, series, master_df)
    if not token:
        st.error("Symbol-token mapping not found in master file. Try another symbol/series.")
        return

    from_dt, to_dt = get_time_range(120)
    try:
        df = fetch_candles_definedge(segment, token, from_dt, to_dt, api_key)
    except Exception as e:
        st.error(f"Error fetching candles: {e}")
        return

    if df.empty:
        st.warning("No data fetched for this symbol.")
        return

    # Fetch index candles for RS
    if index_row is not None:
        index_token = index_row["token"]
        index_segment = index_row["segment"]
        try:
            index_df = fetch_candles_definedge(index_segment, index_token, from_dt, to_dt, api_key)
        except Exception as e:
            st.warning(f"Error fetching {rs_index_option} candles: {e}")
            index_df = None
    else:
        index_df = None
        st.warning(f"{rs_index_option} not found in master file, RS will not be shown.")

    df = df.sort_values("Date")
    chart_df = df.tail(60).copy()

    if show_ema20:
        chart_df['EMA20'] = chart_df['Close'].ewm(span=20, adjust=False).mean()
    if show_ema50:
        chart_df['EMA50'] = chart_df['Close'].ewm(span=50, adjust=False).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
        open=chart_df["Open"],
        high=chart_df["High"],
        low=chart_df["Low"],
        close=chart_df["Close"],
        name="Candles"
    ))
    if show_ema20:
        fig.add_trace(go.Scatter(
            x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
            y=chart_df["EMA20"],
            mode="lines",
            name="20 EMA",
            line=dict(color="blue", width=1.5)
        ))
    if show_ema50:
        fig.add_trace(go.Scatter(
            x=chart_df["Date"].dt.strftime("%Y-%m-%d"),
            y=chart_df["EMA50"],
            mode="lines",
            name="50 EMA",
            line=dict(color="orange", width=1.5)
        ))

    fig.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        title=f"{symbol} ({series}) Daily Candlestick Chart",
        xaxis=dict(type="category")
    )
    st.plotly_chart(fig, use_container_width=True)

    # RS chart just below candles
    if index_df is not None and not index_df.empty:
        rs_series = compute_relative_strength(df, index_df)
        if not rs_series.empty:
            st.markdown(f"### Relative Strength vs {rs_index_option}")
            rs_fig = go.Figure()
            rs_fig.add_trace(go.Scatter(
                x=rs_series.index.strftime("%Y-%m-%d"),
                y=rs_series,
                mode="lines",
                name="RS"
            ))
            rs_fig.update_layout(
                height=250,
                margin=dict(l=10, r=10, t=30, b=10),
                title=f"Relative Strength: {symbol} / {rs_index_option}",
                xaxis=dict(type="category")
            )
            st.plotly_chart(rs_fig, use_container_width=True)
        else:
            st.info("Not enough data to plot Relative Strength.")
    else:
        st.info("Index data not available for Relative Strength.")

    # Table comes after RS chart
    st.dataframe(chart_df[["Date", "Open", "High", "Low", "Close"]].tail(15))

    st.info("This chart shows daily candles and relative strength vs selected index using Definedge API.")

if __name__ == "__main__":
    show()
