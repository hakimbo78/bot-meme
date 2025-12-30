"""
FOCUSED TEST: Test the /pairs/{chain}/latest and /pairs/{chain}/new endpoints
"""

import asyncio
import aiohttp
import json

async def test_specific_endpoints():
    """Test specific endpoints that returned 200"""
    
    with open("specific_endpoint_test.txt", "w", encoding="utf-8") as f:
        f.write("TESTING SPECIFIC ENDPOINTS\n")
        f.write("=" * 80 + "\n\n")
        
        async with aiohttp.ClientSession() as session:
            
            # Test these endpoints that returned 200
            endpoints = [
                "https://api.dexscreener.com/latest/dex/pairs/solana/latest",
                "https://api.dexscreener.com/latest/dex/pairs/solana/new",
                "https://api.dexscreener.com/latest/dex/pairs/base/latest",
                "https://api.dexscreener.com/latest/dex/pairs/base/new",
            ]
            
            for endpoint in endpoints:
                f.write(f"\n{'='*80}\n")
                f.write(f"Endpoint: {endpoint}\n")
                f.write(f"{'='*80}\n\n")
                
                try:
                    async with session.get(endpoint, timeout=10) as response:
                        f.write(f"Status: {response.status}\n")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            f.write(f"Response keys: {list(data.keys())}\n\n")
                            
                            # Print full response
                            f.write("Full response:\n")
                            f.write(json.dumps(data, indent=2)[:2000] + "\n\n")
                            
                            # Check pairs
                            if 'pairs' in data:
                                pairs = data['pairs']
                                f.write(f"Pairs type: {type(pairs)}\n")
                                f.write(f"Pairs value: {pairs}\n")
                                
                                if pairs is not None:
                                    f.write(f"Pairs length: {len(pairs)}\n")
                                    if len(pairs) > 0:
                                        f.write(f"\nFirst pair:\n")
                                        f.write(json.dumps(pairs[0], indent=2)[:500] + "\n")
                            
                            # Check pair (singular)
                            if 'pair' in data:
                                pair = data['pair']
                                f.write(f"\nPair (singular) type: {type(pair)}\n")
                                f.write(f"Pair value: {pair}\n")
                                
                                if pair is not None:
                                    f.write(f"\nPair details:\n")
                                    f.write(json.dumps(pair, indent=2)[:500] + "\n")
                        
                        else:
                            text = await response.text()
                            f.write(f"Error response: {text[:500]}\n")
                            
                except Exception as e:
                    f.write(f"Exception: {e}\n")
                    import traceback
                    f.write(traceback.format_exc() + "\n")
            
            # Also test with actual pair addresses
            f.write(f"\n{'='*80}\n")
            f.write("TESTING WITH ACTUAL PAIR ADDRESS\n")
            f.write(f"{'='*80}\n\n")
            
            # Get a real pair address first
            search_url = "https://api.dexscreener.com/latest/dex/search"
            params = {'q': 'raydium'}
            
            async with session.get(search_url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'pairs' in data and data['pairs']:
                        # Get first Solana pair
                        for pair in data['pairs']:
                            if pair.get('chainId') == 'solana':
                                pair_address = pair.get('pairAddress')
                                f.write(f"Testing with pair address: {pair_address}\n\n")
                                
                                # Test /pairs/{chain}/{address}
                                test_url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
                                
                                async with session.get(test_url, timeout=10) as resp:
                                    f.write(f"URL: {test_url}\n")
                                    f.write(f"Status: {resp.status}\n")
                                    
                                    if resp.status == 200:
                                        pair_data = await resp.json()
                                        f.write(f"Keys: {list(pair_data.keys())}\n")
                                        f.write(json.dumps(pair_data, indent=2)[:1000] + "\n")
                                
                                break
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("CONCLUSION\n")
        f.write("=" * 80 + "\n\n")
        f.write("The /pairs/{chain}/latest and /pairs/{chain}/new endpoints:\n")
        f.write("- Return 200 status\n")
        f.write("- But 'pairs' is None\n")
        f.write("- They expect a PAIR ADDRESS, not 'latest' or 'new'\n")
        f.write("- These are NOT endpoints for getting latest/new pairs\n")
    
    print("Test complete! Check specific_endpoint_test.txt")

if __name__ == "__main__":
    asyncio.run(test_specific_endpoints())
