import streamlit as st
from ws_utils import WSManager
import session_utils

def app():
    st.subheader("📡 Tradebot Live")

    conn = session_utils.get_active_io()
    ws_client = WSManager(conn)

    if st.button("Start WebSocket"):
        ws_client.connect()
        # Example: Reliance with 3 targets
        ws_client.add_position(
            "NSE|RELIANCE-EQ",
            entry=2500,
            qty=10,
            sl_pct=2,
            targets_pct=[2, 4, 6]
        )
        ws_client.subscribe_touchline(["NSE|RELIANCE-EQ"])
        st.success("Subscribed Reliance with SL/Targets strategy.")
