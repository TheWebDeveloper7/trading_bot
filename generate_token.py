from kiteconnect import KiteConnect

api_key = "rynalfq2ew07gxmc"
api_secret = "0kskgjs8t4d42x1i93engxnkenqu1229"
request_token = "EQcHI9JUCdnZhFGEpT2lRYH8VcX52fj9"

kite = KiteConnect(api_key=api_key)

data = kite.generate_session(request_token, api_secret=api_secret)

print("Access Token:", data["access_token"])