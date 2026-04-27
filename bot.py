from flask import Flask
import threading
import time
import os
import requests
import pandas as pd
from datetime import datetime
from kiteconnect import KiteConnect

# ================= CONFIG =================
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

app = Flask(__name__)

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_time():
    return datetime.now().strftime("%H:%M %p")

# ================= WATCHLIST =================

INDEX_LIST = ["NIFTY 50", "NIFTY BANK", "SENSEX"]

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

    width = abs(tc - bc)
    return (width / pivot) * 100


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


def get_token(symbol):
    instruments = kite.instruments("NSE")
    for i in instruments:
        if i["tradingsymbol"] == symbol:
            return i["instrument_token"]
    return None

# ================= INDEX SCANNER (5 MIN) =================

def index_scanner():
    print("📊 Index Scanner Started")

    last_signal = {}

    while True:
        try:
            for idx in INDEX_LIST:

                token = get_token(idx)
                if not token:
                    continue

                data = kite.historical_data(
                    token,
                    from_date="2026-04-25",
                    to_date="2026-04-27",
                    interval="5minute"
                )

                df = pd.DataFrame(data)
                if len(df) < 30:
                    continue

                df = calculate_obv(df)

                bull, bear, last, cpr, roc = check_signal(df)

                price = round(last["close"], 2)

                if idx not in last_signal:
                    last_signal[idx] = ""

                if bull and last_signal[idx] != "CALL":

                    msg = f"""
📊 CPR STRATEGY ALERT

🟢 Signal: OBV Bullish
📈 Symbol: {idx}

🔹 CPR: {round(cpr,2)}% (Narrow)
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Up

💰 Price: {price}
⏰ Time: {get_time()}
"""

                    send_telegram(msg)
                    last_signal[idx] = "CALL"

                elif bear and last_signal[idx] != "PUT":

                    msg = f"""
📊 CPR STRATEGY ALERT

🔴 Signal: OBV Bearish
📈 Symbol: {idx}

🔹 CPR: {round(cpr,2)}% (Narrow)
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Down

💰 Price: {price}
⏰ Time: {get_time()}
"""

                    send_telegram(msg)
                    last_signal[idx] = "PUT"

            time.sleep(300)

        except Exception as e:
            print("Index Error:", e)
            time.sleep(60)

# ================= STOCK SCANNER (15 MIN) =================

def stock_scanner():
    print("📈 Stock Scanner Started")

    last_signal = {}

    while True:
        try:
            for stock in STOCK_LIST:

                token = get_token(stock)
                if not token:
                    continue

                data = kite.historical_data(
                    token,
                    from_date="2026-04-25",
                    to_date="2026-04-27",
                    interval="15minute"
                )

                df = pd.DataFrame(data)
                if len(df) < 30:
                    continue

                df = calculate_obv(df)

                bull, bear, last, cpr, roc = check_signal(df)

                price = round(last["close"], 2)

                if stock not in last_signal:
                    last_signal[stock] = ""

                if bull and last_signal[stock] != "CALL":

                    msg = f"""
📊 CPR STRATEGY ALERT

🟢 Signal: OBV Bullish
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}% (Narrow)
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Up

💰 Price: {price}
⏰ Time: {get_time()}
"""

                    send_telegram(msg)
                    last_signal[stock] = "CALL"

                elif bear and last_signal[stock] != "PUT":

                    msg = f"""
📊 CPR STRATEGY ALERT

🔴 Signal: OBV Bearish
📈 Symbol: {stock}

🔹 CPR: {round(cpr,2)}% (Narrow)
🔹 ROC: {round(roc,2)}
🔹 OBV Trend: Down

💰 Price: {price}
⏰ Time: {get_time()}
"""

                    send_telegram(msg)
                    last_signal[stock] = "PUT"

            time.sleep(300)

        except Exception as e:
            print("Stock Error:", e)
            time.sleep(60)

# ================= FLASK =================

@app.route("/")
def home():
    return "Bot Running"

@app.route('/test')
def test():
    send_telegram("The bot is active and functioning properly.")
    return "Test Mail Sent. Status 200 OK."

@app.route('/emergency')
def emergency():
    send_telegram("There is an error!")
    return "Emergency"

# ================= START =================

if __name__ == "__main__":
    t1 = threading.Thread(target=index_scanner)
    t2 = threading.Thread(target=stock_scanner)

    t1.start()
    t2.start()

    app.run(host="0.0.0.0", port=10000)
