from kiteconnect import KiteConnect
from token_store import save_token

API_KEY = "rynalfq2ew07gxmc"
API_SECRET = "0kskgjs8t4d42x1i93engxnkenqu1229"

request_token = input("Paste request token here: ")

kite = KiteConnect(api_key=API_KEY)

data = kite.generate_session(request_token, api_secret=API_SECRET)

access_token = data["access_token"]

save_token(access_token)

print("✅ Token Updated Successfully")