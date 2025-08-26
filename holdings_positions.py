import streamlit as st
import pandas as pd
from utils import integrate_get
from utils import integrate_post

def app():
    st.header("Positions & Holdings")

    st.subheader("Positions")
    try:
        data = integrate_get("/positions")
        positions = data.get("positions", [])
        if positions:
            st.dataframe(pd.DataFrame(positions))
        else:
            st.info("No positions found.")
    except Exception as e:
        st.error(f"Error fetching positions: {e}")

    st.subheader("Holdings")
    try:
        data = integrate_get("/holdings")
        headers = {"Authorization": api_session_key}
        holdings = data.get("holdings", [])
        if holdings:
            st.dataframe(pd.DataFrame(holdings))
        else:
            st.info("No holdings found.")
    except Exception as e:
        st.error(f"Error fetching holdings: {e}")

if __name__ == "__main__":
    show()
