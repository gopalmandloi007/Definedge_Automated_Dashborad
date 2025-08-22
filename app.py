import streamlit as st
import importlib

# Set page config ONCE at the top
st.set_page_config(page_title="Gopal Mandloi_Dashboard", layout="wide")

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
    "GTT order manage": "gtt",
    "GTT Order Place": "gtt_oco_manage",
    "Square Off": "squareoff",
    "Auto Order (SL & Targets)": "auto_order",
    "Symbol Technical Details": "symbol_technical_details",
    "Batch Symbol Scanner": "definedge_batch_scan",
    "Candlestick Demo": "simple_chart_demo",
    "Websocket Help": "websocket_help",
}

st.title("Gopal Mandloi Integrate Dashboard")

page = st.sidebar.radio("Go to", list(PAGES.keys()))
modulename = PAGES[page]

try:
    module = importlib.import_module(modulename)
    if hasattr(module, "show") and callable(getattr(module, "show")):
        module.show()
    else:
        st.error(f"Module `{modulename}` is missing a callable `show()` function.")
except ModuleNotFoundError:
    st.error(f"Module `{modulename}.py` not found.")
except Exception as e:
    st.error(f"Error loading `{modulename}`: {e}")
