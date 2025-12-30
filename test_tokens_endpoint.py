"""
Test /tokens endpoint untuk melihat apa yang dikembalikan
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json

async def test_tokens_endpoint():
    """Test /tokens/CHAIN endpoint"""
    
    with open("tokens_endpoint_test.txt", "w", encoding="utf-8") as f:
        f.write("TESTING /tokens/CHAIN ENDPOINT\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            for chain in ['base', 'solana']:
                f.write(f"\n{'='*80}\n")
                f.write(f"CHAIN: {chain.upper()}\n")
                f.write(f"{'='*80}\n\n")
                
                url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}"
                
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'pairs' in data:
                                pairs = data['pairs']
                                f.write(f"Total pairs: {len(pairs)}\n\n")
                                
                                # Analyze pairs
                                cutoff_24h = datetime.now() - timedelta(hours=24)
                                cutoff_1h = datetime.now() - timedelta(hours=1)
                                
                                new_24h = []
                                new_1h = []
                                
                                for p in pairs:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff_24h:
                                                new_24h.append(p)
                                            if created_time > cutoff_1h:
                                                new_1h.append(p)
                                        except:
                                            pass
                                
                                f.write(f"New pairs (<24h): {len(new_24h)}\n")
                                f.write(f"New pairs (<1h): {len(new_1h)}\n\n")
                                
                                # Show all pairs
                                f.write("All pairs:\n")
                                for i, p in enumerate(pairs[:20], 1):  # Show first 20
                                    symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                    addr = p.get('baseToken', {}).get('address', 'UNKNOWN')
                                    
                                    vol_24h = p.get('volume', {}).get('h24', 0)
                                    liq = p.get('liquidity', {}).get('usd', 0)
                                    
                                    created_at = p.get('pairCreatedAt')
                                    age = "Unknown"
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                            age_days = age_hours / 24
                                            if age_hours < 24:
                                                age = f"{age_hours:.1f}h"
                                            else:
                                                age = f"{age_days:.1f}d"
                                        except:
                                            pass
                                    
                                    f.write(f"  {i}. {symbol} - Vol: ${vol_24h:,.0f}, Liq: ${liq:,.0f}, Age: {age}\n")
                                    f.write(f"      Address: {addr[:20]}...\n")
                                
                                # Show new pairs if any
                                if new_24h:
                                    f.write(f"\nNEW PAIRS (<24h):\n")
                                    for i, p in enumerate(new_24h, 1):
                                        symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                        created_at = p.get('pairCreatedAt')
                                        created_time = datetime.fromtimestamp(created_at / 1000)
                                        age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                        
                                        vol_24h = p.get('volume', {}).get('h24', 0)
                                        liq = p.get('liquidity', {}).get('usd', 0)
                                        
                                        f.write(f"  {i}. {symbol} - Age: {age_hours:.1f}h, Vol: ${vol_24h:,.0f}, Liq: ${liq:,.0f}\n")
                                
                        else:
                            f.write(f"HTTP Error: {response.status}\n")
                            text = await response.text()
                            f.write(f"Response: {text[:200]}\n")
                            
                except Exception as e:
                    f.write(f"Error: {e}\n")
                    import traceback
                    f.write(traceback.format_exc() + "\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("TEST COMPLETE\n")
        f.write("=" * 80 + "\n")
    
    print("Test complete! Check tokens_endpoint_test.txt")

if __name__ == "__main__":
    asyncio.run(test_tokens_endpoint())
