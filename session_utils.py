import streamlit as st
import time
import json
import os
from debug_utils import debug_log

SESSION_KEY_NAME = "integrate_session"
SESSION_FILE = "session.json"
SESSION_EXPIRY_SECONDS = 84600  # 23.5 hours
OTP_VALIDITY_SECONDS = 300      # 5 minutes

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
    session = st.session_state.get(SESSION_KEY_NAME)
    if session and is_session_valid(session):
        return session
    session = load_session_from_file()
    if session and is_session_valid(session):
        st.session_state[SESSION_KEY_NAME] = session
        return session
    return None

def logout_session():
    st.session_state.pop("integrate_session", None)
    st.session_state.pop("authenticated", None)
    st.session_state.pop("pin_entered", None)
    st.session_state.pop("user_pin", None)
    st.session_state.pop("otp_token", None)
    st.session_state.pop("otp_sent_time", None)
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass

def send_otp_request():
    """
    Send OTP only on manual request or after expiry. Save OTP token and send time in session_state.
    """
    api_token = get_full_api_token()
    api_secret = st.secrets.get("INTEGRATE_API_SECRET")
    if not api_token or not api_secret:
        st.error("API token or API secret not set. Please check your secrets.toml and PIN.")
        return {}
    payload = {"api_token": api_token, "api_secret": api_secret}
    url = "https://integrate.definedgesecurities.com/dart/v1/login/step1"
    try:
        resp = requests.post(url, json=payload, timeout=15)
        debug_log(f"OTP Send (Login Step 1) Response: {resp.text}")
        data = resp.json()
        otp_token = data.get("otp_token")
        if otp_token:
            st.session_state["otp_token"] = otp_token
            st.session_state["otp_sent_time"] = time.time()
        return data
    except Exception as e:
        debug_log(f"OTP Send failed: {e}")
        st.error(f"Failed to send OTP: {e}")
        return {}

def verify_otp(otp_token, otp):
    """
    Verify OTP using broker API. Returns True if login succeeds, else False.
    """
    api_token = get_full_api_token()
    api_secret = st.secrets.get("INTEGRATE_API_SECRET")
    if not api_token or not api_secret:
        st.error("API token or API secret not set. Please check your secrets.toml and PIN.")
        return False
    payload = {"otp_token": otp_token, "otp": otp, "api_token": api_token, "api_secret": api_secret}
    url = "https://integrate.definedgesecurities.com/dart/v1/login/step2"
    try:
        resp = requests.post(url, json=payload, timeout=15)
        debug_log(f"OTP Verify (Login Step 2) Response: {resp.text}")
        data = resp.json()
        if data.get("stat") == "Ok":
            session = {
                "uid": data.get("uid"),
                "actid": data.get("actid"),
                "api_session_key": data.get("api_session_key"),
                "ws_session_key": data.get("ws_session_key"),
                "created_at": time.time()
            }
            save_session_to_file(session)
            st.session_state[SESSION_KEY_NAME] = session
            st.session_state["authenticated"] = True
            debug_log("Login successful, session saved.")
            return True
        else:
            st.error(f"OTP verification failed: {data.get('message', 'Invalid OTP or expired. Please regenerate OTP and try again.')}")
            return False
    except Exception as e:
        debug_log(f"OTP verification failed: {e}")
        st.error(f"OTP verification failed: {e}")
        return False

def otp_expired():
    sent_time = st.session_state.get("otp_sent_time")
    if not sent_time:
        return True
    return (time.time() - sent_time) > OTP_VALIDITY_SECONDS
