import streamlit as st
from utils import integrate_get, integrate_post

def extract_first_valid(d, keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}, "null"):
            return v
    return default

def extract_qty(pos):
    for k in ['netqty', 'net_quantity', 'net_qty', 'quantity', 'Qty']:
        v = pos.get(k)
        if v is not None and v != "":
            try:
                return int(float(v))
            except Exception:
                continue
    return 0

def squareoff_form(item, qty, ts_info, is_position=False):
    label = "Position" if is_position else "Holding"
    unique_id = f"{label}_{ts_info['tradingsymbol']}"

    qty_option = st.radio(
        f"Quantity to Square Off for {ts_info['tradingsymbol']}",
        ["Full", "Partial"],
        horizontal=True,
        key=f"qtyopt_{unique_id}"
    )

    if qty_option == "Partial":
        squareoff_qty = st.number_input(
            "Enter quantity to square off",
            min_value=1,
            max_value=int(qty),
            value=1,
            key=f"squareoffqty_{unique_id}"
        )
    else:
        squareoff_qty = int(qty)

    price_option = st.radio(
        "Order Type",
        ["Market Order", "Limit Order"],
        horizontal=True,
        key=f"pricetype_{unique_id}"
    )

    # Correct default price for limit orders
    if is_position:
        net_qty = extract_qty(item)
        if net_qty > 0:
            default_price = float(
                extract_first_valid(item, ["day_buy_avg", "total_buy_avg"], 0)
            )
        else:
            default_price = float(
                extract_first_valid(item, ["day_sell_avg", "total_sell_avg"], 0)
            )
    else:
        default_price = float(
            extract_first_valid(item, ["avg_buy_price", "average_price", "buy_avg_price"], 0)
        )

    if price_option == "Limit Order":
        squareoff_price = st.number_input(
            "Limit Price (₹)", min_value=0.01, value=round(default_price, 2), key=f"price_{unique_id}"
        )
        price_type = "LIMIT"
    else:
        squareoff_price = 0.0
        price_type = "MARKET"

    validity = st.selectbox("Order Validity", ["DAY", "IOC", "EOS"], index=0, key=f"validity_{unique_id}")
    remarks = st.text_input("Remarks (optional)", key=f"remarks_{unique_id}")

    disclose = st.checkbox("Disclose Partial Quantity?", key=f"disclose_{unique_id}")
    if disclose:
        disclosed_quantity = st.number_input(
            "Disclosed Quantity (optional)", min_value=1, max_value=int(squareoff_qty), value=1, key=f"discloseqty_{unique_id}"
        )
    else:
        disclosed_quantity = None

    st.markdown("---")
    with st.form(f"squareoff_form_{unique_id}"):
        submitted = st.form_submit_button("🟢 Place Square Off Order")
        if submitted:
            payload = {
                "exchange": ts_info['exchange'],
                "tradingsymbol": ts_info["tradingsymbol"],
                "order_type": "SELL",
                "quantity": str(squareoff_qty),
                "price": str(squareoff_price),
                "price_type": price_type,
                "product_type": "CNC",
                "validity": validity,
            }
            if remarks:
                payload["remarks"] = remarks
            if disclosed_quantity:
                payload["disclosed_quantity"] = str(disclosed_quantity)
            with st.spinner("Placing order..."):
                resp = integrate_post("/placeorder", payload)
            status = resp.get('status') or resp.get('message') or resp
            if resp.get("status") == "ERROR":
                st.error(f"Order Failed: {resp.get('message','Error')}")
            else:
                st.success(f"Order Response: {status}")
            st.session_state["sq_id"] = None
            st.session_state["sqp_id"] = None
            st.rerun()

def show():
    st.title("⚡ Definedge Integrate Dashboard")
    st.subheader("💼 Square Off Positions & Holdings")
    st.markdown("---")
    # --- Holdings Table ---
    st.header("📦 Holdings")
    data = integrate_get("/holdings")
    holdings = data.get("data", [])

    hold_cols = ["tradingsymbol", "exchange", "isin", "dp_qty", "t1_qty", "avg_buy_price", "haircut"]
    col_labels = ["Symbol", "Exch", "ISIN", "DP Qty", "T1 Qty", "Avg Price", "Haircut"]
    st.markdown("#### Holdings List")
    columns = st.columns([1.5, 1.2, 1.5, 1.1, 1.1, 1.2, 1.1, 1.2])
    for i, label in enumerate(col_labels):
        columns[i].markdown(f"**{label}**")
    columns[-1].markdown("**Square Off**")

    user_holdings = []
    for h in holdings:
        qty = int(float(h.get("dp_qty", 0) or 0))
        tradingsymbols = h.get("tradingsymbol", [])
        if qty > 0 and tradingsymbols and isinstance(tradingsymbols, list):
            user_holdings.append((h, qty, tradingsymbols))
    if not user_holdings:
        st.info("No holdings to square off.")
    else:
        sq_id = st.session_state.get("sq_id", None)
        for idx, (holding, qty, tradingsymbols) in enumerate(user_holdings):
            ts_info = tradingsymbols[0]
            columns = st.columns([1.5, 1.2, 1.5, 1.1, 1.1, 1.2, 1.1, 1.2])
            for i, key in enumerate(hold_cols):
                val = ts_info.get(key) if key in ts_info else holding.get(key)
                columns[i].write(val)
            if columns[-1].button("Square Off", key=f"squareoff_btn_{ts_info['tradingsymbol']}"):
                st.session_state["sq_id"] = f"HOLD_{idx}"
                st.session_state["sqp_id"] = None
                st.rerun()
            if sq_id == f"HOLD_{idx}":
                squareoff_form(holding, qty, ts_info, is_position=False)

    # --- Positions Table ---
    st.header("📝 Positions")
    pdata = integrate_get("/positions")
    positions = pdata.get("positions") or pdata.get("data") or []

    col_labels = ["Symbol", "Exch", "Product", "Qty", "Buy Avg", "Sell Avg", "Net Qty", "PnL"]
    st.markdown("#### Positions List")
    columns = st.columns([1.5, 1.2, 1.2, 1, 1.2, 1.2, 1, 1.3, 1.2])
    for i, label in enumerate(col_labels):
        columns[i].markdown(f"**{label}**")
    columns[-1].markdown("**Square Off**")

    user_positions = []
    for p in positions:
        qty = extract_qty(p)
        if qty != 0:
            user_positions.append(p)
    sqp_id = st.session_state.get("sqp_id", None)
    if not user_positions:
        st.info("No open positions to square off.")
    else:
        for idx, pos in enumerate(user_positions):
            columns = st.columns([1.5, 1.2, 1.2, 1, 1.2, 1.2, 1, 1.3, 1.2])
            net_qty = extract_qty(pos)
            # Show correct Buy Avg / Sell Avg based on position side
            if net_qty > 0:
                buy_avg = extract_first_valid(pos, ["day_buy_avg", "total_buy_avg"], "-")
                sell_avg = "-"
            elif net_qty < 0:
                buy_avg = "-"
                sell_avg = extract_first_valid(pos, ["day_sell_avg", "total_sell_avg"], "-")
            else:
                buy_avg = "-"
                sell_avg = "-"
            col_vals = [
                extract_first_valid(pos, ["tradingsymbol", "symbol"], "-"),
                extract_first_valid(pos, ["exchange"], "-"),
                extract_first_valid(pos, ["product_type", "productType", "Product"], "-"),
                str(net_qty),
                buy_avg,
                sell_avg,
                str(net_qty),
                extract_first_valid(pos, ["pnl", "unrealized_pnl", "Unrealised P&L"], "-"),
            ]
            for i, val in enumerate(col_vals):
                columns[i].write(val)
            if columns[-1].button("Square Off", key=f"squareoff_btn_pos_{extract_first_valid(pos,['tradingsymbol','symbol'],'')}_{idx}"):
                st.session_state["sqp_id"] = f"POS_{idx}"
                st.session_state["sq_id"] = None
                st.rerun()
            if sqp_id == f"POS_{idx}":
                ts_info = {
                    "tradingsymbol": extract_first_valid(pos, ["tradingsymbol","symbol"]),
                    "exchange": extract_first_valid(pos, ["exchange"]),
                    "isin": extract_first_valid(pos, ["isin"], ""),
                }
                qty = abs(extract_qty(pos))
                squareoff_form(pos, qty, ts_info, is_position=True)

if __name__ == "__main__":
    show()
