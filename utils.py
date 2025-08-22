import streamlit as st
import requests
import pandas as pd

BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"

@st.cache_resource(show_spinner=False)
def get_api_session_key():
    return st.secrets["integrate_api_session_key"]

def integrate_get(endpoint, params=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": get_api_session_key()}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        else:
            st.error(f"Non-JSON response: {resp.text[:200]}")
            return {}
    except Exception as e:
        st.error(f"GET {url} failed: {e}")
        return {}

def integrate_post(endpoint, data=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": get_api_session_key(), "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        else:
            st.error(f"Non-JSON response: {resp.text[:200]}")
            return {}
    except Exception as e:
        st.error(f"POST {url} failed: {e}")
        return {}

def integrate_put(endpoint, data=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": get_api_session_key(), "Content-Type": "application/json"}
    try:
        resp = requests.put(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        else:
            st.error(f"Non-JSON response: {resp.text[:200]}")
            return {}
    except Exception as e:
        st.error(f"PUT {url} failed: {e}")
        return {}

def integrate_delete(endpoint, params=None):
    url = BASE_URL + endpoint
    headers = {"Authorization": get_api_session_key()}
    try:
        resp = requests.delete(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        if "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        else:
            st.error(f"Non-JSON response: {resp.text[:200]}")
            return {}
    except Exception as e:
        st.error(f"DELETE {url} failed: {e}")
        return {}

def load_master_symbols(filename="master.csv"):
    # Read the file, ignore blank lines
    with open(filename, "r", encoding="utf-8") as f:
        lines = [line for line in f if line.strip()]
    records = [line.strip().split("\t") for line in lines]
    # Ignore rows with fewer than 3 columns (junk rows)
    records = [row for row in records if len(row) >= 3]
    # Convert to DataFrame
    df = pd.DataFrame(records)
    # Always assign exactly 15 columns, per your sample
    base_columns = [
        "segment", "token", "symbol", "symbol_series", "series", "unknown1",
        "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
        "isin", "unknown7", "company"
    ]
    df.columns = base_columns[:df.shape[1]]
    # Only EQ & BE series, and only NSE/BSE stocks (not derivatives, indices)
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    # Compose the dropdown label as NSE:SYMBOL-SERIES
    df["dropdown"] = df["segment"] + ":" + df["symbol"] + "-" + df["series"]
    # Remove duplicates if any
    df = df.drop_duplicates(subset=["dropdown"])
    # Sort for better UX
    df = df.sort_values("dropdown")
    # Return dropdown and core fields
    return df[["dropdown", "segment", "symbol", "series", "company"]]
