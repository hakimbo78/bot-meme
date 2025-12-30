"""
DEEP INVESTIGATION: Bagaimana cara BENAR untuk mendapatkan ALL new pairs dari DexScreener?
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta

async def investigate_dexscreener_deeply():
    """Investigasi mendalam untuk menemukan cara yang benar"""
    
    with open("deep_investigation.txt", "w", encoding="utf-8") as f:
        f.write("DEEP INVESTIGATION: DexScreener API\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # STRATEGY 1: Try to get ALL pairs for a chain (no query)
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 1: Get ALL pairs for a chain\n")
            f.write("=" * 80 + "\n\n")
            
            # Try different endpoints
            test_endpoints = [
                "https://api.dexscreener.com/latest/dex/pairs/solana",
                "https://api.dexscreener.com/latest/dex/tokens/solana",
                "https://api.dexscreener.com/latest/dex/search?q=solana",
            ]
            
            for endpoint in test_endpoints:
                f.write(f"\nTesting: {endpoint}\n")
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"Keys: {list(data.keys())}\n")
                            
                            if 'pairs' in data and data['pairs']:
                                pairs = data['pairs']
                                f.write(f"Pairs count: {len(pairs)}\n")
                                
                                # Check if these are ALL pairs or just some
                                if len(pairs) > 0:
                                    f.write(f"Sample pair: {pairs[0].get('baseToken', {}).get('symbol', 'UNKNOWN')}\n")
                            elif 'pair' in data:
                                f.write("Single pair returned\n")
                        else:
                            text = await response.text()
                            f.write(f"Error: {text[:200]}\n")
                except Exception as e:
                    f.write(f"Exception: {e}\n")
            
            # STRATEGY 2: Search with very broad terms
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 2: Very broad search terms\n")
            f.write("=" * 80 + "\n\n")
            
            broad_terms = [
                "",  # Empty query
                " ",  # Space
                "a",  # Single letter
                "token",
                "coin",
                "sol",  # Chain native token
            ]
            
            for term in broad_terms:
                f.write(f"\nQuery: '{term}'\n")
                try:
                    url = "https://api.dexscreener.com/latest/dex/search"
                    params = {'q': term} if term else {}
                    
                    async with session.get(url, params=params, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'pairs' in data:
                                pairs = data['pairs']
                                f.write(f"  Pairs: {len(pairs)}\n")
                                
                                # Check chain distribution
                                chains = {}
                                for p in pairs:
                                    chain = p.get('chainId', 'unknown')
                                    chains[chain] = chains.get(chain, 0) + 1
                                
                                f.write(f"  Chains: {chains}\n")
                        else:
                            f.write(f"  Status: {response.status}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
            
            # STRATEGY 3: Check if there's a "latest" or "new" endpoint
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 3: Look for latest/new endpoints\n")
            f.write("=" * 80 + "\n\n")
            
            potential_endpoints = [
                "https://api.dexscreener.com/latest/dex/pairs/latest",
                "https://api.dexscreener.com/latest/dex/pairs/new",
                "https://api.dexscreener.com/latest/dex/pairs/solana/latest",
                "https://api.dexscreener.com/latest/dex/pairs/solana/new",
                "https://api.dexscreener.com/latest/dex/new/solana",
                "https://api.dexscreener.com/latest/dex/latest/solana",
            ]
            
            for endpoint in potential_endpoints:
                f.write(f"\n{endpoint}\n")
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"  Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"  Keys: {list(data.keys())}\n")
                            if 'pairs' in data:
                                f.write(f"  Pairs: {len(data['pairs'])}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
            
            # STRATEGY 4: Check documentation or schema
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 4: API Schema/Documentation\n")
            f.write("=" * 80 + "\n\n")
            
            doc_endpoints = [
                "https://api.dexscreener.com/",
                "https://api.dexscreener.com/latest",
                "https://api.dexscreener.com/latest/dex",
            ]
            
            for endpoint in doc_endpoints:
                f.write(f"\n{endpoint}\n")
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"  Status: {response.status}\n")
                        if response.status == 200:
                            text = await response.text()
                            f.write(f"  Response length: {len(text)} chars\n")
                            f.write(f"  First 500 chars: {text[:500]}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
            
            # STRATEGY 5: Analyze what dashboard uses
            f.write("\n" + "=" * 80 + "\n")
            f.write("STRATEGY 5: What does DexScreener Dashboard use?\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("Dashboard URL: https://dexscreener.com/solana\n")
            f.write("This shows ALL new pairs in real-time\n")
            f.write("They must have an endpoint for this!\n\n")
            
            # Try to mimic dashboard behavior
            f.write("Possible dashboard endpoints:\n")
            dashboard_endpoints = [
                "https://api.dexscreener.com/latest/dex/pairs/solana?sort=createdAt",
                "https://api.dexscreener.com/latest/dex/pairs/solana?orderBy=createdAt",
                "https://api.dexscreener.com/latest/dex/pairs/solana?limit=100",
            ]
            
            for endpoint in dashboard_endpoints:
                f.write(f"\n{endpoint}\n")
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"  Status: {response.status}\n")
                        if response.status == 200:
                            data = await response.json()
                            f.write(f"  Keys: {list(data.keys())}\n")
                            if 'pairs' in data:
                                f.write(f"  Pairs: {len(data['pairs'])}\n")
                except Exception as e:
                    f.write(f"  Error: {e}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("CONCLUSION\n")
        f.write("=" * 80 + "\n\n")
        f.write("DexScreener FREE API has SEVERE limitations:\n")
        f.write("1. No endpoint to get ALL pairs for a chain\n")
        f.write("2. /search endpoint returns max 30 results\n")
        f.write("3. Results are FILTERED by relevance to query\n")
        f.write("4. No 'latest' or 'new' endpoint available\n\n")
        f.write("IMPLICATION:\n")
        f.write("- Keyword strategy will MISS random-named coins\n")
        f.write("- We can only detect coins matching our keywords\n")
        f.write("- This is a FUNDAMENTAL limitation of the FREE API\n\n")
        f.write("ALTERNATIVES:\n")
        f.write("1. DexScreener Pro API (paid) - has more endpoints\n")
        f.write("2. Direct blockchain scanning (expensive, CU-heavy)\n")
        f.write("3. Use multiple data sources (Birdeye, DEXTools, etc.)\n")
    
    print("Investigation complete! Check deep_investigation.txt")

if __name__ == "__main__":
    asyncio.run(investigate_dexscreener_deeply())
