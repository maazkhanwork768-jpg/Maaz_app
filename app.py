import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Crypto Signal Engine", page_icon="📈", layout="centered")

st.title("📈 Multi-Coin Signal Engine")

popular_coins = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", 
    "AVAX", "LINK", "SUI", "NEAR", "PEPE", "SHIB", "APT", "DOT", "LTC"
]

col_select, col_custom = st.columns([2, 1])

with col_select:
    selected_coin = st.selectbox("Select Binance Coin:", popular_coins, index=0)

with col_custom:
    custom_coin = st.text_input("Or type symbol:", value="").strip().upper()

coin_symbol = custom_coin if custom_coin else selected_coin
ticker = f"{coin_symbol}-USD"

@st.cache_data(ttl=180)
def fetch_crypto_data(symbol_ticker):
    df = yf.download(symbol_ticker, period="100d", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

try:
    df = fetch_crypto_data(ticker)
    
    if df.empty or len(df) < 20:
        st.error(f"Could not fetch data for '{coin_symbol}'. Check ticker symbol.")
    else:
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

        def fmt_price(val):
            return f"${val:,.6f}" if val < 1 else f"${val:,.2f}"

        st.subheader(f"📊 {coin_symbol} Market Analysis")
        st.metric(f"Live {coin_symbol} Price", fmt_price(curr_p))

        col1, col2, col3 = st.columns(3)
        col1.metric("Lower Band", fmt_price(curr_l))
        col2.metric("20 MA Mean", fmt_price(curr_m))
        col3.metric("Upper Band", fmt_price(curr_u))

        st.markdown("---")

        if curr_p < curr_l:
            sl = curr_p - (1.5 * curr_atr)
            tp1, tp2 = curr_m, curr_u
            st.error(f"🚀 BUY / LONG SIGNAL TRIGGERED FOR {coin_symbol}")
            c1, c2 = st.columns(2)
            c1.metric("Suggested Entry", fmt_price(curr_p))
            c1.metric("Stop Loss (SL)", fmt_price(sl))
            c2.metric("Take Profit 1 (TP1)", fmt_price(tp1))
            c2.metric("Take Profit 2 (TP2)", fmt_price(tp2))
        elif curr_p > curr_u:
            sl = curr_p + (1.5 * curr_atr)
            tp1, tp2 = curr_m, curr_l
            st.warning(f"📉 SELL / SHORT SIGNAL TRIGGERED FOR {coin_symbol}")
            c1, c2 = st.columns(2)
            c1.metric("Suggested Entry", fmt_price(curr_p))
            c1.metric("Stop Loss (SL)", fmt_price(sl))
            c2.metric("Take Profit 1 (TP1)", fmt_price(tp1))
            c2.metric("Take Profit 2 (TP2)", fmt_price(tp2))
        else:
            st.info(f"⚡ STATUS FOR {coin_symbol}: NEUTRAL / NO TRADE")
            st.caption("Price is currently inside normal volatility bands. Wait for a breakout.")

except Exception as e:
    st.error(f"Data Fetching Error for {coin_symbol}: {e}")
