import streamlit as st
import pandas as pd
from utils import integrate_get

def app():
    st.header("Order Book & Trade Book")

    st.subheader("Order Book")
    try:
        data = integrate_get("/orders")
        orders = data.get("orders", [])
        if orders:
            st.dataframe(pd.DataFrame(orders))
        else:
            st.info("No orders found.")
    except Exception as e:
        st.error(f"Error fetching order book: {e}")

    st.subheader("Trade Book")
    try:
        data = integrate_get("/trades")
        trades = data.get("trades", [])
        if trades:
            st.dataframe(pd.DataFrame(trades))
        else:
            st.info("No trades found.")
    except Exception as e:
        st.error(f"Error fetching trade book: {e}")

if __name__ == "__main__":
    show()
