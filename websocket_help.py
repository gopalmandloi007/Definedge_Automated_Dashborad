import streamlit as st

def show():
    st.header("WebSocket Live Data / API Help")
    st.markdown("""
**WebSocket API Tips:**
- Use wss://integrate.definedgesecurities.com/WS
- Authenticate using your session key.
- Subscribe to quotes, order updates, etc. as per Integrate API WebSocket documentation.
- Streamlit doesn't support background WebSocket directly; use a Python script or backend for live push.
- For code samples, refer to Integrate API docs or ask your broker support.
    """)
