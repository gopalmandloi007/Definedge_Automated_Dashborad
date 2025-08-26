import json
import os
from integrate import ConnectToIntegrate

SESSION_FILE = "session.json"

def get_active_session():
    """
    Returns a ConnectToIntegrate object.
    If session.json exists, restore keys instead of re-login.
    """
    conn = ConnectToIntegrate()
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            conn.set_session_keys(
                data.get("uid"),
                data.get("actid"),
                data.get("api_session_key"),
                data.get("ws_session_key"),
            )
    return conn

def save_session(conn: ConnectToIntegrate):
    """
    Save session keys to disk (so OTP login not required every time).
    """
    uid, actid, api_session_key, ws_session_key = conn.get_session_keys()
    data = {
        "uid": uid,
        "actid": actid,
        "api_session_key": api_session_key,
        "ws_session_key": ws_session_key,
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)
