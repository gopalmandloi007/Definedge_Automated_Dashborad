import streamlit as st
from utils import get_integrate_client

def show():
    st.header("Place New Order")
    conn, io = get_integrate_client()

    with st.form("place_order_form"):
        tradingsymbol = st.text_input("Symbol (e.g. SBIN-EQ)", value="HPL-EQ")
        side = st.selectbox("Order Side", ["BUY", "SELL"])
        quantity = st.number_input("Quantity", min_value=1, value=1)
        price_type = st.selectbox("Order Type", ["LIMIT", "MARKET"])
        price = st.number_input("Price", min_value=0.0, value=0.0)
        exchange = st.selectbox("Exchange", ["NSE", "BSE"])
        product_type = st.selectbox("Product Type", ["CNC", "MIS"])
        validity = st.selectbox("Validity", ["DAY", "IOC"])
        submitted = st.form_submit_button("Place Order")
        if submitted:
            try:
                order_kwargs = dict(
                    tradingsymbol=tradingsymbol,
                    exchange=conn.EXCHANGE_TYPE_NSE if exchange == "NSE" else conn.EXCHANGE_TYPE_BSE,
                    order_type=conn.ORDER_TYPE_BUY if side == "BUY" else conn.ORDER_TYPE_SELL,
                    price=price,
                    price_type=conn.PRICE_TYPE_LIMIT if price_type == "LIMIT" else conn.PRICE_TYPE_MARKET,
                    product_type=conn.PRODUCT_TYPE_CNC if product_type == "CNC" else conn.PRODUCT_TYPE_MIS,
                    quantity=int(quantity),
                )
                resp = io.place_order(**order_kwargs)
                st.success(f"Order Placed! Response: {resp}")
            except Exception as e:
                st.error(f"Order Placement Failed: {e}")
