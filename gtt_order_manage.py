import streamlit as st
from utils import integrate_get, integrate_post
import requests

def gtt_modify_form(order):
    unique_id = f"gtt_{order.get('alert_id', '')}"
    st.markdown("---")
    st.subheader(f"Modify: {order.get('tradingsymbol', '')} ({order.get('alert_id', '')})")
    with st.form(f"gtt_mod_form_{unique_id}", clear_on_submit=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            condition = st.radio("Condition", ["LTP_ABOVE", "LTP_BELOW", "LMT_OCO"],
                                 index=["LTP_ABOVE", "LTP_BELOW", "LMT_OCO"].index(order.get('condition', 'LTP_ABOVE')))
            order_type = st.radio("Order Type", ["BUY", "SELL"],
                                  index=0 if order.get('order_type', 'BUY') == "BUY" else 1)
        with col2:
            alert_price = st.number_input("Alert Price", value=float(order.get('alert_price', 0)))
            price = st.number_input("Order Price", value=float(order.get('price', 0)))
        with col3:
            quantity = st.number_input("Quantity", value=int(order.get('quantity', 1)), step=1)
            product_type = st.radio("Product Type", ["CNC", "INTRADAY", "NORMAL"],
                                    index=["CNC", "INTRADAY", "NORMAL"].index(order.get('product_type', 'CNC')))
        with col4:
            remarks = st.text_input("Remarks", value=order.get('remarks', ''))
        c1, c2 = st.columns(2)
        submit_mod = c1.form_submit_button("Confirm Modify")
        cancel_mod = c2.form_submit_button("Cancel Modification")
        if submit_mod:
            payload = {
                "exchange": order.get('exchange', ''),
                "alert_id": order.get('alert_id', ''),
                "tradingsymbol": order.get('tradingsymbol', ''),
                "condition": condition,
                "alert_price": str(alert_price),
                "order_type": order_type,
                "quantity": str(quantity),
                "price": str(price),
                "product_type": product_type
            }
            if remarks:
                payload["remarks"] = remarks
            resp = integrate_post("/gttmodify", payload)
            status = resp.get('status') or resp.get('message') or resp
            if resp.get("status") == "ERROR":
                st.error(f"Modify Failed: {resp.get('message','Error')}")
            else:
                st.success(f"Modify Response: {status}")
            st.session_state["gtt_mod_id"] = None
            st.rerun()
        if cancel_mod:
            st.session_state["gtt_mod_id"] = None
            st.experimental_rerun()

def show():
    st.title("Definedge Integrate Dashboard")
    st.header("GTT / OCO Orders Book & Manage")

    data = integrate_get("/gttorders")
    gttlist = data.get("pendingGTTOrderBook", [])
    gtt_mod_id = st.session_state.get("gtt_mod_id", None)

    st.subheader("GTT & OCO Orders Book")
    if gttlist:
        gtt_labels = ["Symbol", "Type", "Cond", "Alert Price", "Order Price", "Qty", "Product", "Remarks", "Modify", "Cancel"]
        cols = st.columns([1.3, 1.1, 1.1, 1.2, 1.2, 0.8, 0.9, 1.2, 1, 1])
        for i, l in enumerate(gtt_labels):
            cols[i].markdown(f"**{l}**")
        for idx, order in enumerate(gttlist):
            cols = st.columns([1.3, 1.1, 1.1, 1.2, 1.2, 0.8, 0.9, 1.2, 1, 1])
            cols[0].write(order.get('tradingsymbol', ''))
            cols[1].write(order.get('order_type', ''))
            cols[2].write(order.get('condition', ''))
            cols[3].write(order.get('alert_price', ''))
            cols[4].write(order.get('price', ''))
            cols[5].write(order.get('quantity', ''))
            cols[6].write(order.get('product_type', ''))
            cols[7].write(order.get('remarks', ''))
            if cols[8].button("Modify", key=f"gtt_mod_btn_{order.get('alert_id', '')}"):
                st.session_state["gtt_mod_id"] = order.get('alert_id', '')
                st.rerun()
            if cols[9].button("Cancel", key=f"gtt_cancel_btn_{order.get('alert_id', '')}"):
                api_session_key = st.secrets.get("integrate_api_session_key", "")
                url = f"https://integrate.definedgesecurities.com/dart/v1/gttcancel/{order.get('alert_id', '')}"
                headers = {"Authorization": api_session_key}
                resp = requests.get(url, headers=headers)
                try:
                    result = resp.json()
                except Exception:
                    result = {"status": "ERROR", "message": "Invalid API response"}
                if result.get("status") == "ERROR":
                    st.error(f"Cancel Failed: {result.get('message','Error')}")
                else:
                    st.success("Order cancelled!")
                st.rerun()
            if gtt_mod_id == order.get('alert_id', ''):
                gtt_modify_form(order)
    else:
        st.info("No pending GTT/OCO orders.")

# Correct the error: Streamlit expects an app() function for page scripts.
def app():
    show()
