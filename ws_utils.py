import json
import threading
import websocket
import time
from utils import place_order   # your REST execution

WS_URL = "wss://trade.definedgesecurities.com/NorenWSTRTP/"

class WSManager:
    def __init__(self, uid, actid, susertoken, source="TRTP"):
        self.uid = uid
        self.actid = actid
        self.susertoken = susertoken
        self.source = source
        self.ws = None
        self.connected = False
        self.subscribed = set()
        self.positions_state = {}  # symbol → dict(state machine info)

    def connect(self):
        def _on_open(ws):
            login_msg = {
                "t": "c",
                "uid": self.uid,
                "actid": self.actid,
                "susertoken": self.susertoken,
                "source": self.source
            }
            ws.send(json.dumps(login_msg))

        def _on_message(ws, msg):
            data = json.loads(msg)
            self.handle_message(data)

        def _on_close(ws, code, reason):
            self.connected = False
            print("WS closed", reason)

        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_open=_on_open,
            on_message=_on_message,
            on_close=_on_close
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
        self.connected = True

        # heartbeat thread
        def _heartbeat():
            while self.connected:
                try:
                    self.ws.send(json.dumps({"t": "h"}))
                except:
                    break
                time.sleep(50)
        threading.Thread(target=_heartbeat, daemon=True).start()

    def subscribe_touchline(self, scriplist):
        msg = {"t": "t", "k": "#".join(scriplist)}
        self.ws.send(json.dumps(msg))
        self.subscribed.update(scriplist)

    def unsubscribe(self, scriplist):
        msg = {"t": "u", "k": "#".join(scriplist)}
        self.ws.send(json.dumps(msg))
        self.subscribed.difference_update(scriplist)

    def handle_message(self, data):
        t = data.get("t")
        if t in ("tf", "df"):  # feed
            symbol = f"{data['e']}|{data['tk']}"
            ltp = float(data.get("lp", 0))
            self.evaluate_triggers(symbol, ltp)

    def evaluate_triggers(self, symbol, ltp):
        state = self.positions_state.get(symbol)
        if not state: return

        entry = state["entry"]
        targets = state["targets"]
        sl = state["sl"]
        rem_qty = state["remaining_qty"]

        # check stop loss
        if ltp <= sl and rem_qty > 0:
            print(f"[{symbol}] Stoploss hit at {ltp}, selling {rem_qty}")
            place_order(symbol, rem_qty, "SELL", "MKT")  # REST API call
            state["remaining_qty"] = 0
            return

        # check targets
        achieved = state["achieved_targets"]
        if achieved < len(targets) and ltp >= targets[achieved]:
            sell_qty = rem_qty // (len(targets) - achieved)
            print(f"[{symbol}] Target-{achieved+1} hit at {ltp}, selling {sell_qty}")
            place_order(symbol, sell_qty, "SELL", "MKT")
            state["remaining_qty"] -= sell_qty
            state["achieved_targets"] += 1
            # trail SL rule
            if achieved == 0:
                state["sl"] = entry
            else:
                state["sl"] = targets[achieved-1]
