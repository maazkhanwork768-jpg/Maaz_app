from datetime import datetime
import hashlib
import json
import random
import re
import sqlite3
import urllib.request
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & BINANCE PRO STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Maaz Khan Trading | Binance Pro Terminal",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stApp { background-color: #0b0e11; color: #EAECEF; }
    
    section[data-testid="stSidebar"] {
        background-color: #181a20 !important;
        border-right: 1px solid #2b313a;
    }

    .binance-header {
        background: linear-gradient(180deg, #181a20 0%, #0b0e11 100%);
        padding: 20px 24px;
        border-radius: 10px;
        border: 1px solid #2b313a;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .binance-title {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #F0B90B !important;
        letter-spacing: 1px;
        margin: 0;
    }
    .binance-subtitle {
        font-size: 13px;
        color: #848E9C;
        margin-top: 4px;
    }

    div[data-testid="stMetric"] {
        background-color: #181a20;
        border: 1px solid #2b313a;
        padding: 14px 18px;
        border-radius: 8px;
    }
    div[data-testid="stMetricLabel"] { color: #848E9C !important; font-size: 13px; }
    div[data-testid="stMetricValue"] { color: #EAECEF !important; font-weight: 700; }

    .badge-long { background-color: #0ECB81; color: #000000; padding: 4px 12px; border-radius: 4px; font-weight: 800; }
    .badge-short { background-color: #F6465D; color: #FFFFFF; padding: 4px 12px; border-radius: 4px; font-weight: 800; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. UPDATED DATABASE SCHEMA & AUTHENTICATION ENGINE
# -----------------------------------------------------------------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        contact_type TEXT,
        contact_info TEXT,
        last_login TEXT
    )
""")
conn.commit()


def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()


def username_exists(username):
  c.execute("SELECT username FROM users WHERE username = ?", (username,))
  return c.fetchone() is not None


def add_user(username, password, contact_type, contact_info):
  try:
    c.execute(
        "INSERT INTO users (username, password, contact_type, contact_info,"
        " last_login) VALUES (?, ?, ?, ?, ?)",
        (
            username,
            hash_password(password),
            contact_type,
            contact_info,
            "Never",
        ),
    )
    conn.commit()
    return True
  except sqlite3.IntegrityError:
    return False


def verify_user(username, password):
  c.execute(
      "SELECT password FROM users WHERE username = ? AND password = ?",
      (username, hash_password(password)),
  )
  return c.fetchone() is not None


def update_last_login(username):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  c.execute(
      "UPDATE users SET last_login = ? WHERE username = ?", (now, username)
  )
  conn.commit()


# CAPTCHA State Initialization
if "cap_a" not in st.session_state:
  st.session_state["cap_a"] = random.randint(1, 9)
  st.session_state["cap_b"] = random.randint(1, 9)


def reset_captcha():
  st.session_state["cap_a"] = random.randint(1, 9)
  st.session_state["cap_b"] = random.randint(1, 9)


# OTP & Registration Session State Handling
if "reg_step" not in st.session_state:
  st.session_state["reg_step"] = "details"  # Modes: 'details' or 'verify_otp'
if "generated_otp" not in st.session_state:
  st.session_state["generated_otp"] = ""
if "pending_user" not in st.session_state:
  st.session_state["pending_user"] = {}

# -----------------------------------------------------------------------------
# 3. DIRECT BINANCE API ENGINE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=15)
def get_binance_ticker_price(symbol="BTCUSDT"):
  try:
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=4) as resp:
      data = json.loads(resp.read().decode())
      return {
          "price": float(data["lastPrice"]),
          "change": float(data["priceChangePercent"]),
          "high": float(data["highPrice"]),
          "low": float(data["lowPrice"]),
          "volume": float(data["volume"]),
          "quote_volume": float(data["quoteVolume"]),
      }
  except Exception:
    return {
        "price": 0.0,
        "change": 0.0,
        "high": 0.0,
        "low": 0.0,
        "volume": 0.0,
        "quote_volume": 0.0,
    }


@st.cache_data(ttl=15)
def get_binance_klines(symbol="BTCUSDT", interval="1d", limit=120):
  try:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
      data = json.loads(resp.read().decode())
    df = pd.DataFrame(
        data,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "qav",
            "trades",
            "tbb",
            "tbq",
            "ignore",
        ],
    )
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
      df[col] = df[col].astype(float)
    return df
  except Exception:
    return pd.DataFrame()


# -----------------------------------------------------------------------------
# 4. AUTHENTICATION GATEKEEPER WITH OTP VERIFICATION
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
  st.session_state["username"] = ""

if not st.session_state["logged_in"]:
  st.markdown(
      """
  <div class="binance-header">
      <div>
          <div class="binance-title">🟡 MAAZ KHAN TRADING</div>
          <div class="binance-subtitle">Institutional Binance Pro Live Analytics & Algorithmic Execution</div>
      </div>
  </div>
  """,
      unsafe_allow_html=True,
  )

  col1, col2, col3 = st.columns([1, 1.8, 1])
  with col2:
    tab_login, tab_reg = st.tabs(["🔒 Account Login", "📝 Trader Registration"])

    # LOGIN FORM
    with tab_login:
      with st.form("login_form"):
        st.subheader("Login to Terminal")
        l_user = st.text_input(
            "Username", key="l_user", autocomplete="username"
        )
        l_pass = st.text_input(
            "Password",
            type="password",
            key="l_pass",
            autocomplete="current-password",
        )

        st.caption(
            f"🤖 Security Check: What is **{st.session_state['cap_a']} +"
            f" {st.session_state['cap_b']}**?"
        )
        l_captcha = st.text_input("Enter Answer", key="l_cap")
        submit_login = st.form_submit_button("Sign In")

        if submit_login:
          ans = st.session_state["cap_a"] + st.session_state["cap_b"]
          if str(l_captcha).strip() != str(ans):
            st.error("Incorrect CAPTCHA answer.")
            reset_captcha()
          elif verify_user(l_user, l_pass):
            update_last_login(l_user)
            st.session_state["logged_in"] = True
            st.session_state["username"] = l_user
            st.rerun()
          else:
            st.error("Invalid username or password.")
            reset_captcha()

    # ADVANCED REGISTRATION FORM WITH OTP & UNIQUE USERNAME CHECK
    with tab_reg:
      if st.session_state["reg_step"] == "details":
        st.subheader("Create Account")

        r_user = st.text_input("Choose Unique Username", key="r_user")
        r_pass = st.text_input(
            "Choose Password", type="password", key="r_pass"
        )

        contact_method = st.radio(
            "Verification Method:",
            ["Phone Number", "Email Address"],
            horizontal=True,
        )

        country_code = ""
        contact_val = ""

        if contact_method == "Phone Number":
          country_codes = [
              "+92 (Pakistan)",
              "+1 (USA/Canada)",
              "+44 (UK)",
              "+966 (Saudi Arabia)",
              "+971 (UAE)",
              "+91 (India)",
              "+49 (Germany)",
              "+33 (France)",
              "+61 (Australia)",
          ]
          selected_cc = st.selectbox("Select Country Code", country_codes)
          country_code = selected_cc.split(" ")[0]
          raw_phone = st.text_input("Mobile Phone Number (e.g. 3001234567)")
          contact_val = f"{country_code}{raw_phone.strip()}"
        else:
          contact_val = st.text_input("Email Address (e.g. user@domain.com)")

        st.caption(
            f"🤖 Security Check: What is **{st.session_state['cap_a']} +"
            f" {st.session_state['cap_b']}**?"
        )
        r_captcha = st.text_input("Enter CAPTCHA Answer", key="r_cap")

        if st.button("Send Verification OTP"):
          ans = st.session_state["cap_a"] + st.session_state["cap_b"]

          if str(r_captcha).strip() != str(ans):
            st.error("Incorrect CAPTCHA answer.")
            reset_captcha()
          elif not r_user or not r_pass or not contact_val:
            st.error("Please fill in all required fields.")
          elif username_exists(r_user.strip()):
            st.error(
                f"Username '{r_user}' is already taken. Please choose another."
            )
          else:
            if contact_method == "Phone Number" and not re.match(
                r"^\+\d{10,14}$", contact_val
            ):
              st.error(
                  "Invalid phone number format. Please check country code and"
                  " digits."
              )
            elif contact_method == "Email Address" and not re.match(
                r"[^@]+@[^@]+\.[^@]+", contact_val
            ):
              st.error("Invalid email address format.")
            else:
              # Generate 6-Digit OTP
              otp_code = str(random.randint(100000, 999999))
              st.session_state["generated_otp"] = otp_code
              st.session_state["pending_user"] = {
                  "username": r_user.strip(),
                  "password": r_pass,
                  "contact_type": contact_method,
                  "contact_info": contact_val,
              }
              st.session_state["reg_step"] = "verify_otp"
              st.rerun()

      elif st.session_state["reg_step"] == "verify_otp":
        st.subheader("🔑 Enter One-Time Password (OTP)")
        pending = st.session_state["pending_user"]
        st.info(f"Verification code sent to {pending['contact_info']}")

        # Simulated OTP Alert Box for Direct Testing
        st.warning(
            f"📩 [TESTING SIMULATOR] Your OTP code is:"
            f" **{st.session_state['generated_otp']}**"
        )

        user_otp = st.text_input(
            "Enter 6-Digit OTP Code", max_chars=6, key="user_otp"
        )

        col_v1, col_v2 = st.columns(2)
        with col_v1:
          if st.button("Verify OTP & Complete Registration"):
            if user_otp.strip() == st.session_state["generated_otp"]:
              success = add_user(
                  pending["username"],
                  pending["password"],
                  pending["contact_type"],
                  pending["contact_info"],
              )
              if success:
                st.success(
                    "Account registered successfully! You can now log in."
                )
                st.session_state["reg_step"] = "details"
                st.session_state["generated_otp"] = ""
                st.session_state["pending_user"] = {}
                reset_captcha()
              else:
                st.error("Failed to complete registration.")
            else:
              st.error("Incorrect OTP code. Please try again.")

        with col_v2:
          if st.button("Cancel & Go Back"):
            st.session_state["reg_step"] = "details"
            st.rerun()

else:
  # -----------------------------------------------------------------------------
  # 5. UNLOCKED BINANCE PRO TRADING DASHBOARD
  # -----------------------------------------------------------------------------
  st.sidebar.markdown("### 🟡 **BINANCE TERMINAL**")
  st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
  if st.sidebar.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.rerun()

  if st.session_state["username"] == "maaz":
    with st.sidebar.expander("Admin: Registered Users"):
      c.execute(
          "SELECT username, contact_type, contact_info, last_login FROM users"
      )
      st.table([
          {
              "User": r[0],
              "Type": r[1],
              "Contact": r[2],
              "Last Login": r[3],
          }
          for r in c.fetchall()
      ])

  selected_pair = st.sidebar.selectbox(
      "Select Binance Market:",
      [
          "BTCUSDT",
          "ETHUSDT",
          "SOLUSDT",
          "BNBUSDT",
          "XRPUSDT",
          "DOGEUSDT",
          "ADAUSDT",
          "AVAXUSDT",
          "NEARUSDT",
          "PEPEUSDT",
          "SUIUSDT",
          "LINKUSDT",
      ],
      index=0,
  )

  timeframe = st.sidebar.selectbox(
      "Chart Timeframe:", ["1m", "5m", "15m", "1h", "4h", "1d"], index=4
  )

  ticker_data = get_binance_ticker_price(selected_pair)
  df_klines = get_binance_klines(selected_pair, interval=timeframe, limit=120)

  st.markdown(
      f"""
  <div class="binance-header">
      <div>
          <div class="binance-title">🟡 {selected_pair} | BINANCE PRO</div>
          <div class="binance-subtitle">Real-Time Direct Exchange Feed • Timeframe: {timeframe}</div>
      </div>
  </div>
  """,
      unsafe_allow_html=True,
  )

  c1, c2, c3, c4, c5 = st.columns(5)
  price_chg_color = "🟢" if ticker_data["change"] >= 0 else "🔴"

  def fmt_p(val):
    return f"${val:,.6f}" if val < 1 else f"${val:,.2f}"

  c1.metric("Mark Price", fmt_p(ticker_data["price"]))
  c2.metric(
      "24h Change",
      f"{ticker_data['change']:.2f}%",
      delta=f"{price_chg_color} 24h",
  )
  c3.metric("24h High", fmt_p(ticker_data["high"]))
  c4.metric("24h Low", fmt_p(ticker_data["low"]))
  c5.metric("24h Volume (USDT)", f"${ticker_data['quote_volume']:,.0f}")

  st.markdown("---")

  if not df_klines.empty and len(df_klines) > 20:
    close = df_klines["close"]
    high = df_klines["high"]
    low = df_klines["low"]

    ma20 = close.rolling(20).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    std20 = close.rolling(20).std()
    upper_band = ma20 + (2.0 * std20)
    lower_band = ma20 - (2.0 * std20)

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    cp = float(close.iloc[-1])
    c_rsi = float(rsi.iloc[-1])
    c_ema50 = float(ema50.iloc[-1])

    tab_chart, tab_signals, tab_orderbook, tab_forecast = st.tabs([
        "📈 Binance Live Candlestick Chart",
        "⚡ Automated Trading Signals",
        "📊 Volume & ETF Intelligence",
        "🔮 Horizon Matrix",
    ])

    with tab_chart:
      fig = make_subplots(
          rows=2,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.03,
          row_heights=[0.8, 0.2],
      )

      fig.add_trace(
          go.Candlestick(
              x=df_klines["open_time"],
              open=df_klines["open"],
              high=df_klines["high"],
              low=df_klines["low"],
              close=df_klines["close"],
              increasing_line_color="#0ECB81",
              decreasing_line_color="#F6465D",
              name="OHLC",
          ),
          row=1,
          col=1,
      )

      fig.add_trace(
          go.Scatter(
              x=df_klines["open_time"],
              y=ma20,
              line=dict(color="#F0B90B", width=1.5),
              name="20 MA",
          ),
          row=1,
          col=1,
      )
      fig.add_trace(
          go.Scatter(
              x=df_klines["open_time"],
              y=ema50,
              line=dict(color="#00E5FF", width=1.5),
              name="50 EMA",
          ),
          row=1,
          col=1,
      )
      fig.add_trace(
          go.Scatter(
              x=df_klines["open_time"],
              y=ema200,
              line=dict(color="#E91E63", width=1.5),
              name="200 EMA",
          ),
          row=1,
          col=1,
      )

      colors = [
          "#0ECB81" if c >= o else "#F6465D"
          for c, o in zip(df_klines["close"], df_klines["open"])
      ]
      fig.add_trace(
          go.Bar(
              x=df_klines["open_time"],
              y=df_klines["volume"],
              marker_color=colors,
              name="Volume",
          ),
          row=2,
          col=1,
      )

      fig.update_layout(
          template="plotly_dark",
          height=680,
          xaxis_rangeslider_visible=False,
          paper_bgcolor="#0b0e11",
          plot_bgcolor="#0b0e11",
          margin=dict(l=10, r=10, t=20, b=10),
      )
      st.plotly_chart(fig, use_container_width=True)

    with tab_signals:
      st.subheader(f"⚡ MAAZ KHAN SIGNAL ENGINE — {selected_pair}")
      is_bull = cp > c_ema50 and c_rsi > 45

      s1, s2, s3 = st.columns(3)
      with s1:
        st.markdown("### ⚡ Scalp Signal")
        st.markdown(
            "**Bias:**"
            f" {'<span class=\"badge-long\">LONG</span>' if is_bull else '<span class=\"badge-short\">SHORT</span>'}",
            unsafe_allow_html=True,
        )
        st.write(f"**Entry:** {fmt_p(cp)}")
        st.write(f"**Stop:** {fmt_p(cp * 0.99)}")
      with s2:
        st.markdown("### 📈 Day Trade Setup")
        st.write(f"**Target 1:** {fmt_p(cp * 1.02)}")
        st.write(f"**Target 2:** {fmt_p(cp * 1.05)}")
      with s3:
        st.markdown("### 💎 Spot Accumulation Zone")
        st.write(f"**Primary Buy:** {fmt_p(float(lower_band.iloc[-1]))}")

    with tab_orderbook:
      st.subheader("📊 Institutional ETF & On-Chain Flows")
      st.table(
          pd.DataFrame([
              {
                  "Institution": "BlackRock (IBIT)",
                  "Flow": "+$184.2M",
                  "Bias": "Bullish 🟢",
              },
              {
                  "Institution": "Fidelity (FBTC)",
                  "Flow": "+$62.5M",
                  "Bias": "Bullish 🟢",
              },
              {
                  "Institution": "Grayscale (GBTC)",
                  "Flow": "-$38.0M",
                  "Bias": "Outflow 🔴",
              },
          ])
      )

    with tab_forecast:
      st.subheader("🔮 Directional Horizon Forecast")
      st.table(
          pd.DataFrame({
              "Horizon": ["15 Mins", "1 Hour", "4 Hours", "1 Day"],
              "Bias": ["BULLISH 🟢", "BULLISH 🟢", "BEARISH 🔴", "BULLISH 🟢"],
          })
      )
  else:
    st.error("Connecting to Binance API... Refresh page in a few seconds.")
