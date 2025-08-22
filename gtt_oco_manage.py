import streamlit as st
from utils import integrate_post
from master_loader import load_watchlist

@st.cache_data
def get_master_df():
    df = load_watchlist("master.csv")
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    df["tradingsymbol"] = df["symbol"] + "-" + df["series"]
    df = df.drop_duplicates(subset=["tradingsymbol"])
    return df

def app():
    st.header("Place GTT / OCO Order")

    master_df = get_master_df()
    symbol_list = master_df["tradingsymbol"].tolist()
    symbol_default = "RELIANCE-EQ" if "RELIANCE-EQ" in symbol_list else (symbol_list[0] if symbol_list else "")

    order_type = st.radio("Choose Order Type:", ["Single GTT", "OCO"], horizontal=True)

    if order_type == "Single GTT":
        st.markdown("##### Place Single GTT Order")
        col1, col2, col3 = st.columns(3)
        with col1:
            tradingsymbol = st.selectbox(
                "Trading Symbol", symbol_list,
                index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0,
                key="gtt_tradingsymbol"
            )
            selected_row = master_df[master_df["tradingsymbol"] == tradingsymbol].iloc[0]
            exchange = st.selectbox("Exchange", [selected_row["segment"]], key="gtt_exchange")
        with col2:
            action = st.radio("Action", ["BUY", "SELL"], horizontal=True, key="gtt_action")
            product_type = st.radio("Product Type", ["CNC", "INTRADAY", "NORMAL"], horizontal=True, key="gtt_product_type")
        with col3:
            condition = st.radio("Condition", ["LTP_ABOVE", "LTP_BELOW"], horizontal=True, key="gtt_condition")
            alert_price = st.number_input("Alert Price", min_value=0.0, step=0.05, key="gtt_alert_price")
            order_price = st.number_input("Order Price", min_value=0.0, step=0.05, key="gtt_order_price")
            quantity = st.number_input("Quantity", min_value=1, step=1, key="gtt_quantity")
        remarks = st.text_input("Remarks (optional)", key="gtt_remarks")

        if st.button("Place Single GTT Order"):
            payload = {
                "exchange": exchange,
                "tradingsymbol": tradingsymbol,
                "condition": condition,
                "alert_price": str(alert_price),
                "order_type": action,
                "price": str(order_price),
                "quantity": str(quantity),
                "product_type": product_type
            }
            if remarks:
                payload["remarks"] = remarks
            resp = integrate_post("/gttplaceorder", payload)
            if resp.get("status", "").upper() == "ERROR":
                st.error(f"Failed: {resp.get('message', resp)}")
            else:
                st.success("Single GTT Order submitted!")
                st.json(resp)

    else:  # OCO
        st.markdown("##### Place OCO Order (Target & Stoploss)")
        col1, col2, col3 = st.columns(3)
        with col1:
            tradingsymbol = st.selectbox(
                "Trading Symbol", symbol_list,
                index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0,
                key="oco_tradingsymbol"
            )
            selected_row = master_df[master_df["tradingsymbol"] == tradingsymbol].iloc[0]
            exchange = st.selectbox("Exchange", [selected_row["segment"]], key="oco_exchange")
        with col2:
            action = st.radio("Action", ["BUY", "SELL"], horizontal=True, key="oco_action")
            product_type = st.radio("Product Type", ["CNC", "INTRADAY", "NORMAL"], horizontal=True, key="oco_product_type")
        with col3:
            target_price = st.number_input("Target Price", min_value=0.0, step=0.05, key="oco_target_price")
            stoploss_price = st.number_input("Stoploss Price", min_value=0.0, step=0.05, key="oco_stoploss_price")
            target_qty = st.number_input("Target Quantity", min_value=1, step=1, key="oco_target_qty")
            stoploss_qty = st.number_input("Stoploss Quantity", min_value=1, step=1, key="oco_stoploss_qty")
        remarks = st.text_input("Remarks (optional)", key="oco_remarks")

        if st.button("Place OCO Order"):
            payload = {
                "tradingsymbol": tradingsymbol,
                "exchange": exchange,
                "order_type": action,
                "product_type": product_type,
                "target_price": str(target_price),
                "stoploss_price": str(stoploss_price),
                "target_quantity": int(target_qty),
                "stoploss_quantity": int(stoploss_qty)
            }
            if remarks:
                payload["remarks"] = remarks
            resp = integrate_post("/ocoplaceorder", payload)
            if resp.get("status", "").upper() == "ERROR":
                st.error(f"Failed: {resp.get('message', resp)}")
            else:
                st.success("OCO Order (target/stoploss) submitted!")
                st.json(resp)
