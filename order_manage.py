import streamlit as st
import requests
from debug_utils import debug_log

def cancel_order(order_id):
    # Get secrets (make sure your .streamlit/secrets.toml contains these keys)
    api_session_key = st.secrets.get("integrate_api_session_key", "")
    uid = st.secrets.get("uid", "")
    actid = st.secrets.get("actid", "")

    url = f"https://integrate.definedgesecurities.com/dart/v1/cancel/{order_id}"
    headers = {
        "Authorization": api_session_key,
        "actid": actid,
        "uid": uid
    }

    debug_log(f"Cancel API Request: {url} | HEADERS: {headers}", print_console=True)
    # Use POST for most APIs. If your broker requires GET, replace with requests.get
    resp = requests.post(url, headers=headers)
    debug_log(f"Cancel API Response [{order_id}]: {resp.status_code} | {resp.text}", print_console=True)

    try:
        result = resp.json()
    except Exception:
        debug_log(f"Cancel API JSON decode failed for [{order_id}]: {resp.text}", print_console=True)
        result = {"status": "ERROR", "message": "Invalid API response"}
    return result

def app():
    st.header("Order Management")

    # Simulate fetching orders (replace this with your real API call)
    orders = [
        {"order_id": "25082300000077", "tradingsymbol": "RELIANCE-EQ", "order_status": "OPEN"},
        # Add more orders here...
    ]

    # Show all orders in a table
    for order in orders:
        st.write(f"Order ID: {order['order_id']} | Symbol: {order['tradingsymbol']} | Status: {order['order_status']}")
        if st.button(f"Cancel {order['order_id']}", key=f"cancel_btn_{order['order_id']}"):
            result = cancel_order(order['order_id'])
            if result.get("status") == "ERROR":
                st.error(f"Cancel Failed: {result.get('message','Error')}")
            else:
                st.success(f"Order {order['order_id']} cancelled!")
            st.rerun()
