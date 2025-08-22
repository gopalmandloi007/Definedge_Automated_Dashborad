import streamlit as st
from integrate import ConnectToIntegrate, IntegrateOrders

def get_active_io():
    """
    Handles login and session key management automatically.
    If session expires, will re-login and refresh keys.
    """
    if "integrate_io" in st.session_state:
        io = st.session_state["integrate_io"]
        # Check if session is still valid
        test = io.holdings()
        if (
            isinstance(test, dict)
            and str(test.get("status", "")).upper() in ["FAILED", "FAIL", "ERROR"]
            and "session" in str(test.get("message", "")).lower()
        ):
            # Session expired, need to re-login
            io = login_and_store()
    else:
        io = login_and_store()
    return io

def login_and_store():
    api_token = st.secrets["INTEGRATE_API_TOKEN"]
    api_secret = st.secrets["INTEGRATE_API_SECRET"]
    conn = ConnectToIntegrate()
    # Step 1: Request OTP
    step1_resp = conn.login_step1(api_token=api_token, api_secret=api_secret)
    st.info(step1_resp.get("message", "OTP sent to your registered mobile/email."))
    # Step 2: Prompt user for OTP
    otp = st.text_input("Enter OTP sent to your mobile/email:", type="password")
    if st.button("Submit OTP"):
        try:
            step2_resp = conn.login_step2(otp)
            st.success("Login successful!")
            uid, actid, api_session_key, ws_session_key = conn.get_session_keys()
            conn.set_session_keys(uid, actid, api_session_key, ws_session_key)
            io = IntegrateOrders(conn)
            st.session_state["integrate_io"] = io
            return io
        except Exception as e:
            st.error(f"Login failed: {e}")
            return None
    return None
