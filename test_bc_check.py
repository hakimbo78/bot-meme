import requests
import json

token = "52qPXcXpo3us1p3gMiKA1NDqum8MNR3WB5TBwYfu1V8z"
url = f"https://api.rugcheck.xyz/v1/tokens/{token}/report"
resp = requests.get(url, timeout=15)

if resp.status_code == 200:
    data = resp.json()
    
    # Key BC-related info:
    markets = data.get('markets', [])
    print(f"MARKETS: {len(markets)} found")
    for m in markets[:3]:
        dex = m.get('dex', 'Unknown')
        mtype = m.get('type', 'Unknown')
        liq = m.get('liquidityA', {})
        liq_usd = liq.get('usd', 0) if isinstance(liq, dict) else 0
        print(f"  DEX: {dex}, Type: {mtype}, LiqUSD: {liq_usd}")
        
    # BC fields
    bonding = data.get('bondingProgress')
    is_completed = data.get('isCompleted')
    print(f"\nBonding: {bonding}, isCompleted: {is_completed}")
    
    risks = data.get('risks', [])
    print(f"\nRISKS: {len(risks)}")
    for r in risks[:5]:
        level = r.get('level', '?')
        name = r.get('name', 'Unknown')
        print(f"  [{level}] {name}")
    
    # Save full JSON
    with open('rugcheck_macrohard.json', 'w') as f:
        json.dump(data, f, indent=2)
    print("\nSaved to rugcheck_macrohard.json")
else:
    print(f"Error: {resp.status_code}")
