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
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

def get_time():
    return datetime.now().strftime("%H:%M:%S")

# ================= WATCHLIST =================
STOCK_LIST = ["RELIANCE","TCS","INFY","HDFCBANK","ICICIBANK"]

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

# ================= TOKEN FETCH =================
def get_token(symbol):
    try:
        instruments = kite.instruments("NSE")
        for i in instruments:
            if i["tradingsymbol"] == symbol:
                return i["instrument_token"]
    except Exception as e:
        print("Token Error:", e)
    return None

# ================= DEBUG SCANNER =================
def debug_scanner():
    print("🚀 Debug Scanner Started")
    send_telegram("🚀 Bot Started - Debug Mode")

    # ✅ CHECK TOKEN
    try:
        profile = kite.profile()
        send_telegram(f"✅ Token OK: {profile['user_name']}")
    except Exception as e:
        send_telegram(f"❌ TOKEN ERROR: {e}")
        return

    while True:
        try:
            for stock in STOCK_LIST:

                print(f"🔍 Checking {stock}")

                token = get_token(stock)

                if not token:
                    print(f"❌ Token not found for {stock}")
                    continue

                data = kite.historical_data(
                    token,
                    from_date="2026-04-25",
                    to_date="2026-04-27",
                    interval="5minute"
                )

                df = pd.DataFrame(data)

                print(f"{stock} candles: {len(df)}")

                if len(df) < 30:
                    print(f"⚠️ Not enough data for {stock}")
                    continue

                df = calculate_obv(df)

                last = df.iloc[-1]
                prev = df.iloc[-2]

                bull = prev["obv"] < prev["obv_ema"] and last["obv"] > last["obv_ema"]
                bear = prev["obv"] > prev["obv_ema"] and last["obv"] < last["obv_ema"]

                cpr = calculate_cpr(df)
                roc = calculate_roc(df)

                print(f"{stock} | CPR: {round(cpr,2)} | ROC: {round(roc,2)}")

                # 🚀 DEBUG ALERT (ALWAYS SEND ONCE)
                send_telegram(f"""
📊 DEBUG CHECK

📈 {stock}
CPR: {round(cpr,2)}
ROC: {round(roc,2)}
Bull: {bull}
Bear: {bear}
Time: {get_time()}
""")

                # OPTIONAL REAL SIGNAL
                if bull:
                    send_telegram(f"🟢 REAL SIGNAL: {stock} Bullish")

                elif bear:
                    send_telegram(f"🔴 REAL SIGNAL: {stock} Bearish")

                time.sleep(10)

            time.sleep(60)

        except Exception as e:
            print("Loop Error:", e)
            send_telegram(f"❌ BOT ERROR: {e}")
            time.sleep(60)

# ================= FLASK =================
@app.route("/")
def home():
    return "Debug Bot Running"

# ================= START =================
if __name__ == "__main__":
    t = threading.Thread(target=debug_scanner)
    t.start()

    app.run(host="0.0.0.0", port=10000)
