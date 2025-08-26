# session_utils.py
import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from connector import ConnectToIntegrate, IntegrateOrders

SESSION_FILE = "session.json"
SESSION_TTL_SECONDS = int(23.5 * 3600)  # 23.5 hours

def save_session_to_file(data: Dict[str, Any], path: str = SESSION_FILE):
    data_copy = dict(data)
    data_copy["_saved_at"] = int(time.time())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data_copy, f, indent=2)

def load_session_from_file(path: str = SESSION_FILE) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    saved = data.get("_saved_at", 0)
    if time.time() - saved > SESSION_TTL_SECONDS:
        # expired
        try:
            os.remove(path)
        except Exception:
            pass
        return None
    return data

def logout_session():
    if os.path.exists(SESSION_FILE):
        try:
            os.remove(SESSION_FILE)
        except Exception:
            pass

def get_active_session():
    """
    Returns session dict or None.
    """
    return load_session_from_file()

def get_active_io() -> IntegrateOrders:
    """
    Return an IntegrateOrders object wired with saved session keys.
    Raises if no session saved.
    """
    s = load_session_from_file()
    if not s:
        raise RuntimeError("No active session found. Please login via login page.")
    conn = ConnectToIntegrate()
    conn.set_session_keys(uid=s.get("uid"), actid=s.get("actid"), api_session_key=s.get("api_session_key"), ws_session_key=s.get("ws_session_key"))
    return IntegrateOrders(conn)
