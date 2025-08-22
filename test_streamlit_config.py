import streamlit as st

st.set_page_config(
    page_title="Streamlit Config Test",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Streamlit Config Test")
st.write("✅ Agar aapko ye message dikh raha hai, aur koi set_page_config error nahi, toh config bilkul sahi hai!")

if st.button("Click me!"):
    st.success("Button click works!")

st.info("Bas yahi file chalani hai. Agar error aaye toh poora error message paste karo.")
