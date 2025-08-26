import streamlit as st

def app():
    st.header("Debug Page")
    st.write("This is the debug page!")
    # You can print session, API response, headers etc. for troubleshooting:
    st.write("Session state:", dict(st.session_state))
    # Add more debug info as needed
