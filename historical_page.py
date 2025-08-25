# historical_page.py
import streamlit as st
from masterfile_handler import download_master, load_master
from historical_handler import update_all_from_master
import os

st.header("Master file & Historical quick tasks")

if st.button("Download today's master (NSE_CASH)"):
    path = download_master("NSE_CASH")
    st.success(f"Saved: {path}")

if st.button("Show sample master"):
    df = load_master("NSE_CASH")
    st.dataframe(df.head())

# provide quick trigger (batch) - similar to code in app.py

