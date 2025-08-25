# tradebot.py
# Streamlit page: Live trade bot with Targets/Trailing SL/Open Risk
# - Prefers WebSocket ticks (ws_utils.WSClient) for low-latency triggers
# - Falls back to REST polling if websocket client not available
# - Uses your utils.integrate_post for REST order execution
# - State machine per-position with remaining-qty rule + progressive SL trail

import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from queue import Queue, Empty

import streamlit as st
import pandas as pd
import numpy as np
import requests

import session_utils
from utils import integrate_post

# ========= CONFIG =========
WS_TICK_EVENT_QUEUE_KEY = "tradebot_tick_queue"
ENGINE_STATE_KEY = "tradebot_engine"
DEFAULT_VALIDITY = "DAY"
DEFAULT_PRODUCT = "CNC"  # For delivery holdings; use "NORMAL"/"INTRADAY" if you want
POLL_INTERVAL_SEC = 2.0   # Fallback polling frequency when WS isn't used
TOTAL_CAPITAL_DEFAULT = 1_000_000  # ₹10,00,000 as per your example

# ========= OPTIONAL: WebSocket bridge (if ws_utils exists) =========
"""
Expected ws_utils.py minimal interface:

class WSClient:
    def __init__(self, uid:str, actid:str, susertoken:str, on_touchline=None, on_order_update=None):
        ...
    def connect(self): ...
    def subscribe_touchline(self, keys: List[str]): ...  # keys like ["NSE|22", "BSE|508123", "NSE|RELIANCE-EQ"]
    def unsubscribe_touchline(self, keys: List[str]): ...
    def close(self): ...

- It should call on_touchline(key:str, ltp:float, raw:dict) on each tick.
- We push ticks into st.session_state[WS_TICK_EVENT_QUEUE_KEY] queue inside on_touchline callback.

If you don't have ws_utils yet, bot will run in Polling mode.
"""
WS_AVAILABLE = False
try:
    from ws_utils import WSClient  # your file
    WS_AVAILABLE = True
except Exception:
    WS_AVAILABLE = False


# ========= Helpers =========

def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _parse_ws_key_to_quote_parts(ws_key: str) -> Tuple[str, str, bool]:
    """
    ws_key is like "NSE|22" (token) OR "NSE|RELIANCE-EQ" (tradingsymbol).
    Returns (exchange, code, is_token)
    """
    if "|" not in ws_key:
        # assume it's a tradingsymbol on NSE
        return "NSE", ws_key, False
    exch, code = ws_key.split("|", 1)
    is_token = code.isdigit()
    return exch, code, is_token

def _get_ltp_via_rest(api_key: str, ws_key: str) -> float:
    exch, code, is_token = _parse_ws_key_to_quote_parts(ws_key)
    # Definedge quotes endpoint accepts either token OR tradingsymbol (both variants exist in your codebase)
    url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exch}/{code}"
    headers = {"Authorization": api_key}
    try:
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            return _safe_float(data.get("ltp", 0))
    except Exception:
        pass
    return 0.0


# ========= Strategy / State Machine =========

@dataclass
class PositionConfig:
    name: str                 # label: e.g., "P1 SBIN"
    ws_key: str               # "NSE|22" or "NSE|RELIANCE-EQ" (for WS/polling)
    tradingsymbol: str        # "SBIN-EQ" (for REST placeorder)
    exchange: str             # "NSE"/"BSE" (for REST placeorder)
    entry: float
    qty: int
    sl_pct: float
    targets_pct: List[float]  # e.g., [10,20,30,40]
    product: str = DEFAULT_PRODUCT

@dataclass
class PositionState:
    cfg: PositionConfig
    sl_price: float = 0.0
    target_prices: List[float] = field(default_factory=list)
    achieved: int = 0
    remaining_qty: int = 0
    realized_pnl: float = 0.0
    last_ltps: List[float] = field(default_factory=list)  # short history
    last_order_ids: List[str] = field(default_factory=list)
    closed: bool = False

    def init_from_cfg(self):
        self.sl_price = round(self.cfg.entry * (1 - self.cfg.sl_pct / 100.0), 2)
        self.target_prices = [round(self.cfg.entry * (1 + p/100.0), 2) for p in self.cfg.targets_pct]
        self.remaining_qty = int(self.cfg.qty)
        self.achieved = 0
        self.realized_pnl = 0.0
        self.last_ltps.clear()
        self.last_order_ids.clear()
        self.closed = False

    def planned_sell_qty(self) -> int:
        remaining_targets = len(self.target_prices) - self.achieved
        if remaining_targets <= 0:
            return self.remaining_qty
        return max(1, self.remaining_qty // remaining_targets)

    def next_target_price(self) -> Optional[float]:
        if self.achieved < len(self.target_prices):
            return self.target_prices[self.achieved]
        return None

    def open_risk_value(self) -> float:
        # max(Entry − Current SL, 0) × Remaining Qty
        risk_per_share = max(self.cfg.entry - self.sl_price, 0)
        return round(risk_per_share * self.remaining_qty, 2)

    def locked_in_value(self) -> float:
        # (SL - Entry) * Remaining Qty, only if SL > Entry
        val = (self.sl_price - self.cfg.entry) * self.remaining_qty
        return round(val if val > 0 else 0.0, 2)

    def record_fill(self, sell_qty: int, fill_price: float):
        pnl = (fill_price - self.cfg.entry) * sell_qty
        self.realized_pnl += pnl
        self.remaining_qty -= sell_qty
        if self.remaining_qty <= 0:
            self.closed = True

    def trail_after_target(self):
        # T1: SL=Entry; T2+: SL = previous target
        if self.achieved == 1:
            self.sl_price = round(self.cfg.entry, 2)
        elif self.achieved >= 2:
            self.sl_price = round(self.target_prices[self.achieved - 2], 2)

    def to_row(self, ltp: float, total_capital: float) -> Dict:
        trgs_str = ", ".join([f"{p:.2f}" for p in self.target_prices]) if self.target_prices else "-"
        next_trig = self.next_target_price()
        return {
            "Name": self.cfg.name,
            "Exchange": self.cfg.exchange,
            "WS Key": self.cfg.ws_key,
            "Tradingsymbol": self.cfg.tradingsymbol,
            "Entry": round(self.cfg.entry, 2),
            "Qty (rem)": self.remaining_qty,
            "SL%": self.cfg.sl_pct,
            "SL Price": round(self.sl_price, 2),
            "Targets": trgs_str,
            "LTP": round(ltp, 2),
            "Next Trigger": next_trig if next_trig is not None else "-",
            "Planned Sell Qty": self.planned_sell_qty() if next_trig is not None else 0,
            "Open Risk (₹)": self.open_risk_value(),
            "Open Risk (%Cap)": round((self.open_risk_value()/total_capital*100) if total_capital else 0.0, 2),
            "Locked-in @Stop (₹)": self.locked_in_value(),
            "Realized P&L (₹)": round(self.realized_pnl, 2),
            "Achieved": self.achieved,
            "Closed": self.closed
        }


class PortfolioEngine:
    """
    Holds all positions + executes the rule engine on tick.
    """
    def __init__(self, total_capital: float, api_session_key: str, dry_run: bool = True):
        self.total_capital = total_capital
        self.api_session_key = api_session_key
        self.dry_run = dry_run
        self.positions: Dict[str, PositionState] = {}  # keyed by ws_key
        self.ltps: Dict[str, float] = {}  # latest LTP per ws_key
        self.order_book: List[Dict] = []  # simple audit trail

    def add_position(self, cfg: PositionConfig):
        st.session_state.setdefault("debug_last", "")
        ps = PositionState(cfg=cfg)
        ps.init_from_cfg()
        self.positions[cfg.ws_key] = ps

    def get_state(self, ws_key: str) -> Optional[PositionState]:
        return self.positions.get(ws_key)

    def on_tick(self, ws_key: str, ltp: float):
        self.ltps[ws_key] = ltp
        ps = self.positions.get(ws_key)
        if not ps or ps.closed or ps.remaining_qty <= 0:
            return

        # Save a short history
        ps.last_ltps.append(ltp)
        if len(ps.last_ltps) > 20:
            ps.last_ltps = ps.last_ltps[-20:]

        # 1) Stoploss check first
        if ltp <= ps.sl_price and ps.remaining_qty > 0:
            self._sell(ps, ps.remaining_qty, ltp, reason="STOPLOSS")
            ps.closed = True
            return

        # 2) Handle gaps that cross multiple targets:
        # while ltp >= next target, keep selling sequentially
        next_t = ps.next_target_price()
        while (next_t is not None) and (ltp >= next_t) and (ps.remaining_qty > 0):
            qty_to_sell = ps.planned_sell_qty()
            self._sell(ps, qty_to_sell, ltp, reason=f"TARGET-{ps.achieved + 1}")
            ps.achieved += 1
            ps.trail_after_target()
            next_t = ps.next_target_price()

    def _sell(self, ps: PositionState, qty: int, price_hint: float, reason: str):
        qty = int(max(0, min(qty, ps.remaining_qty)))
        if qty == 0:
            return

        payload = {
            "tradingsymbol": ps.cfg.tradingsymbol,
            "exchange": ps.cfg.exchange,
            "order_type": "SELL",
            "quantity": qty,
            "product_type": ps.cfg.product,
            "validity": DEFAULT_VALIDITY,
            "price_type": "MARKET",
            "price": 0.0
        }

        order_id = "DRYRUN"
        ok = True
        err = None

        if self.dry_run:
            # Assume immediate fill at price_hint for reporting
            pass
        else:
            try:
                resp = integrate_post("/placeorder", payload)
                # integrate_post returns dict -> capture order id if present
                order_id = str(resp.get("norenordno") or resp.get("order_id") or resp)
                # You can enhance: check API "status" and errors
            except Exception as e:
                ok = False
                err = str(e)

        if ok:
            # Use price_hint as avg fill (best-effort; real fills can be taken from order-update WS)
            ps.record_fill(qty, price_hint)
            self.order_book.append({
                "ts": time.strftime("%H:%M:%S"),
                "name": ps.cfg.name,
                "ws_key": ps.cfg.ws_key,
                "side": "SELL",
                "qty": qty,
                "price_hint": round(price_hint, 2),
                "reason": reason,
                "order_id": order_id,
                "dry_run": self.dry_run
            })
        else:
            self.order_book.append({
                "ts": time.strftime("%H:%M:%S"),
                "name": ps.cfg.name,
                "ws_key": ps.cfg.ws_key,
                "side": "SELL",
                "qty": qty,
                "price_hint": round(price_hint, 2),
                "reason": f"{reason} (FAILED: {err})",
                "order_id": "ERROR",
                "dry_run": self.dry_run
            })

    def portfolio_open_risk(self) -> float:
        return round(sum(ps.open_risk_value() for ps in self.positions.values()), 2)

    def portfolio_locked_in(self) -> float:
        return round(sum(ps.locked_in_value() for ps in self.positions.values()), 2)

    def total_realized(self) -> float:
        return round(sum(ps.realized_pnl for ps in self.positions.values()), 2)

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for ws_key, ps in self.positions.items():
            ltp = self.ltps.get(ws_key, 0.0)
            rows.append(ps.to_row(ltp, self.total_capital))
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        # Useful ordering
        cols = ["Name", "Exchange", "WS Key", "Tradingsymbol", "Entry", "Qty (rem)",
                "SL%", "SL Price", "Targets", "LTP", "Next Trigger", "Planned Sell Qty",
                "Open Risk (₹)", "Open Risk (%Cap)", "Locked-in @Stop (₹)",
                "Realized P&L (₹)", "Achieved", "Closed"]
        return df[cols]


# ========= Streamlit Page =========

def _ensure_engine():
    if ENGINE_STATE_KEY not in st.session_state:
        # Create engine with default total capital & dry-run ON
        api_session_key = st.secrets.get("integrate_api_session_key", "")
        st.session_state[ENGINE_STATE_KEY] = PortfolioEngine(
            total_capital=TOTAL_CAPITAL_DEFAULT,
            api_session_key=api_session_key,
            dry_run=True
        )
    if WS_TICK_EVENT_QUEUE_KEY not in st.session_state:
        st.session_state[WS_TICK_EVENT_QUEUE_KEY] = Queue()

def _start_ws_if_needed(engine: PortfolioEngine, subscribe_keys: List[str]):
    """
    Start WebSocket and subscribe to ws_keys.
    Pushes ticks into the shared queue.
    """
    if not WS_AVAILABLE:
        st.warning("WebSocket client (ws_utils.py) not found. Falling back to REST polling.")
        return None

    # Get session keys
    io = session_utils.get_active_io()
    uid, actid, _, susertoken = io.conn.get_session_keys()

    def on_touchline(key, ltp, raw):
        try:
            st.session_state[WS_TICK_EVENT_QUEUE_KEY].put((key, _safe_float(ltp)))
        except Exception:
            pass

    ws_client = WSClient(uid=uid, actid=actid, susertoken=susertoken,
                         on_touchline=on_touchline, on_order_update=None)
    ws_client.connect()
    if subscribe_keys:
        ws_client.subscribe_touchline(subscribe_keys)
    st.toast(f"Subscribed {len(subscribe_keys)} symbol(s) on WebSocket.")
    return ws_client

def _run_polling_loop(engine: PortfolioEngine, ws_keys: List[str], stop_event: threading.Event):
    """
    Fallback when WS not available: poll REST LTPs periodically and feed engine.
    """
    api_key = engine.api_session_key
    while not stop_event.is_set():
        for k in ws_keys:
            ltp = _get_ltp_via_rest(api_key, k)
            engine.on_tick(k, ltp)
        time.sleep(POLL_INTERVAL_SEC)

def _preload_example_positions(engine: PortfolioEngine):
    # Matches your example setup exactly
    examples = [
        PositionConfig(
            name="P1", ws_key="NSE|P1", tradingsymbol="P1", exchange="NSE",
            entry=100.0, qty=1000, sl_pct=2.0, targets_pct=[10, 20, 30, 40], product=DEFAULT_PRODUCT
        ),
        PositionConfig(
            name="P2", ws_key="NSE|P2", tradingsymbol="P2", exchange="NSE",
            entry=250.0, qty=800, sl_pct=3.0, targets_pct=[8, 15], product=DEFAULT_PRODUCT
        ),
        PositionConfig(
            name="P3", ws_key="NSE|P3", tradingsymbol="P3", exchange="NSE",
            entry=50.0, qty=3000, sl_pct=5.0, targets_pct=[12], product=DEFAULT_PRODUCT
        ),
    ]
    # NOTE:
    # - Replace ws_key & tradingsymbol with real ones (e.g., "NSE|22" and "SBIN-EQ").
    # - They are dummy right now so you can edit them safely in UI before arming the bot.

    for cfg in examples:
        engine.add_position(cfg)


def app():
    st.subheader("🤖 Tradebot — Targets, Trailing SL, Open Risk")
    _ensure_engine()

    engine: PortfolioEngine = st.session_state[ENGINE_STATE_KEY]

    # --- Controls: Capital & Mode ---
    colA, colB, colC = st.columns([2, 2, 2])
    with colA:
        total_cap = st.number_input("Total Capital (₹)", min_value=1_00_000, step=50_000,
                                    value=int(engine.total_capital))
    with colB:
        dry_run = st.toggle("Dry Run (no live orders)", value=engine.dry_run, help="When ON, orders are simulated.")
    with colC:
        use_ws = st.toggle("Use WebSocket (preferred)", value=WS_AVAILABLE, help="If off/unavailable, falls back to REST polling.")

    # Update engine settings
    engine.total_capital = total_cap
    engine.dry_run = dry_run

    # --- Positions Config ---
    with st.expander("Positions (edit before starting)"):
        if not engine.positions:
            _preload_example_positions(engine)

        # Editable grid
        df_cfg = []
        for ws_key, ps in engine.positions.items():
            c = ps.cfg
            df_cfg.append({
                "Name": c.name, "WS Key": c.ws_key, "Tradingsymbol": c.tradingsymbol,
                "Exchange": c.exchange, "Entry": c.entry, "Qty": c.qty,
                "SL%": c.sl_pct, "Targets% (comma)": ", ".join(map(str, c.targets_pct)),
                "Product": c.product
            })
        cfg_df = pd.DataFrame(df_cfg)

        edited = st.data_editor(
            cfg_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Targets% (comma)": st.column_config.TextColumn(help="e.g. 10,20,30,40")
            },
            key="cfg_editor"
        )

        # Apply edits back into engine (recreate all positions)
        if st.button("💾 Apply Config"):
            engine.positions.clear()
            for _, row in edited.iterrows():
                try:
                    targets_pct = [float(x.strip()) for x in str(row["Targets% (comma)"]).split(",") if x.strip() != ""]
                except Exception:
                    targets_pct = []
                cfg = PositionConfig(
                    name=str(row["Name"]).strip(),
                    ws_key=str(row["WS Key"]).strip(),
                    tradingsymbol=str(row["Tradingsymbol"]).strip(),
                    exchange=str(row["Exchange"]).strip().upper(),
                    entry=_safe_float(row["Entry"], 0.0),
                    qty=int(_safe_float(row["Qty"], 0)),
                    sl_pct=_safe_float(row["SL%"], 0.0),
                    targets_pct=targets_pct,
                    product=str(row.get("Product", DEFAULT_PRODUCT)).strip() or DEFAULT_PRODUCT
                )
                engine.add_position(cfg)
            st.success("Config applied. Positions reset to initial SL/targets.")

    # --- Start/Stop Bot ---
    st.markdown("---")
    run_col, sub_col, inj_col = st.columns([1.2, 2, 2.2])

    ws_client = st.session_state.get("tradebot_ws_client")
    stop_event: threading.Event = st.session_state.get("tradebot_stop_event")

    with run_col:
        if st.button("▶️ Start Bot"):
            # Prepare subscriptions
            subscribe_keys = [ps.cfg.ws_key for ps in engine.positions.values()]
            if use_ws and WS_AVAILABLE:
                ws_client = _start_ws_if_needed(engine, subscribe_keys)
                st.session_state["tradebot_ws_client"] = ws_client
                st.session_state["tradebot_stop_event"] = None
                st.success("Bot started on WebSocket.")
            else:
                # Start polling thread
                stop_event = threading.Event()
                st.session_state["tradebot_stop_event"] = stop_event
                t = threading.Thread(target=_run_polling_loop, args=(engine, subscribe_keys, stop_event), daemon=True)
                t.start()
                st.warning("Bot running in REST polling mode (WS not available).")

        if st.button("⏹ Stop Bot"):
            # Stop polling
            if stop_event:
                stop_event.set()
                st.session_state["tradebot_stop_event"] = None
            # Close WS
            if ws_client:
                try:
                    ws_client.close()
                except Exception:
                    pass
                st.session_state["tradebot_ws_client"] = None
            st.info("Bot stopped.")

        st.caption("⚠️ Keep this page open while bot is running (esp. in polling mode).")

    with sub_col:
        st.write("**Order Audit (latest 15)**")
        if engine.order_book:
            ob_df = pd.DataFrame(engine.order_book).tail(15)
            st.dataframe(ob_df, use_container_width=True, height=260)
        else:
            st.info("No orders yet.")

    with inj_col:
        st.write("**Inject Test Tick (for quick simulation)**")
        ws_keys = [ps.cfg.ws_key for ps in engine.positions.values()]
        if ws_keys:
            s_key = st.selectbox("WS Key", ws_keys, key="inj_key")
            price = st.number_input("LTP", min_value=0.0, value=0.0, step=0.05, key="inj_price")
            if st.button("Inject"):
                engine.on_tick(s_key, price)
                st.success(f"Injected LTP {price} for {s_key}")

    # --- Process incoming WS ticks (if any) ---
    q: Queue = st.session_state[WS_TICK_EVENT_QUEUE_KEY]
    processed = 0
    while True:
        try:
            k, l = q.get_nowait()
            engine.on_tick(k, l)
            processed += 1
        except Empty:
            break
    if processed:
        st.caption(f"Processed {processed} tick(s).")

    # --- Portfolio Snapshot ---
    st.markdown("---")
    st.subheader("📊 Portfolio Snapshot")

    df = engine.to_dataframe()
    if df.empty:
        st.info("No positions configured.")
    else:
        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Capital", f"₹{engine.total_capital:,.0f}")
        c2.metric("Open Risk (₹)", f"₹{engine.portfolio_open_risk():,.0f}")
        c3.metric("Locked-in @Stop (₹)", f"₹{engine.portfolio_locked_in():,.0f}")
        c4.metric("Realized P&L (₹)", f"₹{engine.total_realized():,.0f}")

        # Styling for P&L
        def _pnl_style(v):
            try:
                x = float(v)
                if x > 0: return "background-color:#D6F5D6"
                if x < 0: return "background-color:#FFD6D6"
            except: pass
            return ""

        show_cols = [
            "Name","Exchange","WS Key","Tradingsymbol",
            "Entry","Qty (rem)","SL%","SL Price","Targets",
            "LTP","Next Trigger","Planned Sell Qty",
            "Open Risk (₹)","Open Risk (%Cap)","Locked-in @Stop (₹)",
            "Realized P&L (₹)","Achieved","Closed"
        ]
        st.dataframe(
            df[show_cols]
              .style.applymap(_pnl_style, subset=["Open Risk (₹)","Locked-in @Stop (₹)","Realized P&L (₹)"])
              .format({
                  "Entry":"{:.2f}","SL Price":"{:.2f}","LTP":"{:.2f}",
                  "Open Risk (₹)":"{:.2f}","Open Risk (%Cap)":"{:.2f}",
                  "Locked-in @Stop (₹)":"{:.2f}","Realized P&L (₹)":"{:.2f}"
              }),
            use_container_width=True, height=420
        )

    # --- Notes / Safety ---
    with st.expander("ℹ️ Notes & Safety"):
        st.markdown("""
- **Remaining-qty rule**: each target sells `rem / remaining_targets`. Last leg sells all remaining (no fractional qty).
- **Trailing SL**: start with initial SL%; after T1 → SL = Entry; after T2+ → SL = previous target price.
- **Gaps**: If price jumps across multiple targets, engine sells sequential legs in one tick loop (T1 then T2 ...).
- **Partial fills**: This page assumes instant fill at LTP (dry-run). For live fills, subscribe to *order update WS* in `ws_utils` and adjust `record_fill()` with actual `avgprc/flqty`.
- **REST fields**: SELL / MARKET / DAY / product=`CNC` by default. Adjust per your holdings (e.g., `NORMAL`/`INTRADAY`).
- **WebSocket keys**: Use `"NSE|<token>"` or `"NSE|<tradingsymbol>"`. Replace placeholders like `NSE|P1` with real ones (e.g., `NSE|22` and `SBIN-EQ`).
- **Dry Run** ON by default. Turn OFF only when you're ready for live orders.
        """)

