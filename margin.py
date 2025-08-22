import streamlit as st
from utils import integrate_post
import pandas as pd
import json

@st.cache_data
def load_master_symbols():
    df = pd.read_csv("master.csv", sep="\t", header=None)
    # Handles both 14 and 15 column master files
    if df.shape[1] == 15:
        df.columns = [
            "segment", "token", "symbol", "symbol_series", "series", "unknown1",
            "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
            "isin", "unknown7", "company"
        ]
        df = df[["symbol", "series", "segment"]]
    else:
        df.columns = [
            "segment", "token", "symbol", "instrument", "series", "isin1",
            "facevalue", "lot", "something", "zero1", "two1", "one1", "isin", "one2"
        ]
        df = df[["symbol", "series", "segment"]]
    # Only EQ & BE series, and only NSE/BSE stocks (not derivatives, indices)
    df = df[df["series"].isin(["EQ", "BE"])]
    df = df[df["segment"].isin(["NSE", "BSE"])]
    df = df.drop_duplicates(subset=["symbol", "series"])
    return df.sort_values("symbol")

def show():
    st.header("Basket Margin Calculator")
    st.write("Calculate required margin for a basket of orders.")

    master_df = load_master_symbols()
    symbol_list = master_df["symbol"].unique().tolist()
    symbol_default = "SBIN" if "SBIN" in symbol_list else symbol_list[0] if symbol_list else ""

    # Basket builder UI
    st.markdown("#### Add Order to Basket")
    with st.form("add_basket_item"):
        col1, col2, col3 = st.columns(3)
        with col1:
            symbol = st.selectbox("Symbol", symbol_list, index=symbol_list.index(symbol_default) if symbol_default in symbol_list else 0)
            symbol_rows = master_df[master_df["symbol"] == symbol]
            exchange_options = symbol_rows["segment"].unique().tolist()
            exchange = st.selectbox("Exchange", exchange_options, index=0)
        with col2:
            order_type = st.selectbox("Order Type", ["BUY", "SELL"])
            price_type = st.selectbox("Price Type", ["MARKET", "LIMIT"])
            product_type = st.selectbox("Product Type", ["CNC", "INTRADAY", "NORMAL"])
        with col3:
            qty = st.number_input("Quantity", min_value=1, value=1, step=1)
            price = st.number_input("Price (for LIMIT)", min_value=0.0, value=0.0, step=0.05, format="%.2f")
        add_item = st.form_submit_button("Add to Basket")

    # Session state for basket orders
    if "basket_orders" not in st.session_state:
        st.session_state["basket_orders"] = []

    # Add symbol to basket on form submit
    if add_item:
        st.session_state["basket_orders"].append({
            "tradingsymbol": f"{symbol}-EQ", # You can enhance for BE/other series if needed
            "exchange": exchange,
            "order_type": order_type,
            "price": price,
            "price_type": price_type,
            "product_type": product_type,
            "quantity": qty
        })

    st.markdown("#### Basket Orders")
    basket_orders = st.session_state.get("basket_orders", [])
    if basket_orders:
        st.dataframe(pd.DataFrame(basket_orders))
    else:
        st.info("No orders in basket yet.")

    # Calculate margin for basket
    with st.form("basket_margin"):
        st.markdown("##### Edit Basket (JSON, advanced users only)")
        basket_str = st.text_area("Basket Orders JSON (list)", value=json.dumps(basket_orders, indent=2), height=150)
        submit = st.form_submit_button("Calculate Margin")
        if submit:
            try:
                basket = json.loads(basket_str)
                if not isinstance(basket, list):
                    raise ValueError("Input must be a list of order dicts.")
                data = {"basketlists": basket}
                resp = integrate_post("/margin", data)
                st.success("Margin calculation successful!")
                st.json(resp)
            except json.JSONDecodeError:
                st.error("Invalid JSON format. Please check your input.")
            except Exception as e:
                st.error(f"Error: {e}")

    # Clear basket option
    if st.button("Clear Basket"):
        st.session_state["basket_orders"] = []
        st.success("Basket cleared.")

if __name__ == "__main__":
    show()
