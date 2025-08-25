import json
import threading
import time
import websocket
import streamlit as st
from utils import integrate_post  # use your REST order function

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WSManager:
    def __init__(self, conn):
        self.conn = conn   # ConnectToIntegrate instance
        self.ws = None
        self.connected = False
        self.positions_state = {}  # symbol → dict(state machine)

    def connect(self):
        """Connect to Definedge WS"""
        uid, actid, _, susertoken = self.conn.get_session_keys()
        if not susertoken:
            raise Exception("❌ No WS session key, please login again.")

        def on_open(ws):
            payload = {"t": "c", "uid": uid, "actid": actid,
                       "source": "TRTP", "susertoken": susertoken}
            ws.send(json.dumps(payload))
            st.toast("✅ WebSocket connected")

        def on_message(ws, message):
            data = json.loads(message)
            self.handle_message(data)

        def on_error(ws, err): st.error(f"WS Error: {err}")
        def on_close(ws, *a): st.warning("⚠️ WS Closed")

        self.ws = websocket.WebSocketApp(
            WS_URL, on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

        # Heartbeat thread
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def _heartbeat(self):
        while True:
            try:
                if self.ws and self.connected:
                    self.ws.send(json.dumps({"t": "h"}))
            except:
                pass
            time.sleep(50)

    def subscribe_touchline(self, symbols):
        """Subscribe for live LTP"""
        if not self.ws: return
        msg = {"t": "t", "k": "#".join(symbols)}
        self.ws.send(json.dumps(msg))

    def handle_message(self, data):
        t = data.get("t")
        if t in ("tf", "df"):
            symbol = f"{data['e']}|{data['tk']}"
            ltp = float(data.get("lp", 0))
            self.evaluate_triggers(symbol, ltp)
        elif t == "ck":
            self.connected = True
        elif t == "om":
            st.info(f"📡 Order Update: {data}")

    # ----------------------
    # TRIGGER ENGINE
    # ----------------------
    def add_position(self, symbol, entry, qty, sl_pct, targets_pct):
        """Initialize SL/Target strategy for a position"""
        self.positions_state[symbol] = {
            "entry": entry,
            "remaining_qty": qty,
            "sl": entry * (1 - sl_pct/100),
            "targets": [entry*(1+t/100) for t in targets_pct],
            "achieved": 0,
        }

    def evaluate_triggers(self, symbol, ltp):
        state = self.positions_state.get(symbol)
        if not state: return

        entry = state["entry"]
        sl = state["sl"]
        rem = state["remaining_qty"]
        targets = state["targets"]
        ach = state["achieved"]

        # Stoploss
        if ltp <= sl and rem > 0:
            st.error(f"🛑 SL hit for {symbol} at {ltp}, selling {rem}")
            self.execute_order(symbol, rem)
            state["remaining_qty"] = 0
            return

        # Target check
        if ach < len(targets) and ltp >= targets[ach]:
            sell_qty = rem // (len(targets) - ach)
            st.success(f"🎯 Target-{ach+1} hit at {ltp}, selling {sell_qty}")
            self.execute_order(symbol, sell_qty)
            state["remaining_qty"] -= sell_qty
            state["achieved"] += 1
            # Trail SL rule
            if ach == 0:
                state["sl"] = entry
            else:
                state["sl"] = targets[ach-1]

    def execute_order(self, symbol, qty):
        payload = {
            "variety": "REGULAR",
            "symbol_id": symbol,
            "qty": qty,
            "side": "SELL",
            "ordertype": "MKT",
            "product": "CNC",
        }
        try:
            resp = integrate_post("/placeorder", payload)
            st.write(f"✅ Order Response: {resp}")
        except Exception as e:
            st.error(f"Order failed: {e}")
