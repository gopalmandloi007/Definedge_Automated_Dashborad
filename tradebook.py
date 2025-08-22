import streamlit as st
import pandas as pd
from utils import definedge_get

def show():
    st.header("📖 Trade Book")
    data = definedge_get("/trades")
    df = pd.DataFrame(data.get("trades", []))
    st.dataframe(df)
