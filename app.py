# app.py
import streamlit as st
import importlib
import session_utils
from login import login_page

# --- PAGE SETTINGS ---
st.set_page_config(page_title="Gopal Mandloi Dashboard", layout="wide")
st.title("Gopal Mandloi Integrate Autobot (Automated Mode)")

# --- SESSION GATEKEEPER ---
session = session_utils.get_active_session()
if "authenticated" not in st.session_state or not st.session_state.get("authenticated", False):
    login_page()
    st.stop()

st.success("Session active! All API calls are automated.")

# --- PAGES DICTIONARY ---
PAGES = {
    "Holdings": "holdings",
    "Debug": "debug_utils",
    "Portfolio": "holdings_positions",
    "Holdings Details": "holdings_details",
    "Positions": "positions",
    "Order Book": "orderbook",
    "Orders": "orders",
    "Order Manage": "order_manage",
    "Limits": "limits",
    "Margin": "margin",
    "Quotes": "quotes",
    "GTT Order Manage": "gtt_order_manage",
    "GTT OCO Place": "gtt_oco_place",
    "Square Off": "squareoff",
    "Auto Order (SL & Targets)": "auto_order",
    "Symbol Technical Details": "symbol_technical_details",
    "Batch Symbol Scanner": "definedge_batch_scan",
    "Candlestick Demo": "simple_chart_demo",
    "Tradebot": "tradebot",
    "Historical Manager": "historical_page",
}

# --- PAGE SELECTION ---
selected_page = st.sidebar.selectbox("Select Page", list(PAGES.keys()))

# --- INTEGRATE IO OBJECT ---
try:
    io = session_utils.get_active_io()
    st.session_state["integrate_io"] = io
except Exception as e:
    st.error("Cannot build Integrate IO object: " + str(e))
    st.stop()

# --- HISTORICAL MANAGER PAGE ---
if selected_page == "Historical Manager":
    st.header("Historical Data Manager")
    from masterfile_handler import batch_symbols
    from historical_handler import update_all_from_master

    session_key = session.get("api_session_key")
    seg = st.selectbox("Master Segment", ["NSE_CASH", "NSE_FNO", "ALL"])
    batch_size = st.number_input("Batch size", min_value=50, max_value=1000, value=500, step=50)
    timeframe = st.selectbox("Timeframe", ["day", "minute"])
    start_date = st.text_input("Start date (ddMMyyyy or ddMMyyyyHHMM)", "01012020")

    def run_historical_batch():
        done = 0  # variable for nonlocal

        if st.button("Run update for next batch (from master)"):
            progress_bar = st.progress(0)
            batch_iter = batch_symbols(seg, batch_size)
            try:
                first_batch = next(batch_iter)
            except StopIteration:
                st.info("No symbols found in master. Please download master first.")
                first_batch = []

            if first_batch:
                total = len(first_batch)

                def progress_cb(token, idx, total_local, status, rows):
                    nonlocal done
                    done = idx
                    progress_bar.progress(min(1.0, done/total))
                    st.write(f"{idx}/{total} — token={token} status={status} rows={rows}")

                results = update_all_from_master(
                    session_key,
                    master_segment=seg,
                    batch_size=batch_size,
                    timeframe=timeframe,
                    start_date=start_date,
                    sleep_per=0.06,
                    progress=progress_cb
                )
                st.success("Batch update requested (check logs above).")

    run_historical_batch()

# --- LOAD OTHER PAGES DYNAMICALLY ---
else:
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
