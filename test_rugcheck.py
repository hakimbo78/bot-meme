import requests
import time

def test_rugcheck(token_address):
    print(f"Testing RugCheck for: '{token_address}' (Type: {type(token_address)})")
    url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
    print(f"URL: {url}")
    
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error Text: {resp.text}")
        else:
            print("Success!")
            data = resp.json()
            print(f"Score: {data.get('score')}")
    except Exception as e:
        print(f"Exception: {e}")

# Test Logic
# 1. Known good token (USDC on Solana)
print("--- TEST 1: Known Good (USDC) ---")
test_rugcheck("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

# 2. Test provided token names (Need to guess address or mock)
# Since I don't have BBD address from log, I'll test a 'dirty' address
print("\n--- TEST 2: Dirty Input (Space) ---")
test_rugcheck("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v ")

print("\n--- TEST 3: Invalid Input (Garbage) ---")
test_rugcheck("invalid_address_format")
