import streamlit as st
from utils import integrate_post
import requests
import pandas as pd

@st.cache_data
def load_master_symbols():
    df = pd.read_csv("master.csv", sep="\t", header=None)
    # Handles both 14 and 15 column master files
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
    # Only EQ & BE series, and only NSE/BSE stocks (not derivatives, indices)
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    df = df.drop_duplicates(subset=["symbol", "series", "segment"])
    df["tradingsymbol"] = df["symbol"] + "-" + df["series"]
    return df.sort_values("tradingsymbol")

def get_ltp(tradingsymbol, exchange, api_session_key):
    try:
        url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exchange}/{tradingsymbol}"
        headers = {"Authorization": api_session_key}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            return float(resp.json().get("ltp", 0))
    except Exception:
        pass
    return 0

def app():
    st.markdown("""
    <style>
    .stApp { width: 100vw; max-width: 100vw; margin: 0; padding: 0; }
    .order-box {
        background: #f8fafd;
        border-radius: 10px;
        box-shadow: 0 2px 6px #e0e8f0;
        padding: 22px 28px 10px 28px;
        margin: 0 0 16px 0;
    }
    .order-summary {
        background: #e6f3ff;
        border-radius: 7px;
        padding: 12px 16px;
        font-size: 1.01rem;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="order-box">', unsafe_allow_html=True)
    st.header("Order Place", divider="rainbow")

    # Load symbols for dropdown (EQ/BE)
    master_df = load_master_symbols()
    symbol_list = master_df["tradingsymbol"].unique().tolist()
    symbol_default = "RELIANCE-EQ" if "RELIANCE-EQ" in symbol_list else symbol_list[0] if symbol_list else ""

    col1, col2, col3, col4 = st.columns([2,2,2,2], gap="large")

    with col1:
        tradingsymbol = st.selectbox("Symbol", symbol_list, index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0, key="order_ts")
        # Find the row in master_df corresponding to the selected trading symbol
        selected_row = master_df[master_df["tradingsymbol"] == tradingsymbol].iloc[0]
        exchange_options = [selected_row["segment"]]
        exchange = st.selectbox("Exch", exchange_options, index=0, key="order_exch")
        price_type = st.selectbox("Type", ["LIMIT", "MARKET", "SL-LIMIT", "SL-MARKET"], key="order_pt")

    with col2:
        validity = st.selectbox("Validity", ["DAY", "IOC", "EOS"], key="order_val")
        order_type = st.selectbox("Side", ["BUY", "SELL"], key="order_ot")
        product_type = st.selectbox("Product", ["CNC", "INTRADAY", "NORMAL"], key="order_prod")

    with col3:
        qty_or_amt = st.radio("Order By", ["Qty", "Amt"], horizontal=True, key="order_qty_or_amt")

    with col4:
        remarks = st.text_input("Remarks (optional)", key="order_rem")

    api_session_key = st.secrets.get("integrate_api_session_key", "")

    ltp = 0.0
    if tradingsymbol and exchange:
        ltp = get_ltp(tradingsymbol, exchange, api_session_key)

    price = st.number_input("Price", min_value=0.0, value=ltp if ltp > 0 else 0.0, step=0.05, key="order_pr", format="%.2f")

    colQ, colA, colT, colD, colAMO = st.columns([2,2,2,2,2], gap="large")

    if qty_or_amt == "Amt":
        with colA:
            amount = st.number_input("₹ Amt", min_value=0.0, step=100.0, key="order_amt", format="%.2f")
        with colQ:
            qty_auto = int(amount // price) if (price > 0 and amount > 0) else 1
            st.caption(f"Auto-Qty at Price ₹{price:.2f}: {qty_auto}" if price > 0 and amount > 0 else "Auto-Qty: 1")
            qty = st.number_input("Qty", min_value=1, value=qty_auto, step=1, key=f"order_qty_{amount}_{price}")
    else:
        with colQ:
            qty = st.number_input("Qty", min_value=1, value=1, step=1, key="order_qty")
        with colA:
            if ltp > 0:
                st.caption(f"LTP: ₹{ltp:.2f}")
            amount = qty * price if price > 0 else 0.0

    with colT:
        trigger_price = st.number_input("Trig Price", min_value=0.0, value=0.0, step=0.05, key="order_tr_pr", format="%.2f")
    with colD:
        disclosed_quantity = st.number_input("Disc Qty", min_value=0, value=0, step=1, key="order_dis_qty")
    with colAMO:
        amo = st.checkbox("AMO?", key="order_amo")

    st.markdown('</div>', unsafe_allow_html=True)

    # Preview summary
    if tradingsymbol and qty and order_type and price_type:
        st.markdown('<div class="order-summary">', unsafe_allow_html=True)
        st.markdown(
            f"<b>Preview:</b> {order_type} {qty} x <b>{tradingsymbol}</b> @ ₹{price} ({price_type}, {product_type})<br>"
            f"Exch: {exchange} | Validity: {validity} | AMO: {'Yes' if amo else 'No'}<br>"
            f"Order By: <b>{qty_or_amt}</b> | ₹ Amt: <b>{amount:.2f}</b>",
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Place Order", use_container_width=True, type="primary", key="order_place_btn"):
        # --- FIX: Set price_type & trigger_price logic for correct order ---
        data = {
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "order_type": order_type,
            "quantity": int(qty),
            "product_type": product_type,
            "validity": validity
        }
        # Apply correct fields for order type
        if price_type == "MARKET":
            data["price_type"] = "MARKET"
            data["price"] = 0.0
        elif price_type == "LIMIT":
            data["price_type"] = "LIMIT"
            data["price"] = float(price)
        elif price_type == "SL-LIMIT":
            data["price_type"] = "SL-LIMIT"
            data["price"] = float(price)
            data["trigger_price"] = float(trigger_price)
        elif price_type == "SL-MARKET":
            data["price_type"] = "SL-MARKET"
            data["price"] = 0.0
            data["trigger_price"] = float(trigger_price)
        # Add optional fields
        if remarks:
            data["remarks"] = remarks
        if disclosed_quantity:
            data["disclosed_quantity"] = int(disclosed_quantity)
        if amo:
            data["amo"] = "Yes"

        resp = integrate_post("/placeorder", data)
        st.success("Order submitted!")
        st.json(resp)

# Only ONE app() call — let the main Streamlit runner handle this
