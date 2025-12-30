"""
BREAKTHROUGH TEST: Test /tokens/new, /tokens/recent, /tokens/latest endpoints!
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta

async def test_tokens_endpoints():
    """Test the /tokens/* endpoints that returned 200"""
    
    with open("tokens_endpoints_detailed.txt", "w", encoding="utf-8") as f:
        f.write("DETAILED TEST: /tokens/* ENDPOINTS\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            endpoints = [
                "https://api.dexscreener.com/latest/dex/tokens/new",
                "https://api.dexscreener.com/latest/dex/tokens/recent",
                "https://api.dexscreener.com/latest/dex/tokens/latest",
            ]
            
            for endpoint in endpoints:
                f.write(f"\n{'='*80}\n")
                f.write(f"ENDPOINT: {endpoint}\n")
                f.write(f"{'='*80}\n\n")
                
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"Status: {response.status}\n\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            f.write(f"Response keys: {list(data.keys())}\n")
                            f.write(f"Schema version: {data.get('schemaVersion')}\n\n")
                            
                            pairs = data.get('pairs')
                            f.write(f"Pairs type: {type(pairs)}\n")
                            f.write(f"Pairs is None: {pairs is None}\n")
                            
                            if pairs is not None:
                                f.write(f"Pairs length: {len(pairs)}\n\n")
                                
                                if len(pairs) > 0:
                                    f.write("PAIRS FOUND! Analyzing...\n\n")
                                    
                                    # Analyze chains
                                    chains = {}
                                    for p in pairs:
                                        chain = p.get('chainId', 'unknown')
                                        chains[chain] = chains.get(chain, 0) + 1
                                    
                                    f.write(f"Chains distribution:\n")
                                    for chain, count in sorted(chains.items(), key=lambda x: x[1], reverse=True):
                                        f.write(f"  {chain}: {count}\n")
                                    f.write("\n")
                                    
                                    # Check creation times
                                    cutoff_24h = datetime.now() - timedelta(hours=24)
                                    cutoff_1h = datetime.now() - timedelta(hours=1)
                                    
                                    new_24h = 0
                                    new_1h = 0
                                    
                                    for p in pairs:
                                        created_at = p.get('pairCreatedAt')
                                        if created_at:
                                            try:
                                                created_time = datetime.fromtimestamp(created_at / 1000)
                                                if created_time > cutoff_24h:
                                                    new_24h += 1
                                                if created_time > cutoff_1h:
                                                    new_1h += 1
                                            except:
                                                pass
                                    
                                    f.write(f"Age analysis:\n")
                                    f.write(f"  New (<24h): {new_24h}\n")
                                    f.write(f"  Very new (<1h): {new_1h}\n\n")
                                    
                                    # Show sample pairs
                                    f.write("Sample pairs (first 10):\n")
                                    for i, p in enumerate(pairs[:10], 1):
                                        symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                        chain = p.get('chainId', 'unknown')
                                        
                                        created_at = p.get('pairCreatedAt')
                                        age = "Unknown"
                                        if created_at:
                                            try:
                                                created_time = datetime.fromtimestamp(created_at / 1000)
                                                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                                if age_hours < 24:
                                                    age = f"{age_hours:.1f}h"
                                                else:
                                                    age_days = age_hours / 24
                                                    age = f"{age_days:.1f}d"
                                            except:
                                                pass
                                        
                                        vol = p.get('volume', {}).get('h24', 0)
                                        liq = p.get('liquidity', {}).get('usd', 0)
                                        
                                        f.write(f"  {i}. [{chain}] {symbol} - Age: {age}, Vol: ${vol:,.0f}, Liq: ${liq:,.0f}\n")
                                    
                                    f.write("\n")
                                    
                                    # Full JSON of first pair
                                    f.write("Full JSON of first pair:\n")
                                    f.write(json.dumps(pairs[0], indent=2)[:1500] + "\n")
                                    
                                else:
                                    f.write("Pairs array is EMPTY\n")
                            else:
                                f.write("Pairs is NULL\n")
                                
                        else:
                            text = await response.text()
                            f.write(f"Error: {text[:500]}\n")
                            
                except Exception as e:
                    f.write(f"Exception: {e}\n")
                    import traceback
                    f.write(traceback.format_exc() + "\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("CONCLUSION\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("If these endpoints return actual pairs:\n")
        f.write("✅ We found a way to get new tokens WITHOUT keywords!\n")
        f.write("✅ This is EXACTLY what the user wants!\n")
        f.write("✅ Time-based query is POSSIBLE!\n\n")
        
        f.write("If these endpoints return NULL:\n")
        f.write("❌ These endpoints don't work for public API\n")
        f.write("❌ Need to find alternative solution\n")
    
    print("Test complete! Check tokens_endpoints_detailed.txt")

if __name__ == "__main__":
    asyncio.run(test_tokens_endpoints())
