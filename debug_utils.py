import streamlit as st
import pandas as pd
from utils import get_session_headers, integrate_get
from debug_log import debug_log

def app():
    st.header("🛠️ Advanced Debug Page")

    st.subheader("Session State Dump")
    st.json({k: v for k, v in st.session_state.items() if not k.startswith('_')})

    st.subheader("Session Headers")
    headers = get_session_headers()
    st.write(headers)

    st.subheader("Current Integrate Session Object")
    session = st.session_state.get("integrate_session", None)
    st.write(session)

    st.subheader("API Key Debug")
    st.write("Authorization (API key):", headers.get("Authorization"))

    st.divider()

    st.subheader("Live Holdings API Call")
    if headers.get("Authorization"):
        resp = integrate_get("/holdings")
        st.code(resp)
        # Try to show as DataFrame if possible
        holdings = []
        if isinstance(resp, dict):
            for key in ("data", "holdings", "result"):
                if isinstance(resp.get(key), list):
                    holdings = resp[key]
                    break
        if holdings:
            st.dataframe(pd.DataFrame(holdings))
        else:
            st.warning("No holdings data found in API response.")
    else:
        st.error("No API key found in session headers.")

    st.divider()

    st.subheader("Quick API Test")
    api_path = st.text_input("Custom GET API Path (eg. /positions, /orders):", "/positions")
    if st.button("Test API GET"):
        result = integrate_get(api_path)
        st.code(result)

    st.info("If you copy-paste all outputs from this page, any developer can quickly debug your session and API integration!")
