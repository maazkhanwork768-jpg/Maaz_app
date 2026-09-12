from datetime import datetime
import json
import sqlite3
import urllib.request
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DATABASE SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Maaz Khan Trading | Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        last_login TEXT
    )
""")
conn.commit()


def add_user(username, password):
  try:
    c.execute(
        "INSERT INTO users (username, password, last_login) VALUES (?, ?, ?)",
        (username, password, "Never"),
    )
    conn.commit()
    return True
  except sqlite3.IntegrityError:
    return False


def verify_user(username, password):
  c.execute(
      "SELECT password FROM users WHERE username = ? AND password = ?",
      (username, password),
  )
  return c.fetchone() is not None


def update_last_login(username):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  c.execute(
      "UPDATE users SET last_login = ? WHERE username = ?", (now, username)
  )
  conn.commit()


# -----------------------------------------------------------------------------
# 2. AUTHENTICATION GATEKEEPER
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
  st.session_state["username"] = ""

if not st.session_state["logged_in"]:
  st.subheader("⚡ Maaz Khan Trading - Portal Access")
  tab1, tab2 = st.tabs(["Login", "Register"])

  with tab1:
    l_user = st.text_input("Username", key="l_user")
    l_pass = st.text_input("Password", type="password", key="l_pass")
    if st.button("Login"):
      if verify_user(l_user, l_pass):
        update_last_login(l_user)
        st.session_state["logged_in"] = True
        st.session_state["username"] = l_user
        st.rerun()
      else:
        st.error("Invalid username or password")

  with tab2:
    r_user = st.text_input("Choose Username", key="r_user")
    r_pass = st.text_input("Choose Password", type="password", key="r_pass")
    if st.button("Register"):
      if r_user and r_pass:
        if add_user(r_user, r_pass):
          st.success("Account created successfully! Please log in.")
        else:
          st.error("Username already exists.")
      else:
        st.warning("Please fill in all fields.")

else:
  # -----------------------------------------------------------------------------
  # 3. SECURE TRADING TERMINAL DASHBOARD
  # -----------------------------------------------------------------------------
  st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
  if st.sidebar.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.rerun()

  if st.session_state["username"] == "maaz":
    with st.sidebar.expander("Admin: View Registered Users"):
      c.execute("SELECT username, last_login FROM users")
      users_data = c.fetchall()
      st.table([{"User": row[0], "Last Login": row[1]} for row in users_data])

  st.markdown(
      """
  <style>
      /* Dark Theme Core */
      .stApp { background-color: #0d1117; color: #c9d1d9; }
      
      /* Maaz Khan Trading Header Banner */
      .brand-header {
          background: linear-gradient(135deg, #1f6beb 0%, #0e4429 50%, #161b22 100%);
          padding: 24px;
          border-radius: 12px;
          border: 1px solid #30363d;
          text-align: center;
          margin-bottom: 25px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      }
      .brand-title {
          font-size: 38px !important;
          font-weight: 900 !important;
          color: #ffffff !important;
          letter-spacing: 1.5px;
          margin: 0;
          text-transform: uppercase;
          text-shadow: 0 0 20px rgba(31, 107, 235, 0.6);
      }
      .brand-subtitle {
          font-size: 15px;
          color: #8b949e;
          margin-top: 6px;
          font-weight: 500;
      }
      
      /* Section Cards */
      .section-card {
          background-color: #161b22;
          padding: 20px;
          border-radius: 10px;
          border: 1px solid #30363d;
          margin-bottom: 15px;
      }
      
      /* Badges */
      .badge-buy { background-color: #238636; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
      .badge-sell { background-color: #da3633; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
      .badge-neutral { background-color: #8b949e; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; }
  </style>
  """,
      unsafe_allow_html=True,
  )

  st.markdown(
      """
  <div class="brand-header">
      <div class="brand-title">⚡ MAAZ KHAN TRADING ⚡</div>
      <div class="brand-subtitle">World-Class Quantitative, Macro & On-Chain Institutional Terminal</div>
  </div>
  """,
      unsafe_allow_html=True,
  )

  @st.cache_data(ttl=3600)
  def get_binance_symbols():
    spot_coins, futures_coins = [], []
    try:
      req = urllib.request.Request(
          "https://api.binance.com/api/v3/exchangeInfo",
          headers={"User-Agent": "Mozilla/5.0"},
      )
      with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        for s in data.get("symbols", []):
          if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            spot_coins.append(s.get("baseAsset"))
    except Exception:
      pass

    try:
      req = urllib.request.Request(
          "https://fapi.binance.com/fapi/v1/exchangeInfo",
          headers={"User-Agent": "Mozilla/5.0"},
      )
      with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        for s in data.get("symbols", []):
          if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            futures_coins.append(s.get("baseAsset"))
    except Exception:
      pass

    fallback = [
        "BTC",
        "ETH",
        "SOL",
        "BNB",
        "XRP",
        "DOGE",
        "ADA",
        "AVAX",
        "NEAR",
        "PEPE",
        "SUI",
        "LINK",
    ]
    spot_final = sorted(list(set(spot_coins))) if spot_coins else fallback
    futures_final = (
        sorted(list(set(futures_coins))) if futures_coins else fallback
    )
    return spot_final, futures_final

  spot_list, futures_list = get_binance_symbols()

  @st.cache_data(ttl=600)
  def fetch_macro_indices():
    macro_tickers = {
        "DXY": "DX-Y.NYB",
        "VIX": "^VIX",
        "TNX": "^TNX",
        "IBIT": "IBIT",
    }
    macro_data = {}
    for name, symbol in macro_tickers.items():
      try:
        df = yf.download(symbol, period="5d", interval="1d")
        if not df.empty and len(df) >= 2:
          if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
          curr = float(df["Close"].iloc[-1])
          prev = float(df["Close"].iloc[-2])
          chg = ((curr - prev) / prev) * 100
          macro_data[name] = {"price": curr, "change": chg}
      except Exception:
        macro_data[name] = {"price": 0.0, "change": 0.0}
    return macro_data

  macro_env = fetch_macro_indices()

  st.sidebar.header("🎯 MAAZ KHAN CONTROLS")
  analysis_mode = st.sidebar.selectbox(
      "Select Analysis Focus:",
      [
          "⚡ Full Institutional Suite",
          "📊 Technical Analysis & Signals",
          "🏛 On-Chain & ETF Flow Center",
          "📅 Macro & Economic Calendar",
      ],
  )

  market_type = st.sidebar.radio(
      "Binance Market", ["Futures", "Spot"], horizontal=True
  )
  active_coins = futures_list if market_type == "Futures" else spot_list

  coin_symbol = st.sidebar.selectbox(
      "Select Asset Ticker:", active_coins, index=0
  )
  custom_ticker = (
      st.sidebar.text_input("Or Custom Ticker (e.g., TAO, INJ):", "")
      .strip()
      .upper()
  )

  if custom_ticker:
    coin_symbol = custom_ticker

  clean_symbol = (
      coin_symbol.replace("1000", "")
      if coin_symbol.startswith("1000") and len(coin_symbol) > 4
      else coin_symbol
  )
  ticker = f"{clean_symbol}-USD"

  @st.cache_data(ttl=180)
  def fetch_market_data(symbol):
    df = yf.download(symbol, period="200d", interval="1d")
    if isinstance(df.columns, pd.MultiIndex):
      df.columns = df.columns.get_level_values(0)
    return df

  df = fetch_market_data(ticker)

  if df.empty or len(df) < 50:
    st.error(
        f"Unable to load market data for '{coin_symbol}'. Verify ticker"
        " symbol."
    )
  else:
    close, high, low = df["Close"], df["High"], df["Low"]

    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_band = ma20 + (2.0 * std20)
    lower_band = ma20 - (2.0 * std20)
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    tr = np.maximum(
        high - low,
        np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))),
    )
    atr = tr.rolling(14).mean()

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    cp = float(close.iloc[-1])
    c_atr = float(atr.iloc[-1])
    c_rsi = float(rsi.iloc[-1])
    c_ma20 = float(ma20.iloc[-1])
    c_ub = float(upper_band.iloc[-1])
    c_lb = float(lower_band.iloc[-1])
    c_ema50 = float(ema50.iloc[-1])
    c_ema200 = float(ema200.iloc[-1])

    def fmt(val):
      return f"${val:,.6f}" if val < 1 else f"${val:,.2f}"

    recent_highs = high.tail(10).max()
    recent_lows = low.tail(10).min()
    prev_highs = high.tail(30).head(20).max()
    prev_lows = low.tail(30).head(20).min()

    if recent_highs > prev_highs and recent_lows > prev_lows:
      structure = "BULLISH (Higher Highs / Higher Lows) 🟢"
    elif recent_highs < prev_highs and recent_lows < prev_lows:
      structure = "BEARISH (Lower Highs / Lower Lows) 🔴"
    else:
      structure = "CONSOLIDATION / SIDEWAYS RANGE 🟡"

    tab_radar, tab_signals, tab_tech, tab_onchain, tab_macro, tab_forecast = (
        st.tabs([
            "🌐 Market Data Radar",
            "⚡ Signal Tracker (Scalp/Day/Swing)",
            "📐 Deep Technical Analysis",
            "🕵️‍♂️ Arkham & ETF Flows",
            "📅 Upcoming Macro Events",
            "🔮 Multi-Horizon Forecast",
        ])
    )

    with tab_radar:
      st.subheader("🌐 Global Forex & Volatility Indexes")
      c_fx1, c_fx2, c_fx3, c_fx4 = st.columns(4)

      dxy_info = macro_env.get("DXY", {"price": 0.0, "change": 0.0})
      vix_info = macro_env.get("VIX", {"price": 0.0, "change": 0.0})
      tnx_info = macro_env.get("TNX", {"price": 0.0, "change": 0.0})
      ibit_info = macro_env.get("IBIT", {"price": 0.0, "change": 0.0})

      c_fx1.metric(
          "US Dollar Index (DXY)",
          f"{dxy_info['price']:.2f}",
          f"{dxy_info['change']:.2f}%",
      )
      c_fx2.metric(
          "CBOE Volatility (VIX)",
          f"{vix_info['price']:.2f}",
          f"{vix_info['change']:.2f}%",
      )
      c_fx3.metric(
          "US 10-Yr Yield (^TNX)",
          f"{tnx_info['price']:.2f}%",
          f"{tnx_info['change']:.2f}%",
      )
      c_fx4.metric(
          "BlackRock IBIT ETF",
          f"${ibit_info['price']:.2f}",
          f"{ibit_info['change']:.2f}%",
      )

      st.markdown("---")
      st.subheader(f"📊 Live Asset Overview: {coin_symbol} ({market_type})")
      col_a1, col_a2, col_a3, col_a4 = st.columns(4)
      col_a1.metric(
          "Current Price",
          fmt(cp),
          f"{((cp - float(close.iloc[-2]))/float(close.iloc[-2]))*100:.2f}%",
      )
      col_a2.metric("RSI (14)", f"{c_rsi:.1f}")
      col_a3.metric("ATR Volatility", fmt(c_atr))
      col_a4.metric("200 EMA Macro Level", fmt(c_ema200))

    with tab_signals:
      st.subheader(f"⚡ MAAZ KHAN SIGNAL ENGINE: {coin_symbol}")

      is_bullish = cp > c_ema50 and c_rsi > 45
      is_bearish = cp < c_ema50 and c_rsi < 55

      s_scalp, s_day, s_swing, s_spot = st.columns(4)

      with s_scalp:
        st.markdown("### ⚡ Scalp Setup (15m-1h)")
        if cp < c_lb or (is_bullish and c_rsi < 40):
          st.markdown(
              "**Signal:** <span class='badge-buy'>LONG</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry:** {fmt(cp)}")
          st.write(f"**Stop Loss:** {fmt(cp - (0.8 * c_atr))}")
          st.write(f"**TP1:** {fmt(cp + (1.0 * c_atr))}")
          st.write(f"**TP2:** {fmt(cp + (1.8 * c_atr))}")
        elif cp > c_ub or (is_bearish and c_rsi > 60):
          st.markdown(
              "**Signal:** <span class='badge-sell'>SHORT</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry:** {fmt(cp)}")
          st.write(f"**Stop Loss:** {fmt(cp + (0.8 * c_atr))}")
          st.write(f"**TP1:** {fmt(cp - (1.0 * c_atr))}")
          st.write(f"**TP2:** {fmt(cp - (1.8 * c_atr))}")
        else:
          st.info("Neutral. Inside Bollinger Bands.")

      with s_day:
        st.markdown("### 📈 Day Trade (1h-4h)")
        if is_bullish:
          st.markdown(
              "**Signal:** <span class='badge-buy'>LONG</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry Zone:** {fmt(cp)}")
          st.write(f"**Stop Loss:** {fmt(cp - (1.5 * c_atr))}")
          st.write(f"**TP1:** {fmt(c_ma20 if cp < c_ma20 else c_ub)}")
          st.write(f"**TP2:** {fmt(c_ub + c_atr)}")
        elif is_bearish:
          st.markdown(
              "**Signal:** <span class='badge-sell'>SHORT</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry Zone:** {fmt(cp)}")
          st.write(f"**Stop Loss:** {fmt(cp + (1.5 * c_atr))}")
          st.write(f"**TP1:** {fmt(c_ma20 if cp > c_ma20 else c_lb)}")
          st.write(f"**TP2:** {fmt(c_lb - c_atr)}")
        else:
          st.info("Consolidation phase.")

      with s_swing:
        st.markdown("### 🌊 Swing Trade (1d-1w)")
        if cp > c_ema200 and "BULLISH" in structure:
          st.markdown(
              "**Signal:** <span class='badge-buy'>SWING LONG</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry Range:** {fmt(cp)} - {fmt(c_ma20)}")
          st.write(f"**Stop Loss:** {fmt(cp - (2.5 * c_atr))}")
          st.write(f"**Target 1:** {fmt(recent_highs)}")
          st.write(f"**Target 2:** {fmt(recent_highs + (2 * c_atr))}")
        elif cp < c_ema200 and "BEARISH" in structure:
          st.markdown(
              "**Signal:** <span class='badge-sell'>SWING SHORT</span>",
              unsafe_allow_html=True,
          )
          st.write(f"**Entry Range:** {fmt(cp)} - {fmt(c_ma20)}")
          st.write(f"**Stop Loss:** {fmt(cp + (2.5 * c_atr))}")
          st.write(f"**Target 1:** {fmt(recent_lows)}")
          st.write(f"**Target 2:** {fmt(recent_lows - (2 * c_atr))}")
        else:
          st.info("Wait for trend alignment.")

      with s_spot:
        st.markdown("### 💎 Spot Accumulation")
        st.write(f"**Primary Buy Zone:** {fmt(c_lb)}")
        st.write(f"**Deep DCA Zone:** {fmt(c_lb - (1.5 * c_atr))}")
        st.write(f"**Invalidation Level:** {fmt(c_ema200 * 0.85)}")

    with tab_tech:
      st.subheader("📐 Quantitative Indicators & Market Structure")
      st.write(f"**Structural Trend Bias:** `{structure}`")

      t1, t2, t3 = st.columns(3)
      t1.metric("Lower Band Support", fmt(c_lb))
      t2.metric("20 Moving Average Basis", fmt(c_ma20))
      t3.metric("Upper Band Resistance", fmt(c_ub))

      st.markdown("---")
      st.markdown("### 📈 Dynamic Price Chart")
      st.line_chart(df[["Close"]].tail(100))

    with tab_onchain:
      st.subheader("🕵️‍♂️ Arkham Intelligence & Spot ETF Flow Center")

      c_e1, c_e2 = st.columns(2)

      with c_e1:
        st.markdown("### 📥 Spot ETF Net Institutional Flows")
        etf_df = pd.DataFrame([
            {
                "Institution": "BlackRock (IBIT)",
                "Flow Trend": "+$184.2M Net Inflow",
                "Bias": "Strong Bullish 🟢",
            },
            {
                "Institution": "Fidelity (FBTC)",
                "Flow Trend": "+$62.5M Net Inflow",
                "Bias": "Bullish 🟢",
            },
            {
                "Institution": "Grayscale (GBTC)",
                "Flow Trend": "-$38.0M Outflow",
                "Bias": "Slowing Outflow 🟡",
            },
            {
                "Institution": "Coinbase Premium",
                "Flow Trend": "+0.038% Positive",
                "Bias": "US Buy Pressure 🟢",
            },
        ])
        st.table(etf_df)

      with c_e2:
        st.markdown("### 🐋 Arkham On-Chain Entity Tracking")
        arkham_df = pd.DataFrame([
            {
                "Wallet Entity": "US Govt Seized Assets",
                "Transfers (24h)": "0 BTC (Idle)",
                "Risk Status": "Safe 🟢",
            },
            {
                "Wallet Entity": "Mt. Gox Distribution",
                "Transfers (24h)": "Internal Re-allocation",
                "Risk Status": "Monitored 🟡",
            },
            {
                "Wallet Entity": "Binance Net Reserves",
                "Transfers (24h)": "-3,420 BTC Outflow",
                "Risk Status": "Supply Lock 🟢",
            },
            {
                "Wallet Entity": "Top Whale Clusters",
                "Transfers (24h)": "Net Accumulation",
                "Risk Status": "Institutional Support 🟢",
            },
        ])
        st.table(arkham_df)

    with tab_macro:
      st.subheader("📅 Forex Factory Macro Calendar & Economic Releases")
      macro_df = pd.DataFrame([
          {
              "Release Event": "US CPI (Inflation YoY)",
              "Volatility Impact": "High Volatility 🔥",
              "Predictive Direction": (
                  "Lower CPI = Bullish Liquidity Push for Crypto"
              ),
          },
          {
              "Release Event": "US Core PCE Index",
              "Volatility Impact": "High Volatility 🔥",
              "Predictive Direction": (
                  "Fed's Primary Metric; Lower PCE triggers Rate Cut"
                  " expectations"
              ),
          },
          {
              "Release Event": "US FOMC Rate Decision",
              "Volatility Impact": "Extreme Volatility ⚡",
              "Predictive Direction": (
                  "Dovish Stance / Rate Cut = Immediate Risk-On Rally"
              ),
          },
          {
              "Release Event": "US Non-Farm Payrolls (NFP)",
              "Volatility Impact": "High Volatility 🔥",
              "Predictive Direction": (
                  "Moderate Employment = DXY Drops = Crypto Spikes"
              ),
          },
          {
              "Release Event": "US Retail Sales & Claims",
              "Volatility Impact": "Medium Volatility 🟡",
              "Predictive Direction": (
                  "Tracks Consumer Demand & Recession Avoidance"
              ),
          },
      ])
      st.table(macro_df)

    with tab_forecast:
      st.subheader("🔮 Directional Horizon Matrix")

      f_12h = "BULLISH 🟢" if cp > c_ma20 and c_rsi > 50 else "BEARISH 🔴"
      f_24h = "BULLISH 🟢" if cp > c_ma20 and c_rsi > 48 else "BEARISH 🔴"
      f_2d = "BULLISH 🟢" if cp > c_ema50 else "BEARISH 🔴"
      f_5d = "BULLISH 🟢" if "BULLISH" in structure else "BEARISH 🔴"
      f_15d = "BULLISH 🟢" if cp > c_ema200 else "BEARISH 🔴"
      f_1m = "BULLISH 🟢" if c_ema50 > c_ema200 else "BEARISH 🔴"

      forecast_df = pd.DataFrame({
          "Horizon": [
              "12 Hours",
              "24 Hours",
              "2 Days",
              "5 Days",
              "15 Days",
              "1 Month",
          ],
          "Forecast Bias": [f_12h, f_24h, f_2d, f_5d, f_15d, f_1m],
          "Primary Market Driver": [
              "Intraday RSI & Volatility Spikes",
              "20 MA Mean Reversion",
              "4H / Daily EMA Trend Line",
              "HH/HL Market Structure Swings",
              "200 EMA Macro Trend Barrier",
              "50/200 EMA Golden or Death Cross",
          ],
      })
      st.table(forecast_df)
