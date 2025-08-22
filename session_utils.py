import streamlit as st
from integrate import ConnectToIntegrate, IntegrateOrders

def ensure_active_session(conn):
    """Uses session keys from secrets, does NOT login!"""
    uid = st.secrets["INTEGRATE_UID"]
    actid = st.secrets["INTEGRATE_ACTID"]
    api_session_key = st.secrets["INTEGRATE_API_SESSION_KEY"]
    ws_session_key = st.secrets["INTEGRATE_WS_SESSION_KEY"]
    conn.set_session_keys(uid, actid, api_session_key, ws_session_key)
    io = IntegrateOrders(conn)
    test = io.holdings()
    if (
        isinstance(test, dict)
        and str(test.get("status", "")).upper() in ["FAILED", "FAIL", "ERROR"]
        and "session" in str(test.get("message", "")).lower()
    ):
        st.error("Session expired! Please generate a new session key from Colab and paste it in secrets.toml.")
        return None
    return io

def show():
    st.header("Login & Session Key (Manual Mode)")
    try:
        uid = st.secrets["INTEGRATE_UID"]
        actid = st.secrets["INTEGRATE_ACTID"]
        api_session_key = st.secrets["INTEGRATE_API_SESSION_KEY"]
        ws_session_key = st.secrets["INTEGRATE_WS_SESSION_KEY"]
    except Exception as e:
        st.error("Missing session keys in secrets.toml: " + str(e))
        return

    conn = ConnectToIntegrate()
    io = ensure_active_session(conn)
    if io is None:
        st.warning("Session expired. Generate new keys from Colab and update secrets.toml.")
    else:
        st.success("Session active!")
        st.info(f"Current session key: {api_session_key[:8]}... (hidden for security)")
        st.caption(f"Actid: {actid}")
