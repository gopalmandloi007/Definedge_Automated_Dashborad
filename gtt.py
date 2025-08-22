import streamlit as st
from utils import integrate_get, integrate_post
import requests
from watchlist_loader import load_watchlist

WATCHLIST_DF = load_watchlist("master.csv")

def get_symbol_from_token(token):
    row = WATCHLIST_DF[WATCHLIST_DF['token'] == str(token)]
    if not row.empty:
        return row.iloc[0]['symbol']
    return ""

def gtt_modify_form(order):
    unique_id = f"gtt_{order.get('alert_id', '')}"
    symbol = order.get('tradingsymbol', '')
    if not symbol:
        symbol = get_symbol_from_token(order.get('token', ''))
    st.markdown("---")
    st.subheader(f"Modify: {symbol} ({order.get('alert_id', '')})")
    # ... rest of your function unchanged ...

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
            symbol = order.get('tradingsymbol', '')
            if not symbol:
                symbol = get_symbol_from_token(order.get('token', ''))
            cols[0].write(symbol)
            # ...rest unchanged...
            # modify/cancel logic unchanged...
            if gtt_mod_id == order.get('alert_id', ''):
                gtt_modify_form(order)
    else:
        st.info("No pending GTT/OCO orders.")

def app():
    show()
