import streamlit as st
import time
import json
import os
from integrate import ConnectToIntegrate, IntegrateOrders
from debug_utils import debug_log

SESSION_KEY_NAME = "integrate_session"
SESSION_FILE = "session.json"
SESSION_EXPIRY_SECONDS = 84600  # 23.5 hours

def get_full_api_token():
    try:
        partial = st.secrets["INTEGRATE_API_TOKEN"]
    except KeyError:
        st.error("INTEGRATE_API_TOKEN not found in .streamlit/secrets.toml. Please add it with the first 32 characters of your API token.")
        return None
    pin = st.session_state.get("user_pin", "")
    if len(partial) != 32:
        st.error("INTEGRATE_API_TOKEN must be exactly 32 characters.")
        return None
    if len(pin) != 4:
        st.error("PIN must be exactly 4 characters.")
        return None
    return partial + pin

def save_session_to_file(session):
    session_copy = {k: v for k, v in session.items() if k in ["uid", "actid", "api_session_key", "ws_session_key", "created_at"]}
    with open(SESSION_FILE, "w") as f:
        json.dump(session_copy, f)

def load_session_from_file():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            session = json.load(f)
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
    return (now - session["created_at"]) < SESSION_EXPIRY_SECONDS

def get_active_session():
    # Try Streamlit session_state first
    session = st.session_state.get(SESSION_KEY_NAME)
    if session and is_session_valid(session):
        return session
    # Try from file
    session = load_session_from_file()
    if session and is_session_valid(session):
        st.session_state[SESSION_KEY_NAME] = session
        return session
    return None

def get_active_io(force_new_login=False):
    if force_new_login:
        logout_session()
    session = get_active_session()
    if session:
        debug_log(f"Using saved session: {session}")
        conn = ConnectToIntegrate()
        conn.set_session_keys(session["uid"], session["actid"], session["api_session_key"], session["ws_session_key"])
        io = IntegrateOrders(conn)
        st.session_state["integrate_io"] = io
        st.session_state[SESSION_KEY_NAME] = session
        return io

    api_token = get_full_api_token()
    api_secret = st.secrets.get("INTEGRATE_API_SECRET")
    if not api_token or not api_secret:
        st.error("API token or API secret not set. Please check your secrets.toml and PIN.")
        return None

    conn = ConnectToIntegrate()
    try:
        step1_resp = conn.login_step1(api_token=api_token, api_secret=api_secret)
        debug_log(f"Login Step 1 Response: {step1_resp}")
        if not step1_resp or "message" not in step1_resp:
            st.error("Broker API returned an empty or invalid response in Step 1. Please retry.")
            return None
        st.info(step1_resp.get("message", "OTP sent to your registered mobile/email."))
        otp = st.text_input("Enter OTP sent to your mobile/email:", type="password")
        if st.button("Submit OTP"):
            try:
                step2_resp = conn.login_step2(otp)
                debug_log(f"Login Step 2 Response: {step2_resp}")
                if not step2_resp:
                    st.error("Broker API returned an empty or invalid response in Step 2. Please retry.")
                    return None
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
                st.session_state["authenticated"] = True
                debug_log("Login successful, session saved.")
                st.success("Login successful! You may now use the dashboard.")
                st.stop()
                return io
            except ValueError as e:
                debug_log(f"Login failed: {e}")
                st.error("Broker API returned an empty or invalid response. Possible causes:\n- OTP already used/expired\n- Network/server error\n- Wrong secrets")
                return None
            except Exception as e:
                debug_log(f"Login failed: {e}")
                st.error(f"Login failed: {e}")
                return None
        return None
    except Exception as e:
        debug_log(f"Login step 1 failed: {e}")
        st.error(f"Login failed: {e}")
        return None

def logout_session():
    st.session_state.pop("integrate_session", None)
    st.session_state.pop("integrate_io", None)
    st.session_state.pop("user_pin", None)
    st.session_state.pop("authenticated", None)
    st.session_state.pop("pin_entered", None)
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass
