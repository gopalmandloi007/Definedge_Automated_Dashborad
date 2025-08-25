# app.py
import streamlit as st
import importlib
import session_utils
from login import login_page

st.set_page_config(page_title="Gopal Mandloi Dashboard", layout="wide")
st.title("Gopal Mandloi Integrate Autobot (Automated Mode)")

# --- SESSION GATEKEEPER ---
session = session_utils.get_active_session()
if "authenticated" not in st.session_state or not st.session_state.get("authenticated", False):
    login_page()
    st.stop()

st.success("Session active! All API calls are automated.")

PAGES = {
    "Holdings": "holdings",              # create file holdings.py if needed
    "Historical Manager": "historical_page",  # we'll provide a Streamlit wrapper below if required
    "Tradebot": "tradebot",              # optional
}

selected_page = st.sidebar.selectbox("Select Page", list(PAGES.keys()))

# Expose IntegrateOrders object
try:
    io = session_utils.get_active_io()
    st.session_state["integrate_io"] = io
except Exception as e:
    st.error("Cannot build Integrate IO object: " + str(e))
    st.stop()

# For this minimal repo we will map "Historical Manager" directly to a small UI below if selected
if selected_page == "Historical Manager":
    st.header("Historical Data Manager")
    from masterfile_handler import batch_symbols
    from historical_handler import update_all_from_master
    session_key = session.get("api_session_key")
    seg = st.selectbox("Master Segment", ["NSE_CASH", "NSE_FNO", "ALL"])
    batch_size = st.number_input("Batch size", min_value=50, max_value=1000, value=500, step=50)
    timeframe = st.selectbox("Timeframe", ["day", "minute"])
    start_date = st.text_input("Start date (ddMMyyyy or ddMMyyyyHHMM)", "01012020")

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
            done = 0

            def progress_cb(token, idx, total_local, status, rows):
                nonlocal_progress = idx   # track inside closure
                progress_bar.progress(min(1.0, nonlocal_progress / total))
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
