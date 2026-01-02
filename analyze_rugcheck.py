"""
Check RugCheck API capabilities for a specific token
"""
import requests
import json

token = "82hVfzp5MV97cdztarpsn4EhgVCdMpYzkcwMQmWTwK6T"

print(f"\n{'='*80}")
print(f"RUGCHECK API ANALYSIS")
print(f"Token: {token}")
print(f"{'='*80}\n")

# Fetch RugCheck report
url = f"https://api.rugcheck.xyz/v1/tokens/{token}/report"
response = requests.get(url, timeout=10)

if response.status_code == 200:
    data = response.json()
    
    # Pretty print key findings
    print("KEY METRICS:")
    print(f"  Token Name: {data.get('tokenMeta', {}).get('name', 'Unknown')}")
    print(f"  Symbol: {data.get('tokenMeta', {}).get('symbol', 'Unknown')}")
    
    # Risk level
    risks = data.get('risks', [])
    print(f"\n  Total Risks Found: {len(risks)}")
    
    if risks:
        print(f"\n  RISK DETAILS:")
        for risk in risks[:10]:  # Show first 10
            name = risk.get('name', 'Unknown')
            level = risk.get('level', 'unknown')
            description = risk.get('description', '')
            print(f"    - [{level.upper()}] {name}")
            if description:
                print(f"      {description[:100]}...")
    
    # Top holders
    top_holders = data.get('topHolders', [])
    if top_holders:
        print(f"\n  TOP HOLDERS:")
        total_pct = 0
        for holder in top_holders[:5]:
            pct = holder.get('pct', 0)
            total_pct += pct
            print(f"    - {pct:.2f}%")
        print(f"  Top 5 Total: {total_pct:.2f}%")
    
    # Liquidity info
    markets = data.get('markets', [])
    if markets:
        print(f"\n  MARKETS:")
        for m in markets[:3]:
            liq = m.get('liquidityA', {})
            liq_usd = liq.get('usd', 0)
            lp_locked = m.get('lpLockedPct', 0)
            lp_burned = m.get('lpBurnedPct', 0)
            print(f"    - Liquidity: ${liq_usd:,.0f}")
            print(f"      LP Locked: {lp_locked:.1f}%")
            print(f"      LP Burned: {lp_burned:.1f}%")
    
    # Overall score
    score = data.get('score', 0)
    print(f"\n  RUGCHECK SCORE: {score}/100")
    
    # Save full JSON for analysis
    with open('rugcheck_sample.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Full data saved to: rugcheck_sample.json")
    
else:
    print(f"❌ API Error: {response.status_code}")
    print(f"Response: {response.text}")

print(f"\n{'='*80}\n")
