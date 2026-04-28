from flask import Flask
import threading
import time
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import pytz

# ================= CONFIG =================
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

kite = KiteConnect(api_key=API_KEY)

if not ACCESS_TOKEN:
    print("❌ ACCESS TOKEN missing")
    while True:
        time.sleep(60)

kite.set_access_token(ACCESS_TOKEN)

# ================= TIME =================
IST = pytz.timezone("Asia/Kolkata")

def get_time():
    return datetime.now(IST).strftime("%H:%M %p")

def is_market_open():
    now = datetime.now(IST)
    start = now.replace(hour=9, minute=15, second=0)
    end = now.replace(hour=15, minute=30, second=0)
    return start <= now <= end

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except Exception as e:
        print("Telegram Error:", e)

# ================= LOAD INSTRUMENTS =================
INSTRUMENTS = []
while not INSTRUMENTS:
    try:
        INSTRUMENTS = kite.instruments("NSE")
    except:
        time.sleep(5)

# ✅ FAST TOKEN MAP
TOKEN_MAP = {i["tradingsymbol"]: i["instrument_token"] for i in INSTRUMENTS}

def get_token(symbol):
    return TOKEN_MAP.get(symbol, None)

# ================= WATCHLIST =================
STOCK_LIST = [
"RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK","SBIN","AXISBANK","KOTAKBANK",
"LT","ITC","HINDUNILVR","BHARTIARTL","ASIANPAINT","MARUTI","SUNPHARMA",
"TITAN","ULTRACEMCO","NESTLEIND","POWERGRID","NTPC","ONGC","TECHM","WIPRO",
"HCLTECH","ADANIENT","ADANIPORTS","JSWSTEEL","TATASTEEL","COALINDIA",
"IOC","BPCL","HEROMOTOCO","BAJAJFINSV","EICHERMOT","GRASIM","CIPLA",
"DRREDDY","DIVISLAB","INDUSINDBK","HDFCLIFE","SBILIFE","UPL","APOLLOHOSP",
"BRITANNIA","TATAMOTORS","M&M","VEDL"
# 👉 Extend to full Nifty 150
]

# ================= DATE =================
def get_date_range():
    to_date = datetime.now(IST)
    from_date = to_date - timedelta(days=30)
    return from_date, to_date

# ================= INDICATORS =================
def calculate_obv(df):
    obv = [0]
    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i-1]:
            obv.append(obv[-1] + df["volume"].iloc[i])
        elif df["close"].iloc[i] < df["close"].iloc[i-1]:
            obv.append(obv[-1] - df["volume"].iloc[i])
        else:
            obv.append(obv[-1])

    df["obv"] = obv
    df["obv"] = df["obv"] - df["obv"].iloc[0]
    df["obv_ema"] = df["obv"].ewm(span=20, adjust=False).mean()
    return df

# ================= CPR CACHE =================
CPR_CACHE = {}

def calculate_cpr(symbol):
    if symbol in CPR_CACHE:
        return CPR_CACHE[symbol]

    try:
        token = get_token(symbol)

        df = pd.DataFrame(kite.historical_data(
            token,
            datetime.now(IST) - timedelta(days=10),
            datetime.now(IST),
            "day"
        ))

        if len(df) < 2:
            return None

        prev = df.iloc[-2]

        pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
        bc = (prev["high"] + prev["low"]) / 2
        tc = pivot + (pivot - bc)

        cpr = abs(tc - bc) / pivot * 100

        CPR_CACHE[symbol] = cpr
        return cpr

    except:
        return None

def calculate_roc(df, period=10):
    roc_series = ((df["close"] - df["close"].shift(period)) /
                  df["close"].shift(period)) * 100
    return roc_series.iloc[-1]

# ================= FILTERS =================
def breakout_filter(df):
    prev_high = df["high"].rolling(20).max().iloc[-2]
    prev_low = df["low"].rolling(20).min().iloc[-2]
    last_close = df["close"].iloc[-1]
    return last_close > prev_high, last_close < prev_low

def volume_filter(df):
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    return df["volume"].iloc[-1] > 1.5 * avg_vol

def trend_filter(df):
    ema20 = df["close"].ewm(span=20).mean()
    last_close = df["close"].iloc[-1]
    return last_close > ema20.iloc[-1], last_close < ema20.iloc[-1]

# ================= SIGNAL =================
def check_signal(df, symbol):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    cpr = calculate_cpr(symbol)
    roc = calculate_roc(df)

    if cpr is None:
        return False, False, last, 0, 0

    bull_obv = prev["obv"] <= prev["obv_ema"] and last["obv"] > last["obv_ema"]
    bear_obv = prev["obv"] >= prev["obv_ema"] and last["obv"] < last["obv_ema"]

    breakout_up, breakout_down = breakout_filter(df)
    strong_volume = volume_filter(df)
    trend_up, trend_down = trend_filter(df)

    bull = bull_obv and breakout_up and strong_volume and trend_up and cpr < 0.5 and roc > 0
    bear = bear_obv and breakout_down and strong_volume and trend_down and cpr < 0.5 and roc < 0

    return bull, bear, last, cpr, roc

# ================= SCANNER =================
def scanner():
    send_telegram("🚀 Trading Bot Started")
    last_signal = {}

    while True:
        try:
            if not is_market_open():
                print("⏸ Market Closed")
                time.sleep(300)
                continue

            CPR_CACHE.clear()  # refresh daily

            from_date, to_date = get_date_range()

            signals_sent = 0
            MAX_SIGNALS = 5

            for stock in STOCK_LIST:

                if signals_sent >= MAX_SIGNALS:
                    break

                token = get_token(stock)
                if not token:
                    continue

                df = pd.DataFrame(kite.historical_data(
                    token, from_date, to_date, "15minute"
                ))

                if len(df) < 30:
                    continue

                df = calculate_obv(df)

                bull, bear, last, cpr, roc = check_signal(df, stock)

                price = round(last["close"], 2)

                if stock not in last_signal:
                    last_signal[stock] = ""

                if bull and last_signal[stock] != "CALL":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🟢 Signal: OBV Bullish + Breakout
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}%
🔹 ROC: {round(roc,2)}
🔹 Volume: Strong
🔹 Trend: Up

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[stock] = "CALL"
                    signals_sent += 1

                elif bear and last_signal[stock] != "PUT":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🔴 Signal: OBV Bearish + Breakdown
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}%
🔹 ROC: {round(roc,2)}
🔹 Volume: Strong
🔹 Trend: Down

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[stock] = "PUT"
                    signals_sent += 1

                time.sleep(0.15)

            time.sleep(600)

        except Exception as e:
            send_telegram(f"❌ ERROR: {e}")
            time.sleep(60)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running"

@app.route("/home/<msg>")
def hello(msg):
    send_telegram(f"{msg}")
    return f"{msg}"

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=scanner, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
