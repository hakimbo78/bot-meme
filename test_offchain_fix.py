"""
OFFCHAIN SCREENER FIX VERIFICATION TEST

Tests that the DexScreener API fix correctly:
1. Derives virtual 5m metrics from h1 data
2. Applies filters using virtual metrics
3. Emits pairs that pass filters
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from offchain.dex_screener import DexScreenerAPI
from offchain.normalizer import PairNormalizer
from offchain.filters import OffChainFilter
from offchain_config import get_offchain_config


async def test_virtual_5m_fix():
    """Test the virtual 5m metrics fix."""
    
    print("=" * 80)
    print("OFFCHAIN SCREENER FIX VERIFICATION")
    print("=" * 80)
    print()
    
    # Initialize components
    config = get_offchain_config()
    
    dex_screener = DexScreenerAPI(config.get('dexscreener', {}))
    normalizer = PairNormalizer()
    filter_engine = OffChainFilter(config.get('filters', {}))
    
    print("✅ Initialized components")
    print(f"   - Config: {config.get('filters', {})}")
    print()
    
    # Test all enabled chains
    enabled_chains = config.get('enabled_chains', ['base', 'ethereum', 'solana'])
    
    for chain in enabled_chains:
        print(f"\n{'=' * 80}")
        print(f"Testing Chain: {chain.upper()}")
        print(f"{'=' * 80}\n")
        
        # Fetch trending pairs
        print(f"📡 Fetching trending pairs from DexScreener ({chain})...")
        raw_pairs = await dex_screener.fetch_trending_pairs(chain=chain, limit=10)
        
        print(f"   Raw pairs fetched: {len(raw_pairs)}")
        
        if not raw_pairs:
            print(f"   ⚠️  No pairs returned for {chain}")
            continue
        
        print()
        
        # Test normalization and filtering
        passed_count = 0
        failed_count = 0
        
        for idx, raw_pair in enumerate(raw_pairs[:5], 1):  # Test first 5
            print(f"\n--- Pair {idx}/{min(5, len(raw_pairs))} ---")
            
            # Extract key info
            pair_address = raw_pair.get('pairAddress', 'N/A')
            token_symbol = raw_pair.get('baseToken', {}).get('symbol', 'UNKNOWN')
            
            print(f"Token: {token_symbol}")
            print(f"Pair:  {pair_address[:10]}...")
            
            # Normalize
            normalized = normalizer.normalize_dexscreener(raw_pair)
            
            # Show virtual 5m metrics
            print(f"\n📊 RAW API DATA (h1):")
            print(f"   - volume.h1:  ${normalized.get('volume_1h', 0):,.2f}")
            print(f"   - txns.h1:    {normalized.get('tx_1h', 0)}")
            print(f"   - price_change.h1: {normalized.get('price_change_1h', 0):.2f}%")
            
            print(f"\n📊 VIRTUAL 5m METRICS (h1/12):")
            print(f"   - volume_5m:  ${normalized.get('volume_5m', 0):,.2f}")
            print(f"   - tx_5m:      {normalized.get('tx_5m', 0):.2f}")
            
            print(f"\n📊 OTHER METRICS:")
            print(f"   - liquidity:  ${normalized.get('liquidity', 0):,.2f}")
            
            # Apply filters
            passed, reason = filter_engine.apply_filters(normalized)
            
            if passed:
                print(f"\n✅ PASSED ALL FILTERS")
                passed_count += 1
                
                # Show why it passed
                vol_5m = normalized.get('volume_5m', 0)
                tx_5m = normalized.get('tx_5m', 0)
                price_1h = normalized.get('price_change_1h', 0)
                
                print(f"\n🎯 Why it passed:")
                print(f"   - Virtual vol_5m ${vol_5m:.2f} >= ${filter_engine.min_volume_5m_virtual}")
                print(f"   - Virtual tx_5m {tx_5m:.2f} >= {filter_engine.min_tx_5m_virtual}")
                print(f"   - Price_change_1h {price_1h:.2f}% >= {filter_engine.min_price_change_1h}% OR volume spike")
                
            else:
                print(f"\n❌ FAILED: {reason}")
                failed_count += 1
        
        print(f"\n{'=' * 80}")
        print(f"CHAIN SUMMARY: {chain.upper()}")
        print(f"{'=' * 80}")
        print(f"✅ Passed: {passed_count}")
        print(f"❌ Failed: {failed_count}")
        print()
    
    # Close session
    await dex_screener.close()
    
    # Final stats
    stats = filter_engine.get_stats()
    print(f"\n{'=' * 80}")
    print(f"OVERALL FILTER STATISTICS")
    print(f"{'=' * 80}")
    print(f"Total evaluated: {stats['total_evaluated']}")
    print(f"Level-0 filtered: {stats['level0_filtered']}")
    print(f"Level-1 filtered: {stats['level1_filtered']}")
    print(f"✅ Passed: {stats['passed']}")
    print(f"Filter rate: {stats['filter_rate_pct']:.1f}%")
    print()
    
    if stats['passed'] > 0:
        print("🎉 SUCCESS! The off-chain screener is now emitting pairs!")
        print()
        print("✅ FIXES APPLIED:")
        print("   1. Virtual 5m volume = h1 / 12")
        print("   2. Virtual 5m tx count = h1 / 12")
        print("   3. Use h1 price change directly (no scaling)")
        print("   4. Updated config parameters")
        print("   5. Simplified filter logic")
        return True
    else:
        print("⚠️  WARNING: No pairs passed filters")
        print("   This may be normal if there's low market activity")
        print("   Try running during peak hours or lower thresholds")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_virtual_5m_fix())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
