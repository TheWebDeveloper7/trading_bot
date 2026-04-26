from kiteconnect import KiteConnect
import requests
import time

# 🔹 Zerodha API
api_key = "rynalfq2ew07gxmc"
access_token = "5p9Q7yAFQv7RaFaYEGm1VgjQonPEx0jE"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# 🔹 Telegram
TELEGRAM_TOKEN = "8678481015:AAEVn-NmnBtgclf0jruQUVCvDM6mhVT_Ipc"
CHAT_ID = "969392553"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# 🔹 Track price
last_price = None

while True:
    try:
        data = kite.ltp("NSE:RELIANCE")  # you can change symbol
        price = data["NSE:RELIANCE"]["last_price"]

        print("Price:", price)
        send_telegram(price)

        # 🔹 Simple alert condition
        if last_price and price > last_price:
            send_telegram(f"📈 Price Going UP: {price}")

        if last_price and price < last_price:
            send_telegram(f"📉 Price Going DOWN: {price}")

        last_price = price
        time.sleep(10)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)