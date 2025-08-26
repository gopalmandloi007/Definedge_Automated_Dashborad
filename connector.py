# connector.py
# Minimal ConnectToIntegrate and IntegrateOrders wrapper (adjust if broker changes API structure)
import requests
from typing import Dict, Any, Optional

class ConnectToIntegrate:
    def __init__(self):
        self.uid: Optional[str] = None
        self.actid: Optional[str] = None
        self.api_session_key: Optional[str] = None
        self.ws_session_key: Optional[str] = None
        self.otp_token: Optional[str] = None

    def login_step1(self, api_token: str, api_secret: str) -> Dict[str, Any]:
        """
        Step 1: Creates OTP token (GET). Caller should show message to user (OTP sent).
        """
        url = f"https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/login/{api_token}"
        headers = {"api_secret": api_secret}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        self.otp_token = data.get("otp_token")
        return data

    def login_step2(self, otp: str) -> Dict[str, Any]:
        """
        Step 2: Submit OTP (POST) -> returns api_session_key + susertoken etc.
        """
        if not self.otp_token:
            raise RuntimeError("No otp_token found. Run login_step1 first.")
        url = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/token"
        payload = {"otp_token": self.otp_token, "otp": otp}
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # store keys
        self.uid = data.get("uid")
        self.actid = data.get("actid")
        self.api_session_key = data.get("api_session_key")
        self.ws_session_key = data.get("susertoken")
        return data

    def set_session_keys(self, uid: str, actid: str, api_session_key: str, ws_session_key: str):
        self.uid = uid
        self.actid = actid
        self.api_session_key = api_session_key
        self.ws_session_key = ws_session_key

    def get_session_keys(self):
        return {"uid": self.uid, "actid": self.actid, "api_session_key": self.api_session_key, "ws_session_key": self.ws_session_key}


class IntegrateOrders:
    """
    Very small wrapper to place/cancel/modify orders.
    Replace body to use broker-specific payload layout.
    """
    def __init__(self, conn: ConnectToIntegrate, base_url: str = "https://integrate.definedgesecurities.com/dart/v1"):
        self.conn = conn
        self.base_url = base_url.rstrip("/")

    def _headers(self):
        if not self.conn.api_session_key:
            raise RuntimeError("No api_session_key in connector")
        return {"Authorization": self.conn.api_session_key, "Content-Type": "application/json"}

    def holdings(self):
        url = f"{self.base_url}/holdings"
        r = requests.get(url, headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def positions(self):
        url = f"{self.base_url}/positions"
        r = requests.get(url, headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def place_order(self, payload: Dict[str, Any]):
        url = f"{self.base_url}/placeorder"
        r = requests.post(url, json=payload, headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, order_id: str):
        url = f"{self.base_url}/cancel/{order_id}"
        r = requests.get(url, headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    # Add other broker-specific helpers as needed (modify, gtt, etc.)

