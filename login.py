import streamlit as st
import session_utils

def login_page():
    st.subheader("Login Required")

    api_token = st.text_input("API Token")
    api_secret = st.text_input("API Secret")
    otp = st.text_input("OTP", type="password")

    if st.button("Login"):
        conn = session_utils.get_active_io()
        try:
            # Step 1
            resp1 = conn.login_step1(api_token, api_secret)
            st.info(f"OTP Token received: {resp1.get('otp_token')}")
            
            # Step 2
            resp2 = conn.login_step2(otp)
            session_utils.save_session(conn)

            st.session_state["authenticated"] = True
            st.success("Login successful! Session saved.")
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {e}")
