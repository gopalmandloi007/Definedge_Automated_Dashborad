import streamlit as st
from utils import integrate_get, integrate_post
import requests

def norm_status(s):
    return str(s).replace(" ", "_").upper()

def cancel_order(order_id):
    api_session_key = st.secrets.get("integrate_api_session_key", "")
    url = f"https://integrate.definedgesecurities.com/dart/v1/cancel/{order_id}"
    headers = {"Authorization": api_session_key}
    resp = requests.get(url, headers=headers)
    try:
        result = resp.json()
    except Exception:
        result = {"status": "ERROR", "message": "Invalid API response"}
    return result

@st.cache_data(show_spinner=False)
def get_ltp(tradingsymbol, exchange, api_session_key):
    try:
        url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{exchange}/{tradingsymbol}"
        headers = {"Authorization": api_session_key}
        resp = requests.get(url, headers=headers, timeout=2)
        if resp.status_code == 200:
            ltp_val = resp.json().get("ltp", None)
            return float(ltp_val) if ltp_val is not None else "N/A"
    except Exception:
        pass
    return "N/A"

def show():
    st.header("Orders Book & Manage")

    # Fetch orders
    data = integrate_get("/orders")
    orderlist = data.get("orders", [])
    open_statuses = {"OPEN", "PARTIALLY_FILLED", "TRIGGER_PENDING"}
    open_orders = [o for o in orderlist if norm_status(o.get("order_status", "")) in open_statuses]

    if not open_orders:
        st.info("No open/partial/trigger pending orders found.")
        return

    # Track selection state — one per order_id
    if "order_selection" not in st.session_state:
        st.session_state["order_selection"] = {}
    order_selection = st.session_state["order_selection"]

    # Utility: update selection for all visible orders
    def set_all(val):
        for order in open_orders:
            order_selection[order["order_id"]] = val

    st.markdown("""
    <style>
    label, .stNumberInput label, .stRadio label, .stCheckbox label { font-size:12px !important; font-family:Arial, sans-serif; }
    .stNumberInput input, .stTextInput input { font-size:12px !important; height:26px !important; padding:2px 4px !important; min-width:40px !important; max-width:60px !important;}
    </style>
    """, unsafe_allow_html=True)

    # Action buttons for selection/cancel
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Select All"):
        set_all(True)
    if col2.button("Deselect All"):
        set_all(False)
    if col3.button("Cancel Selected"):
        selected_ids = [oid for oid, sel in order_selection.items() if sel]
        if not selected_ids:
            st.warning("No orders selected.")
        else:
            for oid in selected_ids:
                result = cancel_order(oid)
                if result.get("status") == "ERROR":
                    st.error(f"Cancel Failed [{oid}]: {result.get('message','Error')}")
                else:
                    st.success(f"Order {oid} cancelled!")
            st.rerun()
    if col4.button("Cancel All"):
        for order in open_orders:
            oid = order["order_id"]
            result = cancel_order(oid)
            if result.get("status") == "ERROR":
                st.error(f"Cancel Failed [{oid}]: {result.get('message','Error')}")
            else:
                st.success(f"Order {oid} cancelled!")
        st.rerun()

    # Table columns to show
    cols = [
        "order_id", "tradingsymbol", "order_type", "quantity", 
        "price_type", "price", "trigger_price", "ltp", 
        "product_type", "order_status", "exchange", "validity"
    ]
    col_labels = [
        "Select", "Order ID", "Symbol", "Side", "Qty", "Type", "Price", 
        "Trigger Price", "LTP", 
        "Product", "Status", "Exch", "Validity", "Modify", "Cancel"
    ]
    col_widths = [0.7, 1.3, 1.2, 0.8, 0.7, 1, 0.8, 0.9, 0.9, 0.9, 1, 1.3, 0.8, 0.7, 1.2, 1.1]

    api_session_key = st.secrets.get("integrate_api_session_key", "")

    modify_id = st.session_state.get("modify_id", None)
    # If one row is being modified, show only that form (fast UI)
    if modify_id:
        order = next((o for o in open_orders if o["order_id"] == modify_id), None)
        if order:
            st.markdown("---")
            st.subheader(f"Modify Order: {order['tradingsymbol']} ({order['order_id']})")
            price_type_options = ["LIMIT", "MARKET", "SL-LIMIT", "SL-MARKET"]
            def match_price_type(pt):
                pt_norm = str(pt).replace("_", "-").replace(" ", "-").upper()
                for idx, opt in enumerate(price_type_options):
                    if pt_norm == opt:
                        return idx
                pt_simple = pt_norm.replace("-", "")
                for idx, opt in enumerate(price_type_options):
                    if pt_simple == opt.replace("-", ""):
                        return idx
                return 0
            price_type_idx = match_price_type(order.get("price_type", "LIMIT"))
            product_options = ["CNC", "INTRADAY", "NORMAL"]
            product_idx = product_options.index(order.get("product_type", "CNC")) if order.get("product_type", "CNC") in product_options else 0
            validity_options = ["DAY", "EOS", "IOC"]
            validity_idx = validity_options.index(order.get("validity", "DAY")) if order.get("validity", "DAY") in validity_options else 0
            with st.form(f"mod_form_{order['order_id']}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_qty = st.number_input("Qty", min_value=1, value=int(order["quantity"]), key=f"qty_{order['order_id']}")
                    new_price = st.number_input("Price", min_value=0.0, value=float(order["price"]), key=f"price_{order['order_id']}")
                    new_trigger_price = st.number_input("Trigger Price", min_value=0.0, value=float(order.get("trigger_price", 0)), key=f"trgprice_{order['order_id']}")
                with col2:
                    new_price_type = st.selectbox(
                        "Type", price_type_options, index=price_type_idx, key=f"ptype_{order['order_id']}"
                    )
                    new_product = st.selectbox(
                        "Product", product_options, index=product_idx, key=f"prod_{order['order_id']}"
                    )
                with col3:
                    new_validity = st.selectbox(
                        "Validity", validity_options, index=validity_idx, key=f"val_{order['order_id']}"
                    )
                colf1, colf2 = st.columns(2)
                with colf1:
                    submit = st.form_submit_button("✓ Confirm")
                with colf2:
                    cancel = st.form_submit_button("✗ Cancel")
                if submit:
                    payload = {
                        "exchange": order.get('exchange', ''),
                        "order_id": order['order_id'],
                        "tradingsymbol": order.get('tradingsymbol', ''),
                        "quantity": str(new_qty),
                        "price": str(new_price),
                        "trigger_price": str(new_trigger_price),
                        "product_type": new_product,
                        "order_type": order.get('order_type', ''),
                        "price_type": new_price_type,
                        "validity": new_validity
                    }
                    resp = integrate_post("/modify", payload)
                    if resp.get("status") == "ERROR":
                        st.error(f"Modify Failed: {resp.get('message','Error')}")
                    else:
                        st.success("Order modification submitted!")
                    st.session_state["modify_id"] = None
                    st.rerun()
                if cancel:
                    st.session_state["modify_id"] = None
                    # No rerun needed, just return
                    return
            return  # Only show form, not table

    # Table header
    columns = st.columns(col_widths)
    for i, label in enumerate(col_labels):
        columns[i].markdown(f"**{label}**")
    # Table rows
    for order in open_orders:
        columns = st.columns(col_widths)
        # Checkbox for selection
        selected = order_selection.get(order["order_id"], False)
        columns[0].checkbox("", value=selected, key=f"select_{order['order_id']}")
        order_selection[order["order_id"]] = st.session_state[f"select_{order['order_id']}"]
        # Show order fields
        for i, key in enumerate(cols):
            if key == "ltp":
                tradingsymbol = order.get("tradingsymbol", "")
                exchange = order.get("exchange", "")
                ltp_val = get_ltp(tradingsymbol, exchange, api_session_key)
                columns[i+1].write(ltp_val)
            else:
                value = order.get(key, "N/A")
                columns[i+1].write(value)
        # Modify button
        if columns[-2].button("Modify", key=f"mod_btn_{order['order_id']}"):
            st.session_state["modify_id"] = order["order_id"]
            # Do NOT call st.rerun() here for fast UI
        # Cancel button
        if columns[-1].button("Cancel", key=f"cancel_btn_{order['order_id']}"):
            result = cancel_order(order['order_id'])
            if result.get("status") == "ERROR":
                st.error(f"Cancel Failed: {result.get('message','Error')}")
            else:
                st.success("Order cancelled!")
            st.rerun()

if __name__ == "__main__":
    show()
