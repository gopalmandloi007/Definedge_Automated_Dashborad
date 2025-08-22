import streamlit as st
import requests

def get_session_headers():
    session = st.session_state.get("integrate_session")
    if not session:
        return {}
    return {"api_session_key": session["api_session_key"]}

def integrate_get(path):
    base_url = "https://api.definedgesecurities.com"  # Replace with actual base URL
    headers = get_session_headers()
    resp = requests.get(base_url + path, headers=headers)
    try:
        return resp.json()
    except Exception:
        return {"status": "ERROR", "message": resp.text}

def integrate_post(path, payload):
    base_url = "https://api.definedgesecurities.com"  # Replace with actual base URL
    headers = get_session_headers()
    resp = requests.post(base_url + path, json=payload, headers=headers)
    try:
        return resp.json()
    except Exception:
        return {"status": "ERROR", "message": resp.text}
