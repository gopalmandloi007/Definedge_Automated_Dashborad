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


3.  login.py

import streamlit as st
import session_utils

def login_page():
    st.subheader("🔐 Secure Login (PIN + OTP)")

    # If already authenticated and session valid, show logout/lock options
    if st.session_state.get("authenticated", False):
        col1, col2 = st.columns(2)
        if col1.button("🔒 Lock"):
            st.session_state["authenticated"] = False
            st.success("App locked. Re-enter PIN to continue.")
            st.stop()
        if col2.button("🚪 Logout"):
            session_utils.logout_session()
            st.success("Logged out. Session cleared.")
            st.stop()
        st.info("Already logged in!")
        st.stop()

    # If a valid previous session exists, offer choice to continue or start new login
    previous_session = session_utils.get_active_session()
    if previous_session and not st.session_state.get("force_new_login", False):
        st.success("Previous session is active.")
        col1, col2 = st.columns(2)
        if col1.button("Continue with Previous Session"):
            st.session_state["integrate_session"] = previous_session
            st.session_state["authenticated"] = True
            st.success("Continued with previous session.")
            st.stop()
        if col2.button("Start New Login (Logout & Re-Login with PIN and OTP)"):
            session_utils.logout_session()
            st.session_state["force_new_login"] = True
            st.experimental_rerun()
            return
        st.stop()

    # Clear force_new_login flag after use
    if st.session_state.get("force_new_login", False):
        st.session_state["force_new_login"] = False

    # PIN entry
    if not st.session_state.get("pin_entered", False):
        pin = st.text_input("Enter your PIN (last 4 digits of your API token):", max_chars=4, type="password")
        if st.button("Submit PIN"):
            if len(pin) == 4 and pin.isalnum():
                st.session_state["user_pin"] = pin
                st.session_state["pin_entered"] = True
                st.experimental_rerun()
                return
            else:
                st.error("Invalid PIN. Please enter exactly 4 alphanumeric characters.")
        st.stop()

    # If PIN entered, try to restore session or start login flow
    io = session_utils.get_active_io(force_new_login=False)
    if io:
        if not st.session_state.get("authenticated", False):
            st.session_state["authenticated"] = True
            st.experimental_rerun()
            return
        st.stop()
    else:
        st.stop()
