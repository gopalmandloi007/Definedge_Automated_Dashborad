import logging
from session_utils import get_client_session
from quotes import get_circuit_limits
from holdings import get_holdings
from positions import get_positions
from utils import integrate_post

logging.basicConfig(level=logging.INFO)

def snap_to_tick(price, tick_size):
    # Snap price to nearest tick
    return round(round(price / tick_size) * tick_size, 2)

def can_place_gtt(symbol, trigger_price):
    lower, upper = get_circuit_limits(symbol)
    if not (lower <= trigger_price <= upper):
        logging.error(f"GTT order rejected: {symbol} trigger price {trigger_price} outside circuit limits ({lower}-{upper})")
        return False, "CIRCUIT LIMIT ERROR"
    return True, ""

def extract_qty(holding):
    qty = int(float(holding.get("dp_qty", "0") or 0))
    if qty == 0:
        qty = int(float(holding.get("t1_qty", "0") or 0))
    return qty

def place_oco_order(symbol, exchange, qty, entry_price, tick_size, product_type="CNC", remarks="Auto OCO"):
    sl_price = snap_to_tick(entry_price * 0.98, tick_size)
    tgt_price = snap_to_tick(entry_price * 1.12, tick_size)
    # Qty split (half-half, odd will go to SL)
    tgt_qty = qty // 2
    sl_qty = qty - tgt_qty

    # Circuit check
    sl_ok, _ = can_place_gtt(symbol, sl_price)
    tgt_ok, _ = can_place_gtt(symbol, tgt_price)
    if not sl_ok and not tgt_ok:
        logging.warning(f"Skipping {symbol}: Both SL and Target outside circuit.")
        return
    payload = {
        "tradingsymbol": symbol,
        "exchange": exchange,
        "order_type": "SELL",
        "product_type": product_type,
        "target_price": str(tgt_price),
        "stoploss_price": str(sl_price),
        "target_quantity": int(tgt_qty),
        "stoploss_quantity": int(sl_qty),
        "remarks": remarks
    }
    resp = integrate_post("/ocoplaceorder", payload)
    if resp.get("status", "").upper() == "ERROR":
        logging.error(f"{symbol} OCO order failed: {resp.get('message', resp)}")
    else:
        logging.info(f"{symbol} OCO Order submitted! {resp}")
    return resp

def main():
    try:
        positions = get_positions() or []
    except Exception:
        positions = []
    try:
        holdings = get_holdings() or []
    except Exception:
        holdings = []
    # POSITIONS
    for p in positions:
        symbol = p.get("tradingsymbol") or p.get("symbol")
        qty = int(float(p.get("net_quantity") or p.get("netqty") or p.get("quantity") or p.get("Qty") or 0))
        if qty <= 0:
            continue
        exchange = p.get("exchange")
        product_type = p.get("product_type") or p.get("productType") or p.get("Product") or "INTRADAY"
        entry_price = float(p.get("day_buy_avg") or p.get("total_buy_avg") or 0.0)
        tick_size = float(p.get("ticksize") or 0.05)
        if entry_price > 0:
            place_oco_order(symbol, exchange, qty, entry_price, tick_size, product_type)

    # HOLDINGS (NSE only)
    for h in holdings:
        avg_buy_price = float(h.get("avg_buy_price", "0.0"))
        qty = extract_qty(h)
        if qty <= 0:
            continue
        for ts_info in h.get("tradingsymbol", []):
            if ts_info.get("exchange") != "NSE":
                continue
            symbol = ts_info.get("tradingsymbol", "")
            exchange = ts_info.get("exchange", "")
            tick_size = float(ts_info.get("ticksize", "0.05"))
            product_type = "CNC"
            entry_price = avg_buy_price if avg_buy_price > 0.0 else 0.0
            if entry_price > 0:
                place_oco_order(symbol, exchange, qty, entry_price, tick_size, product_type)

if __name__ == "__main__":
    main()
