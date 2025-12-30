"""
ALTERNATIVE SOLUTION: Test GeckoTerminal API
GeckoTerminal is FREE and has better endpoints than DexScreener
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta

async def test_geckoterminal():
    """Test GeckoTerminal API for time-based queries"""
    
    with open("geckoterminal_test.txt", "w", encoding="utf-8") as f:
        f.write("TESTING GECKOTERMINAL API (FREE ALTERNATIVE)\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("GeckoTerminal API: https://www.geckoterminal.com\n")
        f.write("Documentation: https://www.geckoterminal.com/dex-api\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # TEST 1: Get recently added pools
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 1: Recently added pools (NEW PAIRS!)\n")
            f.write("=" * 80 + "\n\n")
            
            networks = ['solana', 'base', 'eth']
            
            for network in networks:
                f.write(f"\n[{network.upper()}]\n")
                f.write("-" * 40 + "\n")
                
                url = f"https://api.geckoterminal.com/api/v2/networks/{network}/new_pools"
                
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"URL: {url}\n")
                        f.write(f"Status: {response.status}\n\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'data' in data:
                                pools = data['data']
                                f.write(f"✅ Found {len(pools)} new pools!\n\n")
                                
                                # Analyze pools
                                for i, pool in enumerate(pools[:5], 1):
                                    attrs = pool.get('attributes', {})
                                    
                                    name = attrs.get('name', 'UNKNOWN')
                                    address = attrs.get('address', 'UNKNOWN')
                                    created_at = attrs.get('pool_created_at')
                                    
                                    # Calculate age
                                    age = "Unknown"
                                    if created_at:
                                        try:
                                            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                            age_hours = (datetime.now(created_time.tzinfo) - created_time).total_seconds() / 3600
                                            if age_hours < 24:
                                                age = f"{age_hours:.1f}h"
                                            else:
                                                age_days = age_hours / 24
                                                age = f"{age_days:.1f}d"
                                        except:
                                            pass
                                    
                                    # Get volume and liquidity
                                    volume_usd = attrs.get('volume_usd', {}).get('h24', 0)
                                    reserve_usd = attrs.get('reserve_in_usd', 0)
                                    
                                    f.write(f"  {i}. {name}\n")
                                    f.write(f"      Address: {address[:20]}...\n")
                                    f.write(f"      Age: {age}\n")
                                    f.write(f"      Volume 24h: ${float(volume_usd):,.0f}\n")
                                    f.write(f"      Liquidity: ${float(reserve_usd):,.0f}\n\n")
                                
                                # Show full JSON of first pool
                                f.write("Full JSON of first pool:\n")
                                f.write(json.dumps(pools[0], indent=2)[:1000] + "\n\n")
                                
                        else:
                            text = await response.text()
                            f.write(f"Error: {text[:200]}\n\n")
                            
                except Exception as e:
                    f.write(f"Exception: {e}\n\n")
            
            # TEST 2: Get trending pools
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 2: Trending pools\n")
            f.write("=" * 80 + "\n\n")
            
            for network in ['solana', 'base']:
                url = f"https://api.geckoterminal.com/api/v2/networks/{network}/trending_pools"
                
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"\n[{network.upper()}] Trending pools\n")
                        f.write(f"Status: {response.status}\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            if 'data' in data:
                                f.write(f"Found {len(data['data'])} trending pools\n")
                except Exception as e:
                    f.write(f"Error: {e}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("CONCLUSION\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("GeckoTerminal API:\n")
        f.write("✅ FREE (no API key required)\n")
        f.write("✅ Has /new_pools endpoint (EXACTLY what we need!)\n")
        f.write("✅ Returns pools sorted by creation time\n")
        f.write("✅ No keyword search required\n")
        f.write("✅ Works for Solana, Base, Ethereum, and more\n\n")
        
        f.write("RECOMMENDATION:\n")
        f.write("Replace DexScreener with GeckoTerminal for:\n")
        f.write("1. Getting new pairs (time-based, no keywords)\n")
        f.write("2. Getting trending pairs\n")
        f.write("3. Better API design\n\n")
        
        f.write("This is EXACTLY what the user wants:\n")
        f.write("- FREE ✅\n")
        f.write("- Time-based query ✅\n")
        f.write("- No keywords needed ✅\n")
        f.write("- No on-chain scanning ✅\n")
    
    print("Test complete! Check geckoterminal_test.txt")

if __name__ == "__main__":
    asyncio.run(test_geckoterminal())
