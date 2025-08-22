import streamlit as st
from session_utils import get_active_io

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


st.set_page_config(page_title="Gopal Mandloi_Autobot", layout="wide")
st.title("Gopal Mandloi Integrate Autobot (Automated Mode)")

st.info("This app manages its own login/session lifecycle. No manual session keys needed!")

io = get_active_io()
if io is not None:
    st.success("Session active! All API calls are automated.")
    # Example usage
    with st.expander("Show Holdings"):
        holdings = io.holdings()
        st.write(holdings)
else:
    st.error("Could not start a session. Check your API token/secret in secrets.toml.")
    # The following 'except' blocks should be associated with a 'try' block, 
