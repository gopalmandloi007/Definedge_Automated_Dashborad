import requests
import streamlit as st
from debug_utils import debug_log

def cancel_order(order_id):
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
    # If your API needs POST, use this. If it needs GET, change to requests.get
    resp = requests.post(url, headers=headers)
    debug_log(f"Cancel API Response [{order_id}]: {resp.status_code} | {resp.text}", print_console=True)

    try:
        result = resp.json()
    except Exception:
        debug_log(f"Cancel API JSON decode failed for [{order_id}]: {resp.text}", print_console=True)
        result = {"status": "ERROR", "message": "Invalid API response"}
    return result

# Example usage with Streamlit button
def streamlit_cancel_ui(order_id):
    if st.button("Cancel Order"):
        result = cancel_order(order_id)
        if result.get("status") == "ERROR":
            st.error(f"Cancel Failed: {result.get('message','Error')}")
        else:
            st.success("Order cancelled!")
        st.rerun()
