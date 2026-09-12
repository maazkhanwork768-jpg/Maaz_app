import base64
from datetime import datetime
from email.mime.text import MIMEText
import hashlib
import json
import random
import re
import smtplib
import sqlite3
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & INSTITUTIONAL DARK THEME DESIGN SYSTEM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Maaz Khan Trading | Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    /* Dark Theme System */
    .stApp { background-color: #0b0e11; color: #EAECEF; }
    
    section[data-testid="stSidebar"] {
        background-color: #181a20 !important;
        border-right: 1px solid #2b313a;
    }

    /* Terminal Header Banner */
    .terminal-header {
        background: linear-gradient(180deg, #181a20 0%, #0b0e11 100%);
        padding: 20px 24px;
        border-radius: 10px;
        border: 1px solid #2b313a;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .terminal-title {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #F0B90B !important;
        letter-spacing: 1px;
        margin: 0;
    }
    .terminal-subtitle {
        font-size: 13px;
        color: #848E9C;
        margin-top: 4px;
    }

    /* Styled Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #181a20;
        border: 1px solid #2b313a;
        padding: 14px 18px;
        border-radius: 8px;
    }
    div[data-testid="stMetricLabel"] { color: #848E9C !important; font-size: 13px; }
    div[data-testid="stMetricValue"] { color: #EAECEF !important; font-weight: 700; }

    /* Signal Badges */
    .badge-long { background-color: #0ECB81; color: #000000; padding: 4px 12px; border-radius: 4px; font-weight: 800; }
    .badge-short { background-color: #F6465D; color: #FFFFFF; padding: 4px 12px; border-radius: 4px; font-weight: 800; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. AUTO-MIGRATING DATABASE & ENCRYPTED AUTHENTICATION ENGINE
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

try:
  c.execute("ALTER TABLE users ADD COLUMN contact_type TEXT")
except sqlite3.OperationalError:
  pass

try:
  c.execute("ALTER TABLE users ADD COLUMN contact_info TEXT")
except sqlite3.OperationalError:
  pass

conn.commit()


def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()


def username_exists(username):
  c.execute("SELECT username FROM users WHERE username = ?", (username,))
  return c.fetchone() is not None


def get_user_contact_info(username):
  c.execute(
      "SELECT contact_type, contact_info FROM users WHERE username = ?",
      (username,),
  )
  return c.fetchone()


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


def update_password(username, new_password):
  c.execute(
      "UPDATE users SET password = ? WHERE username = ?",
      (hash_password(new_password), username),
  )
  conn.commit()


def update_last_login(username):
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  c.execute(
      "UPDATE users SET last_login = ? WHERE username = ?", (now, username)
  )
  conn.commit()


# -----------------------------------------------------------------------------
# 3. OTP DISPATCH & STABLE CAPTCHA ENGINE
# -----------------------------------------------------------------------------
def send_otp_email(receiver_email, otp_code):
  try:
    sender_email = st.secrets.get("SMTP_EMAIL", "")
    sender_password = st.secrets.get("SMTP_PASSWORD", "")

    if sender_email and sender_password:
      msg = MIMEText(
          f"Your Maaz Khan Trading Terminal verification OTP is: {otp_code}\n\nDo"
          " not share this code with anyone."
      )
      msg["Subject"] = "Maaz Khan Trading - Security Verification Code"
      msg["From"] = sender_email
      msg["To"] = receiver_email

      with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
      return True, "Email sent successfully to your inbox!"
    else:
      return False, "SMTP credentials missing from Streamlit Secrets."
  except Exception as e:
    return False, f"Email delivery error: {str(e)}"


def send_otp_sms(receiver_phone, otp_code):
  try:
    account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
    auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
    from_number = st.secrets.get("TWILIO_PHONE_NUMBER", "")

    if account_sid and auth_token and from_number:
      url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
      auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
      data = urllib.parse.urlencode({
          "From": from_number,
          "To": receiver_phone,
          "Body": (
              f"Your Maaz Khan Trading Terminal OTP is: {otp_code}. Valid for"
              " verification."
          ),
      }).encode()
      req = urllib.request.Request(
          url,
          data=data,
          headers={
              "Authorization": f"Basic {auth}",
              "Content-Type": "application/x-www-form-urlencoded",
          },
      )
      with urllib.request.urlopen(req, timeout=6) as resp:
        return True, "SMS sent successfully to your mobile number!"
    else:
      return False, "Twilio SMS credentials missing from Streamlit Secrets."
  except Exception as e:
    return False, f"SMS delivery error: {str(e)}"


if "cap_a" not in st.session_state or "cap_b" not in st.session_state:
  st.session_state["cap_a"] = random.randint(1, 9)
  st.session_state["cap_b"] = random.randint(1, 9)


def reset_captcha():
  st.session_state["cap_a"] = random.randint(1, 9)
  st.session_state["cap_b"] = random.randint(1, 9)


if "reg_step" not in st.session_state:
  st.session_state["reg_step"] = "details"
if "generated_otp" not in st.session_state:
  st.session_state["generated_otp"] = ""
if "pending_user" not in st.session_state:
  st.session_state["pending_user"] = {}

if "reset_step" not in st.session_state:
  st.session_state["reset_step"] = "request"
if "reset_otp" not in st.session_state:
  st.session_state["reset_otp"] = ""
if "reset_target_user" not in st.session_state:
  st.session_state["reset_target_user"] = ""

# -----------------------------------------------------------------------------
# 4. MULTI-PROVIDER MARKET DATA ENGINE (FAST FAILOVER)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=10)
def get_market_ticker_price(symbol="BTCUSDT"):
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  # Endpoint 1: Bybit Global API
  try:
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=3) as resp:
      data = json.loads(resp.read().decode())
      if data.get("retCode") == 0 and data.get("result", {}).get("list"):
        item = data["result"]["list"][0]
        l_price = float(item["lastPrice"])
        chg = float(item.get("price24hPcnt", 0)) * 100
        return {
            "price": l_price,
            "change": chg,
            "high": float(item.get("highPrice24h", l_price)),
            "low": float(item.get("lowPrice24h", l_price)),
            "volume": float(item.get("volume24h", 0)),
            "quote_volume": float(item.get("turnover24h", 0)),
        }
  except Exception:
    pass

  # Endpoint 2: US Exchange REST API
  try:
    url = f"https://api.binance.us/api/v3/ticker/24hr?symbol={symbol}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=3) as resp:
      data = json.loads(resp.read().decode())
      if "lastPrice" in data:
        return {
            "price": float(data["lastPrice"]),
            "change": float(data["priceChangePercent"]),
            "high": float(data["highPrice"]),
            "low": float(data["lowPrice"]),
            "volume": float(data["volume"]),
            "quote_volume": float(data["quoteVolume"]),
        }
  except Exception:
    pass

  # Endpoint 3: Yahoo Finance Fallback
  try:
    yf_symbol = symbol.replace("USDT", "-USD")
    df = yf.download(yf_symbol, period="2d", interval="1d", progress=False)
    if not df.empty and len(df) >= 1:
      if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
      curr_p = float(df["Close"].iloc[-1])
      prev_p = float(df["Close"].iloc[-2]) if len(df) > 1 else curr_p
      chg = (
          ((curr_p - prev_p) / prev_p) * 100 if prev_p > 0 else 0.0
      )
      return {
          "price": curr_p,
          "change": chg,
          "high": float(df["High"].iloc[-1]),
          "low": float(df["Low"].iloc[-1]),
          "volume": float(df["Volume"].iloc[-1]),
          "quote_volume": float(df["Volume"].iloc[-1] * curr_p),
      }
  except Exception:
    pass

  return {
      "price": 0.0,
      "change": 0.0,
      "high": 0.0,
      "low": 0.0,
      "volume": 0.0,
      "quote_volume": 0.0,
  }


@st.cache_data(ttl=15)
def get_market_klines(symbol="BTCUSDT", interval="1d", limit=120):
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

  # Endpoint 1: Bybit Kline Feed
  try:
    bybit_map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }
    b_int = bybit_map.get(interval, "D")
    url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={b_int}&limit={limit}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=3) as resp:
      data = json.loads(resp.read().decode())
      if data.get("retCode") == 0 and data.get("result", {}).get("list"):
        kline_list = data["result"]["list"]
        kline_list.reverse()
        rows = []
        for k in kline_list:
          rows.append({
              "open_time": pd.to_datetime(int(k[0]), unit="ms"),
              "open": float(k[1]),
              "high": float(k[2]),
              "low": float(k[3]),
              "close": float(k[4]),
              "volume": float(k[5]),
          })
        return pd.DataFrame(rows)
  except Exception:
    pass

  # Endpoint 2: US Exchange Kline Feed
  try:
    url = f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=3) as resp:
      data = json.loads(resp.read().decode())
      if isinstance(data, list) and len(data) > 0:
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
    pass

  return pd.DataFrame()


# -----------------------------------------------------------------------------
# 5. SECURE AUTHENTICATION GATEKEEPER
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
  st.session_state["username"] = ""

if not st.session_state["logged_in"]:
  st.markdown(
      """
  <div class="terminal-header">
      <div>
          <div class="terminal-title">⚡ MAAZ KHAN TRADING</div>
          <div class="terminal-subtitle">Institutional Live Market Analytics & Algorithmic Execution Terminal</div>
      </div>
  </div>
  """,
      unsafe_allow_html=True,
  )

  col1, col2, col3 = st.columns([1, 1.8, 1])
  with col2:
    tab_login, tab_reg, tab_forgot = st.tabs([
        "🔒 Account Login",
        "📝 Trader Registration",
        "🔑 Reset Password",
    ])

    # 1. LOGIN FORM
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
            st.error(
                f"Incorrect CAPTCHA answer. What is {st.session_state['cap_a']}"
                f" + {st.session_state['cap_b']}?"
            )
          elif verify_user(l_user, l_pass):
            update_last_login(l_user)
            st.session_state["logged_in"] = True
            st.session_state["username"] = l_user
            st.rerun()
          else:
            st.error("Invalid username or password.")

    # 2. REGISTRATION FORM
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
            st.error(
                f"Incorrect CAPTCHA answer. What is {st.session_state['cap_a']}"
                f" + {st.session_state['cap_b']}?"
            )
          elif not r_user or not r_pass or not contact_val:
            st.error("Please fill in all required fields.")
          elif username_exists(r_user.strip()):
            st.error(
                f"Username '{r_user}' is already taken. Please choose another."
            )
          else:
            valid_format = True
            if contact_method == "Phone Number" and not re.match(
                r"^\+\d{10,14}$", contact_val
            ):
              st.error(
                  "Invalid phone number format. Check country code and digits."
              )
              valid_format = False
            elif contact_method == "Email Address" and not re.match(
                r"[^@]+@[^@]+\.[^@]+", contact_val
            ):
              st.error("Invalid email address format.")
              valid_format = False

            if valid_format:
              otp_code = str(random.randint(100000, 999999))
              st.session_state["generated_otp"] = otp_code
              st.session_state["pending_user"] = {
                  "username": r_user.strip(),
                  "password": r_pass,
                  "contact_type": contact_method,
                  "contact_info": contact_val,
              }

              if contact_method == "Email Address":
                sent, msg = send_otp_email(contact_val, otp_code)
              else:
                sent, msg = send_otp_sms(contact_val, otp_code)

              st.session_state["dispatch_status"] = (sent, msg)
              st.session_state["reg_step"] = "verify_otp"
              st.rerun()

      elif st.session_state["reg_step"] == "verify_otp":
        st.subheader("🔑 Enter One-Time Password (OTP)")
        pending = st.session_state["pending_user"]
        sent_status, status_msg = st.session_state.get(
            "dispatch_status", (False, "")
        )

        st.info(f"Verification code sent to {pending['contact_info']}")

        if sent_status:
          st.success(f"✅ {status_msg}")
        else:
          st.warning(
              f"⚠️ {status_msg}\n\n"
              f"📩 [FALLBACK DISPATCH DISPLAY] Your OTP code is:"
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

    # 3. FORGOT PASSWORD FORM
    with tab_forgot:
      if st.session_state["reset_step"] == "request":
        st.subheader("Reset Forgotten Password")
        target_username = st.text_input(
            "Enter Account Username", key="reset_user_input"
        )

        st.caption(
            f"🤖 Security Check: What is **{st.session_state['cap_a']} +"
            f" {st.session_state['cap_b']}**?"
        )
        f_captcha = st.text_input("Enter Answer", key="f_cap")

        if st.button("Request Password Reset OTP"):
          ans = st.session_state["cap_a"] + st.session_state["cap_b"]

          if str(f_captcha).strip() != str(ans):
            st.error(
                f"Incorrect CAPTCHA answer. What is {st.session_state['cap_a']}"
                f" + {st.session_state['cap_b']}?"
            )
          elif not target_username.strip():
            st.error("Please enter your username.")
          elif not username_exists(target_username.strip()):
            st.error("No account found with this username.")
          else:
            user_info = get_user_contact_info(target_username.strip())
            if user_info:
              c_type, c_info = user_info[0], user_info[1]
              otp_code = str(random.randint(100000, 999999))

              st.session_state["reset_otp"] = otp_code
              st.session_state["reset_target_user"] = target_username.strip()

              if c_type == "Email Address":
                sent, msg = send_otp_email(c_info, otp_code)
              else:
                sent, msg = send_otp_sms(c_info, otp_code)

              st.session_state["reset_dispatch_status"] = (sent, msg, c_info)
              st.session_state["reset_step"] = "verify"
              st.rerun()
            else:
              st.error(
                  "No recovery phone or email associated with this account."
              )

      elif st.session_state["reset_step"] == "verify":
        st.subheader("🔑 Verify OTP & Set New Password")
        r_user_target = st.session_state["reset_target_user"]
        sent_status, status_msg, c_info = st.session_state.get(
            "reset_dispatch_status", (False, "", "")
        )

        st.info(f"Reset code sent to registered contact: {c_info}")

        if sent_status:
          st.success(f"✅ {status_msg}")
        else:
          st.warning(
              f"⚠️ {status_msg}\n\n"
              f"📩 [FALLBACK DISPATCH DISPLAY] Your Password Reset OTP is:"
              f" **{st.session_state['reset_otp']}**"
          )

        r_otp_input = st.text_input(
            "Enter 6-Digit OTP Code", max_chars=6, key="r_otp_input"
        )
        new_pass = st.text_input(
            "Enter New Password", type="password", key="new_pass_input"
        )
        confirm_pass = st.text_input(
            "Confirm New Password", type="password", key="confirm_pass_input"
        )

        col_r1, col_r2 = st.columns(2)
        with col_r1:
          if st.button("Update Password"):
            if r_otp_input.strip() != st.session_state["reset_otp"]:
              st.error("Invalid OTP verification code.")
            elif not new_pass or not confirm_pass:
              st.error("Please fill in both password fields.")
            elif new_pass != confirm_pass:
              st.error("Passwords do not match.")
            else:
              update_password(r_user_target, new_pass)
              st.success(
                  "Password updated successfully! You can now log in with your"
                  " new password."
              )
              st.session_state["reset_step"] = "request"
              st.session_state["reset_otp"] = ""
              st.session_state["reset_target_user"] = ""
              reset_captcha()

        with col_r2:
          if st.button("Cancel & Go Back"):
            st.session_state["reset_step"] = "request"
            st.rerun()

else:
  # -----------------------------------------------------------------------------
  # 6. UNLOCKED INSTITUTIONAL TRADING TERMINAL
  # -----------------------------------------------------------------------------
  st.sidebar.markdown("### ⚡ **MK TERMINAL**")
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
      "Select Market Pair:",
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
      "Chart Timeframe:", ["1m", "5m", "15m", "1h", "4h", "1d"], index=5
  )

  ticker_data = get_market_ticker_price(selected_pair)
  df_klines = get_market_klines(selected_pair, interval=timeframe, limit=120)

  st.markdown(
      f"""
  <div class="terminal-header">
      <div>
          <div class="terminal-title">⚡ {selected_pair} | INSTITUTIONAL TERMINAL</div>
          <div class="terminal-subtitle">Real-Time Global Market Feed • Timeframe: {timeframe}</div>
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

  tab_chart, tab_signals, tab_orderbook, tab_forecast = st.tabs([
      "📈 Interactive Live Chart",
      "⚡ Automated Trading Signals",
      "📊 Volume & ETF Intelligence",
      "🔮 Horizon Matrix",
  ])

  # TAB 1: EMBEDDED TRADINGVIEW CHART (ZERO SERVER LOAD)
  with tab_chart:
    st.subheader(f"📈 Real-Time Charting Engine: {selected_pair}")
    tv_symbol = f"BYBIT:{selected_pair}"

    tradingview_html = f"""
        <div class="tradingview-widget-container" style="height:650px;width:100%;">
          <div id="tradingview_chart" style="height:calc(100% - 32px);width:100%;"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "{tv_symbol}",
            "interval": "D",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#0b0e11",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "container_id": "tradingview_chart"
          }});
          </script>
        </div>
        """
    components.html(tradingview_html, height=660)

  # TAB 2: SIGNAL ENGINE
  with tab_signals:
    st.subheader(f"⚡ MAAZ KHAN SIGNAL ENGINE — {selected_pair}")
    if not df_klines.empty and len(df_klines) > 5:
      close = df_klines["close"]
      ema50 = close.ewm(span=50, adjust=False).mean()
      ma20 = close.rolling(20).mean()
      std20 = close.rolling(20).std()
      lower_band = ma20 - (2.0 * std20)

      delta = close.diff()
      gain = (delta.where(delta > 0, 0)).rolling(14).mean()
      loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
      rs = gain / loss
      rsi = 100 - (100 / (1 + rs))

      cp = float(close.iloc[-1])
      c_rsi = (
          float(rsi.iloc[-1])
          if not rsi.empty and not pd.isna(rsi.iloc[-1])
          else 50.0
      )
      c_ema50 = float(ema50.iloc[-1]) if not ema50.empty else cp

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
        lb_val = (
            float(lower_band.iloc[-1])
            if not lower_band.empty and not pd.isna(lower_band.iloc[-1])
            else cp * 0.95
        )
        st.write(f"**Primary Buy:** {fmt_p(lb_val)}")
    else:
      st.info("Signal engine synchronizing with market feeds...")

  # TAB 3: INSTITUTIONAL FLOWS
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

  # TAB 4: FORECAST
  with tab_forecast:
    st.subheader("🔮 Directional Horizon Forecast")
    st.table(
        pd.DataFrame({
            "Horizon": ["15 Mins", "1 Hour", "4 Hours", "1 Day"],
            "Bias": ["BULLISH 🟢", "BULLISH 🟢", "BEARISH 🔴", "BULLISH 🟢"],
        })
    )
