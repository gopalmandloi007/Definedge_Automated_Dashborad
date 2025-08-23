import streamlit as st
import requests
import time
import json
import os

SESSION_KEY_NAME = "integrate_session"
SESSION_FILE = "session.json"
SESSION_EXPIRY_SECONDS = 84600
OTP_VALIDITY_SECONDS = 300

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
    api_token = get_full_api_token()
    api_secret = st.secrets.get("INTEGRATE_API_SECRET")
    if not api_token or not api_secret:
        st.error("API token or API secret not set. Please check your secrets.toml and PIN.")
        return {}
    payload = {"api_token": api_token, "api_secret": api_secret}
    url = "https://integrate.definedgesecurities.com/dart/v1/login/step1"
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        otp_token = data.get("otp_token")
        if otp_token:
            st.session_state["otp_token"] = otp_token
            st.session_state["otp_sent_time"] = time.time()
        return data
    except Exception as e:
        st.error(f"Failed to send OTP: {e}")
        return {}

def verify_otp(otp_token, otp):
    api_token = get_full_api_token()
    api_secret = st.secrets.get("INTEGRATE_API_SECRET")
    if not api_token or not api_secret:
        st.error("API token or API secret not set. Please check your secrets.toml and PIN.")
        return False
    payload = {"otp_token": otp_token, "otp": otp, "api_token": api_token, "api_secret": api_secret}
    url = "https://integrate.definedgesecurities.com/dart/v1/login/step2"
    try:
        resp = requests.post(url, json=payload, timeout=15)
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
            return True
        else:
            st.error(f"OTP verification failed: {data.get('message', 'Invalid OTP or expired. Please regenerate OTP and try again.')}")
            return False
    except Exception as e:
        st.error(f"OTP verification failed: {e}")
        return False

def otp_expired():
    sent_time = st.session_state.get("otp_sent_time")
    if not sent_time:
        return True
    return (time.time() - sent_time) > OTP_VALIDITY_SECONDS

def login_page():
    st.subheader("🔐 Secure Login (PIN + OTP)")

    # Already authenticated
    if st.session_state.get("authenticated", False):
        col1, col2 = st.columns(2)
        if col1.button("🔒 Lock"):
            st.session_state["authenticated"] = False
            st.success("App locked. Re-enter PIN to continue.")
            st.stop()
        if col2.button("🚪 Logout"):
            logout_session()
            st.success("Logged out. Session cleared.")
            st.stop()
        st.info("Already logged in!")
        st.stop()

    # If previous session valid
    previous_session = get_active_session()
    if previous_session and not st.session_state.get("force_new_login", False):
        st.success("Previous session is active.")
        col1, col2 = st.columns(2)
        if col1.button("Continue with Previous Session"):
            st.session_state["integrate_session"] = previous_session
            st.session_state["authenticated"] = True
            st.success("Continued with previous session.")
            st.stop()
        if col2.button("Start New Login (Logout & Re-Login with PIN and OTP)"):
            logout_session()
            st.session_state["force_new_login"] = True
            st.experimental_rerun()
            return  # <<< RETURN after rerun!
        st.stop()
    if st.session_state.get("force_new_login", False):
        st.session_state["force_new_login"] = False

    # PIN entry (no mask)
    if not st.session_state.get("pin_entered", False):
        pin = st.text_input("Enter your PIN (last 4 digits of your API token):", max_chars=4)
        if st.button("Submit PIN"):
            if len(pin) == 4 and pin.isalnum():
                st.session_state["user_pin"] = pin
                st.session_state["pin_entered"] = True
                st.experimental_rerun()
                return  # <<< RETURN after rerun!
            else:
                st.error("Invalid PIN. Please enter exactly 4 alphanumeric characters.")
        st.stop()

    # OTP Management
    otp_token = st.session_state.get("otp_token")
    otp_sent_time = st.session_state.get("otp_sent_time")
    otp_expired_now = otp_expired()
    now = time.time()

    # Show info if OTP sent and valid
    if otp_token and otp_sent_time and not otp_expired_now:
        time_left = int(OTP_VALIDITY_SECONDS - (now - otp_sent_time))
        st.info(f"An OTP has been sent. Please enter it below. (Valid for {time_left} seconds)")
    else:
        otp_token = None

    # Regenerate OTP button
    if st.button("Regenerate OTP") or not otp_token:
        otp_response = send_otp_request()
        if otp_response and otp_response.get("otp_token"):
            st.success("OTP sent to your mobile/email. Please enter it below.")
        else:
            st.error("Failed to send OTP. Please check your PIN or try again.")
        st.stop()

    # OTP entry
    otp_token = st.session_state.get("otp_token")
    if otp_token:
        otp_input = st.text_input("Enter OTP:", max_chars=6)
        if st.button("Submit OTP"):
            is_valid = verify_otp(otp_token, otp_input)
            if is_valid:
                st.session_state["authenticated"] = True
                st.success("Logged in successfully!")
                st.stop()
            else:
                st.error("Invalid OTP. Please try again or regenerate OTP.")
        st.stop()
    else:
        st.warning("Please click 'Regenerate OTP' to get a new OTP.")
