"""
SIMPLE DEBUG: Test DexScreener API
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json

async def test_api():
    """Test DexScreener API"""
    
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write("DEXSCREENER API TEST\n")
        f.write("=" * 80 + "\n\n")
        
        chains = ['base', 'solana']
        
        async with aiohttp.ClientSession() as session:
            for chain in chains:
                f.write(f"\n{'='*80}\n")
                f.write(f"CHAIN: {chain.upper()}\n")
                f.write(f"{'='*80}\n\n")
                
                # Get query
                if chain == 'base':
                    query = '0x4200000000000000000000000000000000000006'
                elif chain == 'solana':
                    query = 'So11111111111111111111111111111111111111112'
                else:
                    query = chain
                
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': query}
                
                try:
                    async with session.get(url, params=params, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'pairs' in data:
                                pairs = data['pairs']
                                f.write(f"Total pairs: {len(pairs)}\n")
                                
                                # Filter by chain
                                chain_pairs = [p for p in pairs if p.get('chainId', '').lower() == chain]
                                f.write(f"Chain pairs: {len(chain_pairs)}\n\n")
                                
                                # Quality filter
                                quality_pairs = []
                                for p in chain_pairs:
                                    vol_24h = p.get('volume', {}).get('h24', 0) if isinstance(p.get('volume'), dict) else 0
                                    vol_24h = float(vol_24h) if vol_24h else 0
                                    
                                    liquidity = p.get('liquidity', {}).get('usd', 0) if isinstance(p.get('liquidity'), dict) else 0
                                    liquidity = float(liquidity) if liquidity else 0
                                    
                                    if vol_24h > 0 and liquidity >= 100:
                                        quality_pairs.append(p)
                                
                                f.write(f"Quality pairs (vol>0, liq>=100): {len(quality_pairs)}\n\n")
                                
                                # Check new pairs
                                cutoff = datetime.now() - timedelta(hours=24)
                                new_pairs = []
                                
                                for p in quality_pairs:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff:
                                                new_pairs.append(p)
                                        except:
                                            pass
                                
                                f.write(f"New pairs (<24h): {len(new_pairs)}\n\n")
                                
                                # Show sample
                                if quality_pairs:
                                    f.write("Sample pairs:\n")
                                    for i, p in enumerate(quality_pairs[:5], 1):
                                        symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                        vol = p.get('volume', {}).get('h24', 0)
                                        liq = p.get('liquidity', {}).get('usd', 0)
                                        
                                        created_at = p.get('pairCreatedAt')
                                        age = "Unknown"
                                        if created_at:
                                            try:
                                                created_time = datetime.fromtimestamp(created_at / 1000)
                                                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                                age = f"{age_hours:.1f}h"
                                            except:
                                                pass
                                        
                                        f.write(f"  {i}. {symbol} - Vol: ${vol:,.0f}, Liq: ${liq:,.0f}, Age: {age}\n")
                            else:
                                f.write("No 'pairs' key in response\n")
                        else:
                            f.write(f"HTTP Error: {response.status}\n")
                            
                except Exception as e:
                    f.write(f"Error: {e}\n")
                    import traceback
                    f.write(traceback.format_exc() + "\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("TEST COMPLETE - Check debug_output.txt\n")
        f.write("=" * 80 + "\n")
    
    print("Test complete! Check debug_output.txt for results.")

if __name__ == "__main__":
    asyncio.run(test_api())
