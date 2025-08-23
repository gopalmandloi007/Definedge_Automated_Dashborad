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
