import streamlit as st
import requests

def get_session_headers():
    session = st.session_state.get("integrate_session")
    if not session:
        return {}
    return {"api_session_key": session["api_session_key"]}

def integrate_get(path):
    base_url = "https://integrate.definedgesecurities.com/dart/v1"  # NEW BASE URL!
    headers = get_session_headers()
    url = base_url + path
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ERROR", "message": f"Non-JSON response: {resp.text}"}
    except requests.ConnectionError:
        return {"status": "ERROR", "message": f"Could not connect to API server at {url}. Please check your network or API status."}
    except requests.Timeout:
        return {"status": "ERROR", "message": f"Request to {url} timed out."}
    except requests.HTTPError as e:
        return {"status": "ERROR", "message": f"HTTP error: {e}, Response: {getattr(e.response, 'text', '')}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Unexpected error: {str(e)}"}

def integrate_post(path, payload):
    base_url = "https://integrate.definedgesecurities.com/dart/v1"  # NEW BASE URL!
    headers = get_session_headers()
    url = base_url + path
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ERROR", "message": f"Non-JSON response: {resp.text}"}
    except requests.ConnectionError:
        return {"status": "ERROR", "message": f"Could not connect to API server at {url}. Please check your network or API status."}
    except requests.Timeout:
        return {"status": "ERROR", "message": f"Request to {url} timed out."}
    except requests.HTTPError as e:
        return {"status": "ERROR", "message": f"HTTP error: {e}, Response: {getattr(e.response, 'text', '')}"}
    except Exception as e:
        return {"status": "ERROR", "message": f"Unexpected error: {str(e)}"}
