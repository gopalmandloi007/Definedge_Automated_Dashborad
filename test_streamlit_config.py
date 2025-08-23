import streamlit as st

def app():
    st.header("Test Streamlit Config")
    st.write("Streamlit secrets: ", st.secrets)
    st.write("Session state: ", st.session_state)
