
import os
import hmac
import hashlib
import base64
import datetime
import requests
import json
from dotenv import load_dotenv

# Load env directly
load_dotenv()

API_KEY = (os.getenv('OKX_API_KEY') or '').strip().strip('"').strip("'")
SECRET_KEY = (os.getenv('OKX_SECRET_KEY') or '').strip().strip('"').strip("'")
PASSPHRASE = (os.getenv('OKX_PASSPHRASE') or '').strip().strip('"').strip("'")

print(f"--- DEBUGGING OKX AUTH ---")
print(f"API Key Length: {len(API_KEY)}")
print(f"Secret Key Length: {len(SECRET_KEY)}")
print(f"Passphrase Length: {len(PASSPHRASE)}")
print(f"API Key Preview: {API_KEY[:4]}...{API_KEY[-4:]}")

def get_timestamp():
    return datetime.datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'

def sign(timestamp, method, request_path, body=''):
    message = f"{timestamp}{method}{request_path}{body}"
    print(f"DEBUG SIGN STRING: [{message}]") # Verify exact string
    mac = hmac.new(
        bytes(SECRET_KEY, encoding='utf8'),
        bytes(message, encoding='utf-8'),
        digestmod=hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode('utf-8')

def test_auth():
    # 1. Check Time
    url_time = "https://www.okx.com/api/v5/public/time"
    try:
        r = requests.get(url_time)
        server_time = int(r.json()['data'][0]['ts'])
        local_time = int(datetime.datetime.now().timestamp() * 1000)
        diff = local_time - server_time
        print(f"\nTime Check:")
        print(f"Server Time: {server_time}")
        print(f"Local Time:  {local_time}")
        print(f"Diff (ms):   {diff}")
        if abs(diff) > 30000:
            print("❌ WARNING: VPS Time is drifting significantly!")
    except Exception as e:
        print(f"Failed to check time: {e}")

    # 2. Test Simple Auth WITH PARAMS (Account Balance)
    # Endpoint: /api/v5/account/balance?ccy=USDT
    method = 'GET'
    path_base = '/api/v5/account/balance'
    params = {'ccy': 'USDT'}
    
    # Sort params manually to simulate what we did in client
    params = dict(sorted(params.items()))
    
    from urllib.parse import urlencode
    query_string = urlencode(params)
    path = f"{path_base}?{query_string}"
    
    timestamp = get_timestamp()
    signature = sign(timestamp, method, path)
    
    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': signature,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json'
    }
    
    print(f"\nTesting Auth Endpoint: {path}")
    try:
        url = f"https://www.okx.com{path}"
        r = requests.get(url, headers=headers)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text}")
        
        if r.json().get('code') == '0':
            print("✅ AUTH SUCCESS! Credentials are valid.")
        else:
            print("❌ AUTH FAILED. Check credentials logic.")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_auth()
