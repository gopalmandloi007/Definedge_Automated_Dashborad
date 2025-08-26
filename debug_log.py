import streamlit as st

def debug_log(msg):
    if "debug_mode" in st.session_state and st.session_state["debug_mode"]:
        st.write(f"DEBUG: {msg}")
    # You can also log to a file if needed
