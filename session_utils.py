import streamlit as st
import time
import json
import os
from integrate import ConnectToIntegrate, IntegrateOrders
from debug_utils import debug_log

SESSION_KEY_NAME = "integrate_session"
SESSION_FILE = "session.json"

def save_session_to_file(session):
    # Only save non-secret keys!
    session_copy = {k: v for k, v in session.items() if k in ["uid", "actid", "api_session_key", "ws_session_key", "created_at"]}
    with open(SESSION_FILE, "w") as f:
        json.dump(session_copy, f)

def load_session_from_file():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            session = json.load(f)
            # Validate structure
            keys = ["uid", "actid", "api_session_key", "ws_session_key", "created_at"]
            if all(k in session for k in keys):
                return session
    return None

def is_session_valid(session=None):
    if session is None:
        session = st.session_state.get(SESSION_KEY_NAME)
    if session is None:
        session = load_session_from_file()
    if session is None:
        return False
    now = time.time()
    # Expiry: 23.5 hours (for broker), can adjust as per broker's session lifetime
    return (now - session["created_at"]) < 84600

def get_active_io():
    # If session is valid, restore it
    if is_session_valid():
        sess = st.session_state.get(SESSION_KEY_NAME) or load_session_from_file()
        debug_log(f"Using saved session: {sess}")
        conn = ConnectToIntegrate()
        conn.set_session_keys(sess["uid"], sess["actid"], sess["api_session_key"], sess["ws_session_key"])
        io = IntegrateOrders(conn)
        st.session_state["integrate_io"] = io
        st.session_state[SESSION_KEY_NAME] = sess
        return io
    else:
        return login_and_store()

def login_and_store():
    # Only prompt OTP if session is not valid
    if is_session_valid():
        sess = st.session_state.get(SESSION_KEY_NAME) or load_session_from_file()
        debug_log("Session still valid, skipping login.")
        conn = ConnectToIntegrate()
        conn.set_session_keys(sess["uid"], sess["actid"], sess["api_session_key"], sess["ws_session_key"])
        io = IntegrateOrders(conn)
        st.session_state["integrate_io"] = io
        st.session_state[SESSION_KEY_NAME] = sess
        return io

    # Secrets should only be in Streamlit secrets, never in code
    api_token = st.secrets["INTEGRATE_API_TOKEN"]
    api_secret = st.secrets["INTEGRATE_API_SECRET"]
    conn = ConnectToIntegrate()
    step1_resp = conn.login_step1(api_token=api_token, api_secret=api_secret)
    debug_log(f"Login Step 1 Response: {step1_resp}")
    st.info(step1_resp.get("message", "OTP sent to your registered mobile/email."))
    otp = st.text_input("Enter OTP sent to your mobile/email:", type="password")
    if st.button("Submit OTP"):
        try:
            step2_resp = conn.login_step2(otp)
            debug_log(f"Login Step 2 Response: {step2_resp}")
            st.success("Login successful!")
            uid, actid, api_session_key, ws_session_key = conn.get_session_keys()
            session = {
                "uid": uid,
                "actid": actid,
                "api_session_key": api_session_key,
                "ws_session_key": ws_session_key,
                "created_at": time.time()
            }
            save_session_to_file(session)
            st.session_state[SESSION_KEY_NAME] = session
            conn.set_session_keys(uid, actid, api_session_key, ws_session_key)
            io = IntegrateOrders(conn)
            st.session_state["integrate_io"] = io
            debug_log("Login successful, session saved.")
            return io
        except Exception as e:
            debug_log(f"Login failed: {e}")
            st.error(f"Login failed: {e}")
            return None
    return None
