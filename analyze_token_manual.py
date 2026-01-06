import requests
import json
import time
from datetime import datetime, timezone
import sys
import os

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

import asyncio

from security_audit import audit_token
from trading_config import TRADING_CONFIG

async def analyze_manual(pair_address, chain='ethereum'):
    print(f"\n{'='*60}")
    print(f" BOT ANALYSIS SIMULATION")
    print(f"Target: {chain.upper()} | {pair_address}")
    print(f"{'='*60}\n")
    
    # 1. FETCH DATA (DexScreener)
    print("1. DATA COLLECTION (DexScreener)...")
    display_chain = chain
    if chain.lower() == 'eth': display_chain = 'ethereum'
    
    try:
        # Try as token address first (returns all pairs)
        url = f"https://api.dexscreener.com/latest/dex/tokens/{pair_address}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        pairs = data.get('pairs') or []
        if not pairs:
            # Fallback: Try as pair address just in case
            url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            pairs = data.get('pairs') or []
            
        if not pairs:
            print(f"x Error: Token/Pair not found. Using MOCK data for testing...")
            pair = {
                'baseToken': {'address': pair_address, 'name': 'TEST_TOKEN', 'symbol': 'TEST'},
                'liquidity': {'usd': 50000},
                'volume': {'h24': 100000},
                'priceChange': {'h1': 5.5},
                'pairCreatedAt': int((time.time() - 7200) * 1000) # 2 hours ago
            }
            pairs = [pair]
            
        pair = pairs[0]
        token = pair.get('baseToken', {})
        token_address = token.get('address')
        token_name = token.get('name')
        token_symbol = token.get('symbol')
        
        liquidity = pair.get('liquidity', {}).get('usd', 0)
        fdv = pair.get('fdv', 0)
        price_change_1h = pair.get('priceChange', {}).get('h1', 0)
        volume_24h = pair.get('volume', {}).get('h24', 0)
        
        # Calculate Age
        pair_created_at = pair.get('pairCreatedAt', 0)
        if pair_created_at:
            created_time = datetime.fromtimestamp(pair_created_at / 1000, tz=timezone.utc)
            now_time = datetime.now(timezone.utc)
            age_delta = now_time - created_time
            age_hours = age_delta.total_seconds() / 3600
        else:
            age_hours = 0
            
        print(f"   Token: {token_name} ({token_symbol})")
        print(f"   Address: {token_address}")
        print(f"   Age: {age_hours:.2f} hours")
        print(f"   Liquidity: ${liquidity:,.0f}")
        print(f"   Volume 24h: ${volume_24h:,.0f}")
        print(f"   Price Change 1h: {price_change_1h}%")
        
    except Exception as e:
        print(f"x Error fetching DexScreener: {e}")
        return

    print(f"\n{'-'*30}")
    print("2. FILTER CHECKS (Stable Pump Strategy)")
    print(f"{'-'*30}")
    
    # Check 1: Age Filter
    min_age = TRADING_CONFIG['signal_mode']['min_age_hours']
    max_age = TRADING_CONFIG['signal_mode']['max_age_hours']
    
    age_status = "[PASS]" if min_age <= age_hours <= max_age else "[FAIL]"
    print(f"   [Age Filter] {min_age}h < {age_hours:.2f}h < {max_age}h : {age_status}")
    
    # Check 2: Liquidity Filter
    min_liq = TRADING_CONFIG['signal_mode']['min_liquidity']
    liq_status = "[PASS]" if liquidity >= min_liq else "[FAIL]"
    print(f"   [Liquidity Filter] ${liquidity:,.0f} >= ${min_liq:,.0f} : {liq_status}")
    
    # Check 3: Security Audit
    print(f"\n{'-'*30}")
    print("3. SECURITY AUDIT (GoPlus/RugCheck) [ASYNC]")
    print(f"{'-'*30}")
    
    # NOW AWAITING ASYNC CALL
    security_data = await audit_token(token_address, chain)
    
    risk_level = security_data.get('risk_level', 'UNKNOWN')
    risk_score = security_data.get('risk_score', 0)
    
    sec_status = "[FAIL]" if risk_level == 'FAIL' else "[PASS]"
    if risk_level == 'WARN': sec_status = "[WARN] (Pass)"
    
    print(f"   [Security Filter] Level: {risk_level} | Score: {risk_score}/100 : {sec_status}")
    
    print("\n   Detailed Risks:")
    for r in security_data.get('risks', []):
        print(f"   - {r}")
        
    print(f"   Honeypot: {'YES' if security_data.get('is_honeypot') else 'NO'}")
    print(f"   Mintable: {'YES' if security_data.get('is_mintable') else 'NO'}")
    print(f"   LP Locked: {security_data.get('lp_locked_percent', 0)}%")
    print(f"   Top 10 Holders: {security_data.get('top10_holders_percent', 0):.1f}%")

    print(f"\n{'-'*60}")
    print(" FINAL VERDICT")
    print(f"{'-'*60}")
    
    failure_reasons = []
    if age_status == "[FAIL]": failure_reasons.append(f"Age {age_hours:.1f}h outside range {min_age}-{max_age}h")
    if liq_status == "[FAIL]": failure_reasons.append(f"Liquidity ${liquidity:,.0f} < ${min_liq:,.0f}")
    if risk_level == 'FAIL': failure_reasons.append(f"Security Level {risk_level}")
    
    if failure_reasons:
        print(f" SKIPPED / FILTERED OUT")
        for reason in failure_reasons:
            print(f"   - {reason}")
    else:
        print(f" POTENTIAL SIGNAL")
        print(f"   (Pending Off-Chain Score Check - usually requires >70 for BUY)")

if __name__ == "__main__":
    try:
        asyncio.run(analyze_manual("0xfbfdc696243e6b4325f4f9573eb9400f19d436d3", "ethereum"))
    except KeyboardInterrupt:
        pass
