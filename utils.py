import streamlit as st
import requests
import os
from debug_utils import debug_log

def get_session_headers():
    session = st.session_state.get("integrate_session")
    if not session:
        return {}
    return {
        "Authorization": session["api_session_key"],
        "actid": session["actid"],
        "uid": session["uid"]
    }

def integrate_get(path):
    base_url = "https://integrate.definedgesecurities.com/dart/v1"
    headers = get_session_headers()
    url = base_url + path
    debug_log(f"GET {url} with headers {headers}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        debug_log(f"GET response: {resp.status_code} - {resp.text}")
        resp.raise_for_status()
        try:
            data = resp.json()
            if data.get("status") == "ERROR" and "session" in data.get("message", "").lower():
                debug_log("Session expired error detected in API response.")
                st.session_state.pop("integrate_session", None)
                try:
                    os.remove("session.json")
                except Exception:
                    pass
            return data
        except Exception:
            return {"status": "ERROR", "message": f"Non-JSON response: {resp.text}"}
    except Exception as e:
        debug_log(f"GET error: {e}")
        return {"status": "ERROR", "message": str(e)}

def integrate_post(path, payload):
    base_url = "https://integrate.definedgesecurities.com/dart/v1"
    headers = get_session_headers()
    url = base_url + path
    debug_log(f"POST {url} payload {payload} headers {headers}")
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        debug_log(f"POST response: {resp.status_code} - {resp.text}")
        resp.raise_for_status()
        try:
            data = resp.json()
            if data.get("status") == "ERROR" and "session" in data.get("message", "").lower():
                debug_log("Session expired error detected in API response.")
                st.session_state.pop("integrate_session", None)
                try:
                    os.remove("session.json")
                except Exception:
                    pass
            return data
        except Exception:
            return {"status": "ERROR", "message": f"Non-JSON response: {resp.text}"}
    except Exception as e:
        debug_log(f"POST error: {e}")
        return {"status": "ERROR", "message": str(e)}
