import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="BTC Signal Engine", page_icon="📈", layout="centered")
st.title("📈 BTC Live Signal Engine")

@st.cache_data(ttl=300)
def fetch_btc_data():
    df = yf.download("BTC-USD", period="100d", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

try:
    df = fetch_btc_data()
    close, high, low = df['Close'], df['High'], df['Low']

    window, window_dev = 20, 2.0
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    lower_band = ma - (window_dev * std)
    upper_band = ma + (window_dev * std)

    tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
    atr = tr.rolling(14).mean()

    curr_p, curr_l = float(close.iloc[-1]), float(lower_band.iloc[-1])
    curr_m, curr_u = float(ma.iloc[-1]), float(upper_band.iloc[-1])
    curr_atr = float(atr.iloc[-1])

    st.metric("Live Bitcoin Price", f"${curr_p:,.2f}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Lower Band", f"${curr_l:,.2f}")
    col2.metric("20 MA Mean", f"${curr_m:,.2f}")
    col3.metric("Upper Band", f"${curr_u:,.2f}")

    st.markdown("---")

    if curr_p < curr_l:
        sl = curr_p - (1.5 * curr_atr)
        tp1, tp2 = curr_m, curr_u
        st.error("🚀 BUY / LONG SIGNAL TRIGGERED")
        c1, c2 = st.columns(2)
        c1.metric("Suggested Entry", f"${curr_p:,.2f}")
        c1.metric("Stop Loss (SL)", f"${sl:,.2f}")
        c2.metric("Take Profit 1 (TP1)", f"${tp1:,.2f}")
        c2.metric("Take Profit 2 (TP2)", f"${tp2:,.2f}")
    elif curr_p > curr_u:
        sl = curr_p + (1.5 * curr_atr)
        tp1, tp2 = curr_m, curr_l
        st.warning("📉 SELL / SHORT SIGNAL TRIGGERED")
        c1, c2 = st.columns(2)
        c1.metric("Suggested Entry", f"${curr_p:,.2f}")
        c1.metric("Stop Loss (SL)", f"${sl:,.2f}")
        c2.metric("Take Profit 1 (TP1)", f"${tp1:,.2f}")
        c2.metric("Take Profit 2 (TP2)", f"${tp2:,.2f}")
    else:
        st.info("⚡ STATUS: NEUTRAL / NO TRADE")
        st.caption("Price is currently inside normal volatility bands. Wait for a breakout.")

except Exception as e:
    st.error(f"Data Fetching Error: {e}")
