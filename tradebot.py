import streamlit as st
from websocket_handler import WebSocketHandler

def app():
    st.header("Tradebot — Automated Trading & Live Tracking (New)")
    session = st.session_state.get("integrate_session")
    if not session:
        st.error("No active session found!")
        return

    uid, actid, ws_session_key = session["uid"], session["actid"], session["ws_session_key"]

    # UI for handler settings
    st.subheader("WebSocket Handler Controls")
    strategy = st.selectbox("Strategy", ["Scalping", "Intraday", "Swing", "Position"])
    decision_interval = st.slider("Decision Interval (sec)", 1, 300, 5)
    max_idle_time = st.slider("Auto Disconnect (sec)", 30, 600, 300)
    auto_disconnect = st.checkbox("Disconnect on Blur/Idle", True)

    # Handler callbacks
    def on_touchline(data):
        st.session_state['last_touchline'] = data

    def on_depth(data):
        st.session_state['last_depth'] = data

    def on_order(data):
        st.session_state['last_order'] = data

    if "ws_handler" not in st.session_state:
        st.session_state["ws_handler"] = None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start Live Feed"):
            ws_handler = WebSocketHandler(
                uid, actid, ws_session_key,
                on_touchline=on_touchline,
                on_depth=on_depth,
                on_order=on_order,
                decision_interval=decision_interval,
                auto_disconnect_on_blur=auto_disconnect,
                max_idle_time=max_idle_time
            )
            ws_handler.connect()
            ws_handler.subscribe_touchline(['NSE|22'])  # Example scrip
            ws_handler.subscribe_order_update()
            st.session_state["ws_handler"] = ws_handler
            st.success("Live WebSocket Feed Started.")

    with col2:
        if st.button("Stop Live Feed"):
            if st.session_state["ws_handler"]:
                st.session_state["ws_handler"].disconnect()
                st.session_state["ws_handler"] = None
                st.success("WebSocket Feed Stopped.")

    # Live data panel
    st.subheader("Live Updates")
    if 'last_touchline' in st.session_state:
        st.json(st.session_state['last_touchline'])
    if 'last_order' in st.session_state:
        st.json(st.session_state['last_order'])
