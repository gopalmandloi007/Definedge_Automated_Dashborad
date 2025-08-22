import streamlit as st
import pandas as pd
from utils import integrate_post
from master_loader import load_watchlist

# --- Debug log (optional but recommended)
def debug(message):
    try:
        with open("debug.log", "a") as f:
            from datetime import datetime
            f.write(f"{datetime.now().isoformat()} - {message}\n")
    except Exception as e:
        print(f"DEBUG LOG FAILED: {e} | Original: {message}")

@st.cache_data
def get_master_df():
    df = load_watchlist("master.csv")
    # Only EQ/BE stocks (you can widen filter as needed)
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    df["tradingsymbol"] = df["symbol"] + "-" + df["series"]
    df["token"] = df["token"].astype(str)
    df = df.drop_duplicates(subset=["tradingsymbol"])
    debug(f"Loaded {len(df)} master symbols for dropdown.")
    return df

def app():
    st.header("GTT Order Place (Automatic Symbol Dropdown)")

    master_df = get_master_df()
    symbol_list = master_df["tradingsymbol"].tolist()
    symbol_default = "RELIANCE-EQ" if "RELIANCE-EQ" in symbol_list else (symbol_list[0] if symbol_list else "")

    # --- UI Layout ---
    col1, col2, col3 = st.columns(3)

    with col1:
        tradingsymbol = st.selectbox(
            "Symbol (Auto Dropdown)", symbol_list,
            index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0
        )
        selected_row = master_df[master_df["tradingsymbol"] == tradingsymbol].iloc[0]
        exchange = selected_row["segment"]
        token = selected_row["token"]
        st.text(f"Exchange: {exchange}")
        st.text(f"Token: {token}")

    with col2:
        condition = st.selectbox("Condition", ["LTP_ABOVE", "LTP_BELOW", "LMT_OCO"])
        order_type = st.selectbox("Order Type", ["BUY", "SELL"])
        product_type = st.selectbox("Product Type", ["CNC", "INTRADAY", "NORMAL"])

    with col3:
        alert_price = st.number_input("Alert Price", min_value=0.0, value=0.0, step=0.05, format="%.2f")
        price = st.number_input("Order Price", min_value=0.0, value=0.0, step=0.05, format="%.2f")
        quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
        remarks = st.text_input("Remarks (optional)")

    # --- Submit ---
    if st.button("Place GTT Order", use_container_width=True, type="primary"):
        data = {
            "tradingsymbol": tradingsymbol,
            "token": token,
            "exchange": exchange,
            "condition": condition,
            "alert_price": str(alert_price),
            "order_type": order_type,
            "quantity": str(quantity),
            "price": str(price),
            "product_type": product_type
        }
        if remarks:
            data["remarks"] = remarks
        debug(f"GTT Order Submit: {data}")
        resp = integrate_post("/gttplace", data)
        st.success("GTT Order submitted!")
        st.json(resp)
