import streamlit as st
import pandas as pd
from utils import integrate_get

@st.cache_data
def load_master():
    # Supports both 14 and 15 column master.csv automatically
    df = pd.read_csv("master.csv", sep="\t", header=None)
    if df.shape[1] == 15:
        df.columns = [
            "segment", "token", "symbol", "symbol_series", "series", "unknown1",
            "unknown2", "unknown3", "series2", "unknown4", "unknown5", "unknown6",
            "isin", "unknown7", "company"
        ]
        return df[["segment", "token", "symbol", "symbol_series", "series"]]
    else:  # legacy 14-column
        df.columns = [
            "segment", "token", "symbol", "instrument", "series", "isin1",
            "facevalue", "lot", "something", "zero1", "two1", "one1", "isin", "one2"
        ]
        return df[["segment", "token", "symbol", "instrument", "series"]]

def get_token_by_symbol(symbol, exchange, master_df):
    symbol = symbol.strip().upper()
    exchange = exchange.strip().upper()
    # Try symbol first
    row = master_df[(master_df['symbol'].str.upper() == symbol) & (master_df['segment'].str.upper() == exchange)]
    if not row.empty:
        return row.iloc[0]['token']
    # Try symbol_series (for indices in 15-col)
    if "symbol_series" in master_df.columns:
        row2 = master_df[(master_df['symbol_series'].str.upper() == symbol) & (master_df['segment'].str.upper() == exchange)]
        if not row2.empty:
            return row2.iloc[0]['token']
    # Try instrument (for 14-col)
    if "instrument" in master_df.columns:
        row3 = master_df[(master_df['instrument'].str.upper() == symbol) & (master_df['segment'].str.upper() == exchange)]
        if not row3.empty:
            return row3.iloc[0]['token']
    return None

def render_quotes(data):
    if not data or "status" not in data:
        st.warning("No data returned.")
        return
    st.markdown(
        f"""
        <div style='background:#F1FAFF;border-radius:10px;padding:16px 18px 8px 18px;box-shadow:0 2px 8px #e0e8f0;margin-bottom:16px;'>
        <h3 style='margin-bottom:4px;'>{data.get('company_name','-')} <span style='font-size:1.1rem;color:#888'>({data.get('tradingsymbol','-')})</span></h3>
        <span style='font-size:1.15rem;color:#005ff9;font-weight:600;'>₹ {data.get('ltp','-')}</span>
        <span style='background:#e8f6ff;color:#333;padding:2px 10px 2px 10px;margin-left:18px;border-radius:7px;font-size:0.98rem;'>{data.get('exchange','-')} / {data.get('instrument_name','-')}</span>
        <hr style='margin:10px 0 6px 0;'/>
        <div style='display:flex;flex-wrap:wrap;gap:18px;font-size:1rem;'>
            <div><b>ISIN:</b> <span style='color:#174;'> {data.get('isin','-')}</span></div>
            <div><b>Lot Size:</b> <span style='color:#174;'> {data.get('lotsize','-')}</span></div>
            <div><b>Tick Size:</b> <span style='color:#174;'> {data.get('ticksize','-')}</span></div>
            <div><b>Precision:</b> <span style='color:#174;'> {data.get('price_precision','-')}</span></div>
            <div><b>Upper Circuit:</b> <span style='color:#f80;'> {data.get('upper_circuit','-')}</span></div>
            <div><b>Lower Circuit:</b> <span style='color:#f80;'> {data.get('lower_circuit','-')}</span></div>
        </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    with st.expander("Show All Data (Quotes Response)", expanded=False):
        st.json(data)

def render_security_info(data):
    if not data or "status" not in data:
        st.warning("No data returned.")
        return
    st.markdown(
        f"""
        <div style='background:#F9F9F9;border-radius:10px;padding:16px 18px 8px 18px;box-shadow:0 2px 8px #e0e8f0;margin-bottom:16px;'>
        <h4 style='margin-bottom:4px;'>{data.get('company_name','-')} <span style='font-size:1.1rem;color:#888'>({data.get('tradingsymbol','-')})</span></h4>
        <span style='background:#e8f6ff;color:#333;padding:2px 10px 2px 10px;margin-left:0;border-radius:7px;font-size:0.99rem;'>
            {data.get('exchange','-')} / {data.get('instrument_name','-')}
        </span>
        <hr style='margin:10px 0 6px 0;'/>
        <div style='display:flex;flex-wrap:wrap;gap:18px;font-size:1rem;'>
            <div><b>ISIN:</b> <span style='color:#174;'> {data.get('isin','-')}</span></div>
            <div><b>Lot Size:</b> <span style='color:#174;'> {data.get('lotsize','-')}</span></div>
            <div><b>Tick Size:</b> <span style='color:#174;'> {data.get('ticksize','-')}</span></div>
            <div><b>Precision:</b> <span style='color:#174;'> {data.get('price_precision','-')}</span></div>
            <div><b>Freeze Qty:</b> <span style='color:#f80;'>{data.get('freeze_qty','-')}</span></div>
            <div><b>Delivery Margin:</b> <span style='color:#d40;'>{data.get('deliveryMargin','-')}</span></div>
            <div><b>Var Margin:</b> <span style='color:#d40;'>{data.get('varMargin','-')}</span></div>
            <div><b>ELM Margin:</b> <span style='color:#d40;'>{data.get('elmMargin','-')}</span></div>
            <div><b>Issue Date:</b> <span style='color:#333;'>{data.get('issueDate','-')}</span></div>
            <div><b>Listing Date:</b> <span style='color:#333;'>{data.get('listingDate','-')}</span></div>
        </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    with st.expander("Show All Data (Security Info Response)", expanded=False):
        st.json(data)

def show():
    st.header("Get Quotes / Security Info")

    master_df = load_master()
    exchange = st.selectbox("Exchange", sorted(master_df["segment"].unique()), index=0)
    # Symbol dropdown, only for selected exchange, sorted
    df_exch = master_df[master_df["segment"] == exchange]
    symbol_list = sorted(df_exch["symbol"].dropna().unique().tolist())
    symbol = st.selectbox("Symbol", symbol_list, index=0)

    token = get_token_by_symbol(symbol, exchange, master_df)
    if not token:
        st.warning("Symbol-token mapping not found in master file. Try another symbol.")
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get Quotes"):
            try:
                data = integrate_get(f"/quotes/{exchange}/{token}")
                render_quotes(data)
            except Exception as e:
                st.error(f"Error fetching quotes: {e}")
    with col2:
        if st.button("Get Security Info"):
            try:
                data = integrate_get(f"/securityinfo/{exchange}/{token}")
                render_security_info(data)
            except Exception as e:
                st.error(f"Error fetching security info: {e}")

if __name__ == "__main__":
    show()
