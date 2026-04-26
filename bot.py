from flask import Flask
import threading
import time
import os
import requests
import pandas as pd
from kiteconnect import KiteConnect

# ================= CONFIG (ENV VARIABLES) =================
API_KEY = os.getenv("API_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ================= INIT =================
kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

app = Flask(__name__)

# ================= TELEGRAM =================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ================= INDICATORS =================
def calculate_indicators(df):
    df["pivot"] = (df["high"] + df["low"] + df["close"]) / 3
    df["bc"] = (df["high"] + df["low"]) / 2
    df["tc"] = df["pivot"] + (df["pivot"] - df["bc"])

    # CPR width
    df["cpr_width"] = abs(df["tc"] - df["bc"])
    df["cpr_percent"] = (df["cpr_width"] / df["close"]) * 100
    df["is_narrow"] = df["cpr_percent"] < 0.3

    # ROC
    df["roc"] = df["close"].pct_change() * 100
    df["roc_rising"] = df["roc"] > df["roc"].shift(1)
    df["roc_falling"] = df["roc"] < df["roc"].shift(1)

    # OBV
    df["direction"] = (df["close"] > df["close"].shift(1)).astype(int)
    df["direction"] = df["direction"].replace(0, -1)
    df["obv"] = (df["volume"] * df["direction"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20).mean()

    return df

# ================= STRATEGY =================
def check_signal(df):
    latest = df.iloc[-1]

    callScore = 0
    putScore = 0

    # CALL CONDITIONS
    if latest["close"] > latest["tc"]:
        callScore += 1

    if latest["close"] > (latest["high"] - (latest["high"] - latest["low"]) * 0.25):
        callScore += 2

    if latest["roc"] > 0 and latest["roc_rising"]:
        callScore += 1

    if latest["obv"] > latest["obv_ema"]:
        callScore += 1

    if latest["is_narrow"]:
        callScore += 2

    # PUT CONDITIONS
    if latest["close"] < latest["bc"]:
        putScore += 1

    if latest["close"] < (latest["low"] + (latest["high"] - latest["low"]) * 0.25):
        putScore += 2

    if latest["roc"] < 0 and latest["roc_falling"]:
        putScore += 1

    if latest["obv"] < latest["obv_ema"]:
        putScore += 1

    if latest["is_narrow"]:
        putScore += 2

    return callScore, putScore, latest

# ================= MAIN BOT LOOP =================
def run_bot():
    print("Bot Started...")

    last_signal = None

    while True:
        try:
            # Example: RELIANCE token (change later)
            instrument_token = 738561

            data = kite.historical_data(
                instrument_token,
                from_date="2024-01-01",
                to_date="2024-12-31",
                interval="5minute"
            )

            df = pd.DataFrame(data)

            if df.empty:
                print("No data")
                time.sleep(60)
                continue

            df = calculate_indicators(df)

            callScore, putScore, latest = check_signal(df)

            message = f"""
📊 BTST SIGNAL

Price: {latest['close']}
CPR: {'NARROW' if latest['is_narrow'] else 'WIDE'}

CALL Score: {callScore}
PUT Score: {putScore}
"""

            print(message)

            # SIGNAL LOGIC
            if callScore >= 7 and last_signal != "CALL":
                send_telegram("📈 STRONG CALL SIGNAL\n" + message)
                last_signal = "CALL"

            elif putScore >= 7 and last_signal != "PUT":
                send_telegram("📉 STRONG PUT SIGNAL\n" + message)
                last_signal = "PUT"

            time.sleep(300)  # 5 min

        except Exception as e:
            print("Error:", e)
            time.sleep(60)

# ================= FLASK =================
@app.route('/')
def home():
    return "Bot is running"

@app.route('/test')
def test():
    send_telegram("✅ Bot is working from Render!")
    return "Test sent"

@app.route('/rishit')
def rishit():
    send_telegram("Hello XYZ! Welcome to the Website... Hope you have a wonderful day ahead!!")
    return "Fully functional"

# ================= START =================
if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    app.run(host="0.0.0.0", port=10000)