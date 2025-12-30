"""
DEBUG SCRIPT: Test DexScreener API untuk mendeteksi koin baru

Script ini akan:
1. Melakukan direct API call ke DexScreener
2. Memeriksa apakah API mengembalikan data
3. Membandingkan dengan data yang terlihat di dashboard DexScreener
4. Mengidentifikasi root cause masalah deteksi koin baru
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json
import sys

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Output file
OUTPUT_FILE = "dexscreener_debug_output.txt"

def log(message):
    """Log to both console and file"""
    print(message)
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

async def test_dexscreener_api():
    """Test direct API calls ke DexScreener"""
    
    print("=" * 80)
    print("DEXSCREENER API DEBUG TEST")
    print("=" * 80)
    print()
    
    # Test untuk beberapa chain
    chains_to_test = ['base', 'ethereum', 'solana']
    
    async with aiohttp.ClientSession() as session:
        for chain in chains_to_test:
            print(f"\n{'='*80}")
            print(f"TESTING CHAIN: {chain.upper()}")
            print(f"{'='*80}\n")
            
            # 1. Test Search API (yang digunakan oleh bot)
            await test_search_api(session, chain)
            
            # 2. Test Pairs API (alternatif)
            await test_pairs_api(session, chain)
            
            print()

async def test_search_api(session, chain):
    """Test Search API endpoint"""
    print(f"[1] Testing SEARCH API for {chain}")
    print("-" * 80)
    
    # Get search query (sama seperti di dex_screener.py)
    query = get_search_query(chain)
    print(f"Search Query: {query}")
    
    url = "https://api.dexscreener.com/latest/dex/search"
    params = {'q': query}
    
    try:
        async with session.get(url, params=params, timeout=10) as response:
            print(f"Status Code: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                
                if 'pairs' in data:
                    pairs = data['pairs']
                    print(f"Total pairs returned: {len(pairs)}")
                    
                    # Filter by chain
                    chain_pairs = [p for p in pairs if p.get('chainId', '').lower() == chain]
                    print(f"Pairs for {chain}: {len(chain_pairs)}")
                    
                    if chain_pairs:
                        # Analyze first 5 pairs
                        print(f"\nAnalyzing first 5 pairs:")
                        for i, pair in enumerate(chain_pairs[:5], 1):
                            analyze_pair(pair, i, chain)
                        
                        # Check for new pairs (< 24h old)
                        new_pairs = []
                        cutoff_time = datetime.now() - timedelta(hours=24)
                        
                        for pair in chain_pairs:
                            created_at = pair.get('pairCreatedAt')
                            if created_at:
                                try:
                                    created_time = datetime.fromtimestamp(created_at / 1000)
                                    if created_time > cutoff_time:
                                        new_pairs.append(pair)
                                except:
                                    pass
                        
                        print(f"\n✅ New pairs (< 24h): {len(new_pairs)}")
                        if new_pairs:
                            print("\nSample new pairs:")
                            for i, pair in enumerate(new_pairs[:3], 1):
                                created_at = pair.get('pairCreatedAt')
                                created_time = datetime.fromtimestamp(created_at / 1000)
                                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                                print(f"  {i}. {pair.get('baseToken', {}).get('symbol', 'UNKNOWN')} - Age: {age_hours:.1f}h")
                    else:
                        print(f"❌ No pairs found for {chain}")
                else:
                    print("❌ No 'pairs' key in response")
                    print(f"Response keys: {list(data.keys())}")
            else:
                print(f"❌ HTTP Error: {response.status}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_pairs_api(session, chain):
    """Test alternative Pairs API endpoint"""
    print(f"\n[2] Testing PAIRS API for {chain}")
    print("-" * 80)
    
    # Try to get trending pairs directly
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
    
    try:
        async with session.get(url, timeout=10) as response:
            print(f"Status Code: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                print(f"Response keys: {list(data.keys())}")
                
                if 'pairs' in data:
                    pairs = data['pairs']
                    print(f"Total pairs: {len(pairs)}")
                    
                    if pairs:
                        print("\nFirst 3 pairs:")
                        for i, pair in enumerate(pairs[:3], 1):
                            analyze_pair(pair, i, chain)
                else:
                    print("No 'pairs' key in response")
            else:
                print(f"❌ HTTP Error: {response.status}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

def get_search_query(chain):
    """Get search query for chain (sama seperti di dex_screener.py)"""
    chain = chain.lower()
    if chain == 'base':
        return '0x4200000000000000000000000000000000000006'  # Base WETH
    elif chain == 'solana':
        return 'So11111111111111111111111111111111111111112'  # Wrapped SOL
    elif chain == 'ethereum':
        return '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  # Mainnet WETH
    else:
        return chain

def analyze_pair(pair, index, chain):
    """Analyze a single pair"""
    print(f"\n  Pair #{index}:")
    print(f"    Symbol: {pair.get('baseToken', {}).get('symbol', 'UNKNOWN')}")
    print(f"    Chain: {pair.get('chainId', 'UNKNOWN')}")
    print(f"    Pair Address: {pair.get('pairAddress', 'UNKNOWN')[:20]}...")
    
    # Volume
    volume = pair.get('volume', {})
    vol_24h = volume.get('h24', 0) if isinstance(volume, dict) else 0
    print(f"    Volume 24h: ${vol_24h:,.0f}")
    
    # Liquidity
    liquidity = pair.get('liquidity', {})
    liq_usd = liquidity.get('usd', 0) if isinstance(liquidity, dict) else 0
    print(f"    Liquidity: ${liq_usd:,.0f}")
    
    # Transactions
    txns = pair.get('txns', {})
    if isinstance(txns, dict):
        h24 = txns.get('h24', {})
        if isinstance(h24, dict):
            buys = h24.get('buys', 0)
            sells = h24.get('sells', 0)
            print(f"    Txns 24h: {buys + sells} (B:{buys}, S:{sells})")
    
    # Price change
    price_change = pair.get('priceChange', {})
    if isinstance(price_change, dict):
        h1 = price_change.get('h1', 0)
        h24 = price_change.get('h24', 0)
        print(f"    Price Change: 1h={h1}%, 24h={h24}%")
    
    # Age
    created_at = pair.get('pairCreatedAt')
    if created_at:
        try:
            created_time = datetime.fromtimestamp(created_at / 1000)
            age_hours = (datetime.now() - created_time).total_seconds() / 3600
            age_days = age_hours / 24
            print(f"    Age: {age_days:.2f} days ({age_hours:.1f} hours)")
        except:
            print(f"    Age: Error parsing timestamp")
    
    # Check if it would pass bot filters
    print(f"    Would pass filters:")
    print(f"      - Volume > 0: {'✅' if vol_24h > 0 else '❌'}")
    print(f"      - Liquidity > $100: {'✅' if liq_usd >= 100 else '❌'}")
    print(f"      - Chain match: {'✅' if pair.get('chainId', '').lower() == chain else '❌'}")

async def test_bot_filters():
    """Test bot's actual filter logic"""
    print("\n" + "=" * 80)
    print("TESTING BOT FILTER LOGIC")
    print("=" * 80)
    
    try:
        from offchain.dex_screener import DexScreenerAPI
        from offchain.filters import OffChainFilter
        from offchain.normalizer import PairNormalizer
        from offchain_config import get_offchain_config
        
        config = get_offchain_config()
        
        # Initialize components
        dexscreener = DexScreenerAPI(config.get('dexscreener', {}))
        filter_obj = OffChainFilter(config.get('filters', {}))
        normalizer = PairNormalizer()
        
        print("\nTesting with actual bot components...")
        
        for chain in ['base', 'ethereum', 'solana']:
            print(f"\n[{chain.upper()}]")
            
            # Fetch trending pairs
            trending = await dexscreener.fetch_trending_pairs(chain, limit=10)
            print(f"  Trending pairs: {len(trending)}")
            
            # Fetch new pairs
            new_pairs = await dexscreener.fetch_new_pairs(chain, max_age_minutes=1440)  # 24h
            print(f"  New pairs (24h): {len(new_pairs)}")
            
            # Test filters on first pair
            if trending:
                print(f"\n  Testing filter on first trending pair:")
                raw_pair = trending[0]
                normalized = normalizer.normalize_dexscreener(raw_pair, 'dexscreener')
                
                passed, reason, metadata = filter_obj.apply_filters(normalized)
                
                print(f"    Pair: {normalized.get('token_symbol', 'UNKNOWN')}")
                print(f"    Passed: {'✅' if passed else '❌'}")
                print(f"    Reason: {reason}")
                if metadata:
                    print(f"    Score: {metadata.get('score', 0):.1f}")
                    print(f"    Verdict: {metadata.get('verdict', 'UNKNOWN')}")
        
        await dexscreener.close()
        
    except Exception as e:
        print(f"❌ Error testing bot filters: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function"""
    
    # 1. Test direct API
    await test_dexscreener_api()
    
    # 2. Test bot filters
    await test_bot_filters()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
