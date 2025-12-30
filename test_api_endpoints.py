"""
Test DexScreener API Endpoints untuk menemukan endpoint yang tepat
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def test_all_endpoints():
    """Test berbagai endpoint DexScreener"""
    
    with open("api_endpoints_test.txt", "w", encoding="utf-8") as f:
        f.write("DEXSCREENER API ENDPOINTS TEST\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # Test 1: Search with token symbol (not address)
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 1: Search by chain name\n")
            f.write("=" * 80 + "\n")
            
            for chain in ['base', 'solana']:
                url = "https://api.dexscreener.com/latest/dex/search"
                params = {'q': chain}  # Just use chain name
                
                try:
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            chain_pairs = [p for p in pairs if p.get('chainId', '').lower() == chain]
                            
                            f.write(f"\n{chain.upper()}: {len(chain_pairs)} pairs\n")
                            
                            # Check for new pairs
                            cutoff = datetime.now() - timedelta(hours=24)
                            new_count = 0
                            for p in chain_pairs:
                                created_at = p.get('pairCreatedAt')
                                if created_at:
                                    try:
                                        created_time = datetime.fromtimestamp(created_at / 1000)
                                        if created_time > cutoff:
                                            new_count += 1
                                    except:
                                        pass
                            
                            f.write(f"  New pairs (<24h): {new_count}\n")
                            
                            if new_count > 0:
                                f.write("  Sample new pairs:\n")
                                for p in chain_pairs:
                                    created_at = p.get('pairCreatedAt')
                                    if created_at:
                                        try:
                                            created_time = datetime.fromtimestamp(created_at / 1000)
                                            if created_time > cutoff:
                                                symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                                f.write(f"    - {symbol} (Age: {age_hours:.1f}h)\n")
                                        except:
                                            pass
                except Exception as e:
                    f.write(f"Error: {e}\n")
            
            # Test 2: Try tokens/CHAIN endpoint
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 2: Tokens endpoint\n")
            f.write("=" * 80 + "\n")
            
            for chain in ['base', 'solana']:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}"
                
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"\n{chain.upper()}: Status {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"  Response keys: {list(data.keys())}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
            
            # Test 3: Try empty search
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 3: Empty/minimal search\n")
            f.write("=" * 80 + "\n")
            
            url = "https://api.dexscreener.com/latest/dex/search"
            params = {'q': 'a'}  # Minimal query
            
            try:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        f.write(f"\nTotal pairs with 'a': {len(pairs)}\n")
                        
                        # Group by chain
                        by_chain = {}
                        for p in pairs:
                            chain = p.get('chainId', 'unknown')
                            by_chain[chain] = by_chain.get(chain, 0) + 1
                        
                        f.write("By chain:\n")
                        for chain, count in sorted(by_chain.items(), key=lambda x: x[1], reverse=True)[:10]:
                            f.write(f"  {chain}: {count}\n")
            except Exception as e:
                f.write(f"Error: {e}\n")
            
            # Test 4: Try to find "new" or "trending" endpoint
            f.write("\n" + "=" * 80 + "\n")
            f.write("TEST 4: Looking for trending/new endpoints\n")
            f.write("=" * 80 + "\n")
            
            test_urls = [
                "https://api.dexscreener.com/latest/dex/trending",
                "https://api.dexscreener.com/latest/dex/new",
                "https://api.dexscreener.com/latest/dex/pairs/new",
                "https://api.dexscreener.com/latest/dex/pairs/trending",
            ]
            
            for url in test_urls:
                try:
                    async with session.get(url, timeout=10) as response:
                        f.write(f"\n{url}\n")
                        f.write(f"  Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"  Keys: {list(data.keys())}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("TEST COMPLETE\n")
        f.write("=" * 80 + "\n")
    
    print("Test complete! Check api_endpoints_test.txt")

if __name__ == "__main__":
    asyncio.run(test_all_endpoints())
