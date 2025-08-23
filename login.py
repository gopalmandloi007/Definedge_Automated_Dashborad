import streamlit as st
import session_utils
import time

OTP_VALIDITY_SECONDS = 300  # 5 minutes

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

    # OTP Management
    otp_sent_time = st.session_state.get("otp_sent_time")
    otp_token = st.session_state.get("otp_token")
    otp_expired = False
    now = time.time()

    # If PIN entered, check if OTP was already sent and is still valid
    if otp_token and otp_sent_time:
        if now - otp_sent_time > OTP_VALIDITY_SECONDS:
            otp_expired = True
            st.session_state["otp_token"] = None
            st.session_state["otp_sent_time"] = None
            st.warning("OTP expired. Please request a new OTP.")
        else:
            time_left = int(OTP_VALIDITY_SECONDS - (now - otp_sent_time))
            st.info(f"An OTP has been sent. Please enter it below. (Valid for {time_left} seconds)")
    else:
        otp_expired = True

    # Regenerate OTP button
    if st.button("Regenerate OTP") or otp_expired:
        # Only send if expired or user requests
        otp_response = session_utils.send_otp_request(pin=st.session_state.get("user_pin", ""))
        if otp_response and otp_response.get("otp_token"):
            st.session_state["otp_token"] = otp_response["otp_token"]
            st.session_state["otp_sent_time"] = time.time()
            st.success("OTP sent to your mobile/email. Please enter it below.")
        else:
            st.error("Failed to send OTP. Please check your PIN or try again.")
        st.stop()

    # OTP entry
    otp_token = st.session_state.get("otp_token")
    if otp_token:
        otp_input = st.text_input("Enter OTP:", max_chars=6, type="password")
        if st.button("Submit OTP"):
            # Validate OTP using your session_utils
            is_valid = session_utils.verify_otp(otp_token, otp_input)
            if is_valid:
                st.session_state["authenticated"] = True
                st.success("Logged in successfully!")
                st.stop()
            else:
                st.error("Invalid OTP. Please try again or regenerate OTP.")
        st.stop()
    else:
        st.warning("Please click 'Regenerate OTP' to get a new OTP.")
