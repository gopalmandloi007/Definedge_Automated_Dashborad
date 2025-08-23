import websocket
import threading
import json
import time

class WebSocketHandler:
    def __init__(self, uid, actid, ws_session_key, 
                 on_touchline=None, on_depth=None, on_order=None,
                 decision_interval=5, auto_disconnect_on_blur=True, max_idle_time=300):
        self.url = "wss://trade.definedgesecurities.com/NorenWSTRTP/"
        self.uid = uid
        self.actid = actid
        self.ws_session_key = ws_session_key
        self.ws = None
        self.connected = False
        self.last_heartbeat = time.time()
        self.last_message = time.time()
        self.subscribed_touchline = set()
        self.subscribed_depth = set()
        self.order_subscribed = False
        self.on_touchline = on_touchline
        self.on_depth = on_depth
        self.on_order = on_order
        self.decision_interval = decision_interval
        self.auto_disconnect_on_blur = auto_disconnect_on_blur
        self.max_idle_time = max_idle_time
        self._stop = threading.Event()
        self._thread = None

    def _on_open(self, ws):
        # Send connect request
        ws.send(json.dumps({
            "t": "c",
            "uid": self.uid,
            "actid": self.actid,
            "source": "TRTP",
            "susertoken": self.ws_session_key
        }))
        self.connected = True
        self.last_heartbeat = time.time()

    def _on_message(self, ws, message):
        self.last_message = time.time()
        data = json.loads(message)
        t = data.get("t")
        if t == "ck":
            self.connected = True
        elif t == "tf":
            if self.on_touchline:
                self.on_touchline(data)
        elif t == "df":
            if self.on_depth:
                self.on_depth(data)
        elif t == "om":
            if self.on_order:
                self.on_order(data)
        # Handle more types as needed

    def _on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self.connected = False
        print("WebSocket closed:", close_status_code, close_msg)
        # Optionally auto-reconnect here

    def connect(self):
        self._stop.clear()
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self._thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self._thread.start()
        # Start heartbeat thread
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        # Start idle checker
        threading.Thread(target=self._idle_checker, daemon=True).start()

    def disconnect(self):
        self._stop.set()
        if self.ws:
            self.ws.close()
        self.connected = False

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            if self.connected and (time.time() - self.last_heartbeat > 50):
                try:
                    self.ws.send(json.dumps({"t": "h"}))
                    self.last_heartbeat = time.time()
                except Exception as e:
                    print("Heartbeat error:", e)
            time.sleep(5)

    def _idle_checker(self):
        while not self._stop.is_set():
            if self.max_idle_time and (time.time() - self.last_message > self.max_idle_time):
                print("Idle timeout, disconnecting WebSocket.")
                self.disconnect()
            time.sleep(5)

    def subscribe_touchline(self, scriplist):
        k_str = '#'.join(scriplist)
        self.ws.send(json.dumps({"t": "t", "k": k_str}))
        self.subscribed_touchline.update(scriplist)

    def unsubscribe_touchline(self, scriplist):
        k_str = '#'.join(scriplist)
        self.ws.send(json.dumps({"t": "u", "k": k_str}))
        self.subscribed_touchline.difference_update(scriplist)

    def subscribe_depth(self, scriplist):
        k_str = '#'.join(scriplist)
        self.ws.send(json.dumps({"t": "d", "k": k_str}))
        self.subscribed_depth.update(scriplist)

    def unsubscribe_depth(self, scriplist):
        k_str = '#'.join(scriplist)
        self.ws.send(json.dumps({"t": "ud", "k": k_str}))
        self.subscribed_depth.difference_update(scriplist)

    def subscribe_order_update(self):
        if not self.order_subscribed:
            self.ws.send(json.dumps({"t": "o", "actid": self.actid}))
            self.order_subscribed = True

    def unsubscribe_order_update(self):
        if self.order_subscribed:
            self.ws.send(json.dumps({"t": "uo"}))
            self.order_subscribed = False

    def change_decision_interval(self, seconds):
        self.decision_interval = seconds

    def change_idle_timeout(self, seconds):
        self.max_idle_time = seconds
