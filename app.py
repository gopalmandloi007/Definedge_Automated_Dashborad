import streamlit as st
import requests
import json
import websocket
import threading

# ==============================
# CONFIGURATION
# ==============================
BASE_URL = "https://api.definedgesecurities.com"
LOGIN_URL = f"{BASE_URL}/auth/token"
PLACE_ORDER_URL = f"{BASE_URL}/orders"
HOLDINGS_URL = f"{BASE_URL}/holdings"
POSITIONS_URL = f"{BASE_URL}/positions"
QUOTES_URL = f"{BASE_URL}/quotes"

st.set_page_config(page_title="Definedge Trading App", layout="wide")

# ==============================
# SESSION STATE for TOKEN mgmt
# ==============================
if "access_token" not in st.session_state:
    st.session_state.access_token = None


# ==============================
# LOGIN FUNCTION
# ==============================
def login(client_id, client_secret, pin):
    try:
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "pin": pin
        }
        res = requests.post(LOGIN_URL, json=payload)
        if res.status_code == 200:
            token = res.json().get("access_token")
            st.session_state.access_token = token
            st.success("✅ Login successful")
        else:
            st.error(f"Login failed: {res.text}")
    except Exception as e:
        st.error(f"Error: {e}")


# ==============================
# PLACE ORDER FUNCTION
# ==============================
def place_order(symbol, qty, side, order_type="MARKET", product="CNC"):
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    payload = {
        "symbol": symbol,
        "qty": qty,
        "side": side,            # BUY or SELL
        "type": order_type,      # MARKET / LIMIT
        "product": product       # CNC / MIS etc.
    }
    res = requests.post(PLACE_ORDER_URL, headers=headers, json=payload)
    return res.json()


# ==============================
# FETCH HOLDINGS & POSITIONS
# ==============================
def get_holdings():
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    res = requests.get(HOLDINGS_URL, headers=headers)
    return res.json()

def get_positions():
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    res = requests.get(POSITIONS_URL, headers=headers)
    return res.json()


# ==============================
# QUOTES (Market Data)
# ==============================
def get_quotes(symbol):
    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
    res = requests.get(f"{QUOTES_URL}?symbol={symbol}", headers=headers)
    return res.json()


# ==============================
# WEBSOCKET HANDLER
# ==============================
def on_message(ws, message):
    data = json.loads(message)
    st.session_state.ws_data = data  # Save incoming ticks in session_state

def on_open(ws):
    st.success("🔗 WebSocket connected")

def start_ws():
    ws_url = "wss://stream.definedgesecurities.com"  # replace with actual WS url
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_open=on_open)
    ws.run_forever()

# ==============================
# STREAMLIT UI
# ==============================
st.title("📈 Definedge Trading App")

# ---- Login Section ----
with st.expander("🔑 Login"):
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret", type="password")
    pin = st.text_input("PIN", type="password")
    if st.button("Login"):
        login(client_id, client_secret, pin)

# ---- Order Placement ----
if st.session_state.access_token:
    st.subheader("📝 Place Order")
    col1, col2, col3 = st.columns(3)
    with col1:
        symbol = st.text_input("Symbol", "NSE:RELIANCE")
    with col2:
        qty = st.number_input("Quantity", value=1, step=1)
    with col3:
        side = st.selectbox("Side", ["BUY", "SELL"])

    if st.button("Place Order"):
        result = place_order(symbol, qty, side)
        st.write(result)

    # ---- Holdings & Positions ----
    st.subheader("📊 Holdings / Positions")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Get Holdings"):
            st.json(get_holdings())
    with c2:
        if st.button("Get Positions"):
            st.json(get_positions())

    # ---- Quotes ----
    st.subheader("💹 Market Quotes")
    q_symbol = st.text_input("Quote Symbol", "NSE:INFY")
    if st.button("Get Quote"):
        st.json(get_quotes(q_symbol))

    # ---- WebSocket Live Ticks ----
    st.subheader("🔴 Live Market Feed (WebSocket)")
    if st.button("Start WebSocket"):
        threading.Thread(target=start_ws, daemon=True).start()
    if "ws_data" in st.session_state:
        st.write(st.session_state.ws_data)
