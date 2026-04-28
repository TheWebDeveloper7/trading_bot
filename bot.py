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

# ================= TOKEN SAFETY =================
if not ACCESS_TOKEN:
    print("❌ ACCESS TOKEN missing")
    while True:
        time.sleep(60)

kite.set_access_token(ACCESS_TOKEN)

# ================= TIMEZONE =================
IST = pytz.timezone('Asia/Kolkata')

def get_time():
    return datetime.now(IST).strftime("%H:%M %p")

def is_market_open():
    now = datetime.now(IST)
    start = now.replace(hour=9, minute=15, second=0)
    end = now.replace(hour=15, minute=30, second=0)
    return start <= now <= end

# ================= TOKEN CHECK =================
try:
    kite.profile()
    print("✅ Token Valid")
except Exception as e:
    print("❌ Token Error:", e)

# ================= LOAD INSTRUMENTS =================
NSE, BSE = [], []

while not NSE:
    try:
        NSE = kite.instruments("NSE")
    except:
        time.sleep(5)

while not BSE:
    try:
        BSE = kite.instruments("BSE")
    except:
        time.sleep(5)

print("✅ Instruments Loaded")

# ================= INDEX TOKENS =================
INDEX_TOKENS = {
    "NIFTY 50": 256265,
    "NIFTY BANK": 260105
}

# ================= TELEGRAM =================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except Exception as e:
        print("Telegram Error:", e)

# ================= WATCHLIST =================
STOCK_LIST = [
    "RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK",
    "SBIN","AXISBANK","LT","ITC","BAJFINANCE",
    "KOTAKBANK","HINDUNILVR","BHARTIARTL","ASIANPAINT",
    "MARUTI","SUNPHARMA","TITAN","ULTRACEMCO",
    "NESTLEIND","POWERGRID","NTPC","ONGC","TECHM",
    "WIPRO","HCLTECH","ADANIENT","ADANIPORTS",
    "JSWSTEEL","TATASTEEL","COALINDIA","IOC",
    "BPCL","HEROMOTOCO","BAJAJFINSV","EICHERMOT",
    "GRASIM","CIPLA","DRREDDY","DIVISLAB",
    "SHRIRAMFIN","INDUSINDBK","HDFCLIFE","SBILIFE",
    "UPL","APOLLOHOSP","BRITANNIA","TATAMOTORS",
    "M&M","VEDL"
]

# ================= TOKEN FETCH =================
def get_token(symbol):
    for i in NSE:
        if i["tradingsymbol"] == symbol:
            return i["instrument_token"]
    for i in BSE:
        if i["tradingsymbol"] == symbol:
            return i["instrument_token"]
    print(f"❌ Token not found: {symbol}")
    return None

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
    df["obv_ema"] = df["obv"].ewm(span=20).mean()
    return df

def calculate_cpr(df):
    prev = df.iloc[-2]
    pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
    bc = (prev["high"] + prev["low"]) / 2
    tc = pivot + (pivot - bc)
    return abs(tc - bc) / pivot * 100

def calculate_roc(df, period=10):
    return ((df["close"].iloc[-1] - df["close"].iloc[-period]) /
            df["close"].iloc[-period]) * 100

def check_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    bull = prev["obv"] < prev["obv_ema"] and last["obv"] > last["obv_ema"]
    bear = prev["obv"] > prev["obv_ema"] and last["obv"] < last["obv_ema"]

    cpr = calculate_cpr(df)
    roc = calculate_roc(df)

    return bull and cpr < 0.5, bear and cpr < 0.5, last, cpr, roc

# ================= DATE =================
def get_date_range():
    to_date = datetime.now(IST)
    from_date = to_date - timedelta(days=5)
    return from_date, to_date

# ================= HEARTBEAT =================
def heartbeat():
    while True:
        send_telegram("💓 Bot Alive")
        time.sleep(1800)

# ================= INDEX SCANNER =================
def index_scanner():
    send_telegram("📊 Index Scanner Started")
    last_signal = {}

    while True:
        try:
            if not is_market_open():
                print("⏸ Market Closed (Index)")
                time.sleep(300)
                continue

            from_date, to_date = get_date_range()

            for name, token in INDEX_TOKENS.items():

                df = pd.DataFrame(kite.historical_data(token, from_date, to_date, "5minute"))
                if len(df) == 0:
                    continue

                df = calculate_obv(df)
                bull, bear, last, cpr, roc = check_signal(df)

                price = round(last["close"], 2)

                if name not in last_signal:
                    last_signal[name] = ""

                if bull and last_signal[name] != "CALL":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🟢 Signal: OBV Bullish
📈 Symbol: {name}

🔹 CPR: {round(cpr,2)}%
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Up

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[name] = "CALL"

                elif bear and last_signal[name] != "PUT":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🔴 Signal: OBV Bearish
📈 Symbol: {name}

🔹 CPR: {round(cpr,2)}%
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Down

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[name] = "PUT"

            time.sleep(300)

        except Exception as e:
            send_telegram(f"❌ Index Error: {e}")
            time.sleep(60)

# ================= STOCK SCANNER =================
def stock_scanner():
    send_telegram("📈 Stock Scanner Started")
    last_signal = {}

    while True:
        try:
            if not is_market_open():
                print("⏸ Market Closed (Stocks)")
                time.sleep(300)
                continue

            from_date, to_date = get_date_range()

            for stock in STOCK_LIST:

                token = get_token(stock)
                if not token:
                    continue

                df = pd.DataFrame(kite.historical_data(token, from_date, to_date, "15minute"))
                if len(df) == 0:
                    continue

                df = calculate_obv(df)
                bull, bear, last, cpr, roc = check_signal(df)

                price = round(last["close"], 2)

                if stock not in last_signal:
                    last_signal[stock] = ""

                if bull and last_signal[stock] != "CALL":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🟢 Signal: OBV Bullish
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}%
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Up

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[stock] = "CALL"

                elif bear and last_signal[stock] != "PUT":
                    send_telegram(f"""
📊 CPR STRATEGY ALERT

🔴 Signal: OBV Bearish
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Down

💰 Price: {price}
⏰ Time: {get_time()}
""")
                    last_signal[stock] = "PUT"

                time.sleep(0.3)

            time.sleep(300)

        except Exception as e:
            send_telegram(f"❌ Stock Error: {e}")
            time.sleep(60)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "🚀 Bot Running"

@app.route("/test")
def test():
    send_telegram("✅ Test Message Successful")
    return "Test Sent"

# ================= START =================
if __name__ == "__main__":
    send_telegram("🚀 Trading Bot Started")

    threading.Thread(target=index_scanner, daemon=True).start()
    threading.Thread(target=stock_scanner, daemon=True).start()
    threading.Thread(target=heartbeat, daemon=True).start()

    app.run(host="0.0.0.0", port=10000)
