import streamlit as st
import importlib
from login import login_page
import session_utils

# --- PAGE SETTINGS ---
st.set_page_config(page_title="Gopal Mandloi Dashboard", layout="wide")
st.title("Gopal Mandloi Integrate Autobot (Automated Mode)")

# --- SESSION GATEKEEPER ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    login_page()
    st.stop()

st.success("Session active! All API calls are automated.")

# --- LEGACY PAGES ---
PAGES = {
    "Holdings": "holdings",
    "Holdings Details": "holdings_details",
    "Positions": "positions",
    "Order Book": "orderbook",
    "Orders": "orders",
    "Order Manage": "order_manage",
    "Limits": "limits",
    "Margin": "margin",
    "Quotes": "quotes",
    "GTT order manage": "gtt_order_manage",
    "GTT Order Place": "gtt_oco_place",
    "Square Off": "squareoff",
    "Auto Order (SL & Targets)": "auto_order",
    "Symbol Technical Details": "symbol_technical_details",
    "Batch Symbol Scanner": "definedge_batch_scan",
    "Candlestick Demo": "simple_chart_demo",
    "Websocket Help": "websocket_help",
    # --- NEW TRADEBOT PAGE ---
    "Tradebot": "tradebot",  # <--- Your new bot page
}

# --- DEBUG LOG VIEWER ---
with st.sidebar.expander("Show Debug Log"):
    if st.button("Refresh Debug Log"):
        pass
    try:
        with open("debug.log") as f:
            log_lines = f.readlines()[-50:]
            st.text("".join(log_lines))
    except Exception:
        st.info("Debug log not available yet.")

selected_page = st.sidebar.selectbox("Select Page", list(PAGES.keys()))

# --- SESSION OBJECTS ---
io = session_utils.get_active_io()
st.session_state["integrate_io"] = io

# --- PAGE LOADER ---
try:
    page_module = importlib.import_module(PAGES[selected_page])
    if hasattr(page_module, "app"):
        page_module.app()
    else:
        st.error(
            f"The page `{selected_page}` does not have an app() function.\n\n"
            "Please make sure your page file defines a function called app().\n"
            "Example:\n"
            "def app():\n    # your streamlit code here"
        )
except ModuleNotFoundError as e:
    st.error(f"Module `{PAGES[selected_page]}` not found. Please check your file/module names.\n\nError: {e}")
