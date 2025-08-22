import requests

class ConnectToIntegrate:
    def __init__(self):
        self.uid = None
        self.actid = None
        self.api_session_key = None
        self.ws_session_key = None
        self.otp_token = None  # for step 2

    def login_step1(self, api_token, api_secret):
        url = f"https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/login/{api_token}"
        headers = {"api_secret": api_secret}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self.otp_token = data.get("otp_token")
        return data

    def login_step2(self, otp):
        url = "https://signin.definedgesecurities.com/auth/realms/debroking/dsbpkc/token"
        json_data = {"otp_token": self.otp_token, "otp": otp}
        resp = requests.post(url, json=json_data)
        resp.raise_for_status()
        data = resp.json()
        # Save session keys for use
        self.uid = data.get("uid")
        self.actid = data.get("actid")
        self.api_session_key = data.get("api_session_key")
        self.ws_session_key = data.get("susertoken")
        return data

    def set_session_keys(self, uid, actid, api_session_key, ws_session_key):
        self.uid = uid
        self.actid = actid
        self.api_session_key = api_session_key
        self.ws_session_key = ws_session_key

    def get_session_keys(self):
        return self.uid, self.actid, self.api_session_key, self.ws_session_key

class IntegrateOrders:
    def __init__(self, conn):
        self.conn = conn
    def holdings(self):
        # Dummy for now, real API calls should use self.conn.api_session_key in headers
        return {"data": [{"dp_qty": 10, "avg_buy_price": 100, "tradingsymbol": [{"exchange": "NSE", "tradingsymbol": "SBIN", "token": "123", "isin": "IN1234567890"}]}]}
