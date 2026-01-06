import requests
import json

token = "9BsasuPUQQcBx85X1Km6mjzFxxJmHkGg1mZfuHFrcy5P"
url = f"https://api.rugcheck.xyz/v1/tokens/{token}/report"
resp = requests.get(url, timeout=15)

if resp.status_code == 200:
    data = resp.json()
    
    print(f"BONDING: {data.get('bondingProgress')}")
    print(f"COMPLETED: {data.get('isCompleted')}")
    
    markets = data.get('markets', [])
    print(f"\nMARKETS: {len(markets)}")
    for m in markets:
        print("-" * 20)
        print(f"DEX: {m.get('dex')}")
        print(f"TYPE: {m.get('type')}")
        
    # Save full JSON
    with open('dronex_rugcheck.json', 'w') as f:
        json.dump(data, f, indent=2)
else:
    print(f"Error: {resp.status_code}")
