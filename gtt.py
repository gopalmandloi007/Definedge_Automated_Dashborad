import streamlit as st
from utils import integrate_post
import requests
import pandas as pd

@st.cache_data
def load_master_symbols():
    df = pd.read_csv("master.csv", sep="\t", header=None)
    if df.shape[1] == 15:
        df.columns = [
            "segment", "token", "symbol", "symbol_series", "series", "unknown1",
            "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
            "isin", "unknown7", "company"
        ]
        df = df[["symbol", "series", "segment"]]
    else:
        df.columns = [
            "segment", "token", "symbol", "instrument", "series", "isin1",
            "facevalue", "lot", "something", "zero1", "two1", "one1", "isin", "one2"
        ]
        df = df[["symbol", "series", "segment"]]
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    df = df.drop_duplicates(subset=["symbol", "series", "segment"])
    df["tradingsymbol"] = df["symbol"] + "-" + df["series"]
    return df.sort_values("tradingsymbol")

def app():
    st.header("GTT Order Place")
    master_df = load_master_symbols()
    symbol_list = master_df["tradingsymbol"].unique().tolist()
    symbol_default = "RELIANCE-EQ" if "RELIANCE-EQ" in symbol_list else symbol_list[0] if symbol_list else ""

    col1, col2, col3, col4 = st.columns([2,2,2,2], gap="large")

    with col1:
        tradingsymbol = st.selectbox("Symbol", symbol_list, index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0, key="gtt_ts")
        selected_row = master_df[master_df["tradingsymbol"] == tradingsymbol].iloc[0]
        exchange_options = [selected_row["segment"]]
        exchange = st.selectbox("Exch", exchange_options, index=0, key="gtt_exch")
        condition = st.selectbox("Condition", ["LTP_ABOVE", "LTP_BELOW", "LMT_OCO"], key="gtt_cond")
        order_type = st.selectbox("Order Type", ["BUY", "SELL"], key="gtt_ot")

    with col2:
        alert_price = st.number_input("Alert Price", min_value=0.0, value=0.0, step=0.05, key="gtt_alert_pr", format="%.2f")
        price = st.number_input("Order Price", min_value=0.0, value=0.0, step=0.05, key="gtt_order_pr", format="%.2f")
        quantity = st.number_input("Quantity", min_value=1, value=1, step=1, key="gtt_qty")

    with col3:
        product_type = st.selectbox("Product Type", ["CNC", "INTRADAY", "NORMAL"], key="gtt_prod")
        remarks = st.text_input("Remarks (optional)", key="gtt_rem")

    api_session_key = st.secrets.get("integrate_api_session_key", "")

    if st.button("Place GTT Order", use_container_width=True, type="primary", key="gtt_place_btn"):
        data = {
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "condition": condition,
            "alert_price": str(alert_price),
            "order_type": order_type,
            "quantity": str(quantity),
            "price": str(price),
            "product_type": product_type
        }
        if remarks: data["remarks"] = remarks
        resp = integrate_post("/gttplace", data)
        st.success("GTT Order submitted!")
        st.json(resp)
