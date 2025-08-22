import streamlit as st
import time
from integrate import ConnectToIntegrate, IntegrateOrders

SESSION_KEY_NAME = "integrate_session"

def is_session_valid():
    session = st.session_state.get(SESSION_KEY_NAME)
    if session is None:
        return False
    now = time.time()
    # Valid for 24 hours (86400 seconds)
    return (now - session["created_at"]) < 86400

def get_active_io():
    if is_session_valid():
        sess = st.session_state[SESSION_KEY_NAME]
        conn = ConnectToIntegrate()
        conn.set_session_keys(sess["uid"], sess["actid"], sess["api_session_key"], sess["ws_session_key"])
        io = IntegrateOrders(conn)
        st.session_state["integrate_io"] = io
        return io
    else:
        return login_and_store()

def login_and_store():
    # >>> First check, if session is already valid, do NOT show OTP UI <<<
    if is_session_valid():
        sess = st.session_state[SESSION_KEY_NAME]
        conn = ConnectToIntegrate()
        conn.set_session_keys(sess["uid"], sess["actid"], sess["api_session_key"], sess["ws_session_key"])
        io = IntegrateOrders(conn)
        st.session_state["integrate_io"] = io
        return io

    # Only this code runs if session is NOT valid
    api_token = st.secrets["INTEGRATE_API_TOKEN"]
    api_secret = st.secrets["INTEGRATE_API_SECRET"]
    conn = ConnectToIntegrate()
    step1_resp = conn.login_step1(api_token=api_token, api_secret=api_secret)
    st.info(step1_resp.get("message", "OTP sent to your registered mobile/email."))
    otp = st.text_input("Enter OTP sent to your mobile/email:", type="password")
    # Trick: Only process OTP if button pressed and not before!
    if st.button("Submit OTP"):
        try:
            step2_resp = conn.login_step2(otp)
            st.success("Login successful!")
            uid, actid, api_session_key, ws_session_key = conn.get_session_keys()
            conn.set_session_keys(uid, actid, api_session_key, ws_session_key)
            st.session_state[SESSION_KEY_NAME] = {
                "uid": uid,
                "actid": actid,
                "api_session_key": api_session_key,
                "ws_session_key": ws_session_key,
                "created_at": time.time()
            }
            io = IntegrateOrders(conn)
            st.session_state["integrate_io"] = io
            return io
        except Exception as e:
            st.error(f"Login failed: {e}")
            return None
    # Important: If not submitted OTP, return None! (So rerun doesn't go forward)
    return None
