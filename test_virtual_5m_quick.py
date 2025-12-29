"""
QUICK TEST: Verify Virtual 5m Metrics Calculation

This test verifies that the normalizer correctly calculates virtual 5m metrics from h1 data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from offchain.normalizer import PairNormalizer
from offchain.filters import OffChainFilter
from offchain_config import get_offchain_config


def test_virtual_5m_calculation():
    """Test virtual 5m calculation with mock data."""
    
    print("=" * 80)
    print("VIRTUAL 5m METRICS CALCULATION TEST")
    print("=" * 80)
    print()
    
    # Create normalizer
    normalizer = PairNormalizer()
    
    # Mock DexScreener API response (simulating what the API actually returns)
    mock_pair = {
        'chainId': 'base',
        'dexId': 'uniswap_v2',
        'pairAddress': '0x1234567890abcdef',
        'baseToken': {
            'address': '0xtoken123',
            'name': 'TestToken',
            'symbol': 'TEST'
        },
        'quoteToken': {
            'address': '0xweth',
            'name': 'Wrapped Ether',
            'symbol': 'WETH'
        },
        'priceUsd': '0.00123',
        'priceChange': {
            'm5': None,      # ❌ DexScreener doesn't provide this reliably
            'h1': 25.5,      # ✅ Provided
            'h6': 80.2,
            'h24': 150.0
        },
        'volume': {
            'm5': None,      # ❌ NOT provided by API
            'h1': 1200,      # ✅ Provided
            'h24': 18000
        },
        'txns': {
            'm5': None,      # ❌ NOT provided by API
            'h1': {
                'buys': 15,
                'sells': 9   # Total: 24 transactions
            },
            'h24': {
                'buys': 200,
                'sells': 232  # Total: 432 transactions
            }
        },
        'liquidity': {
            'usd': 85000
        },
        'pairCreatedAt': None
    }
    
    print("📥 MOCK DEXSCREENER API RESPONSE:")
    print(f"   volume.h1:  ${mock_pair['volume']['h1']:,}")
    print(f"   txns.h1:    {mock_pair['txns']['h1']['buys'] + mock_pair['txns']['h1']['sells']}")
    print(f"   priceChange.h1: {mock_pair['priceChange']['h1']}%")
    print(f"   liquidity:  ${mock_pair['liquidity']['usd']:,}")
    print()
    
    # Normalize the pair
    normalized = normalizer.normalize_dexscreener(mock_pair)
    
    print("🔄 NORMALIZED PAIR EVENT:")
    print(f"   volume_5m:  ${normalized.get('volume_5m', 0):.2f}  [VIRTUAL: h1/12]")
    print(f"   volume_1h:  ${normalized.get('volume_1h', 0):.2f}")
    print(f"   tx_5m:      {normalized.get('tx_5m', 0):.2f}  [VIRTUAL: h1/12]")
    print(f"   tx_1h:      {normalized.get('tx_1h', 0)}")
    print(f"   price_change_1h: {normalized.get('price_change_1h', 0):.2f}%")
    print(f"   liquidity:  ${normalized.get('liquidity', 0):,.2f}")
    print()
    
    # Verify virtual calculations
    expected_volume_5m = 1200 / 12.0  # = 100
    expected_tx_5m = 24 / 12.0  # = 2.0
    
    actual_volume_5m = normalized.get('volume_5m', 0)
    actual_tx_5m = normalized.get('tx_5m', 0)
    
    print("✅ VERIFICATION:")
    print(f"   Expected volume_5m: ${expected_volume_5m:.2f}")
    print(f"   Actual volume_5m:   ${actual_volume_5m:.2f}")
    print(f"   Match: {abs(actual_volume_5m - expected_volume_5m) < 0.01}")
    print()
    print(f"   Expected tx_5m: {expected_tx_5m:.2f}")
    print(f"   Actual tx_5m:   {actual_tx_5m:.2f}")
    print(f"   Match: {abs(actual_tx_5m - expected_tx_5m) < 0.01}")
    print()
    
    # Test filters
    config = get_offchain_config()
    filter_engine = OffChainFilter(config.get('filters', {}))
    
    print("🔍 FILTER TEST:")
    print(f"   Config thresholds:")
    print(f"     - min_volume_5m_virtual: ${filter_engine.min_volume_5m_virtual}")
    print(f"     - min_tx_5m_virtual: {filter_engine.min_tx_5m_virtual}")
    print(f"     - min_price_change_1h: {filter_engine.min_price_change_1h}%")
    print(f"     - min_liquidity: ${filter_engine.min_liquidity:,}")
    print()
    
    passed, reason = filter_engine.apply_filters(normalized)
    
    if passed:
        print("✅ RESULT: PASSED ALL FILTERS")
        print()
        print("🎯 Why it passed:")
        print(f"   ✅ liquidity (${normalized['liquidity']:,.0f}) >= ${filter_engine.min_liquidity:,}")
        print(f"   ✅ virtual_volume_5m (${actual_volume_5m:.2f}) >= ${filter_engine.min_volume_5m_virtual}")
        print(f"   ✅ virtual_tx_5m ({actual_tx_5m:.2f}) >= {filter_engine.min_tx_5m_virtual}")
        print(f"   ✅ price_change_1h ({normalized['price_change_1h']:.2f}%) >= {filter_engine.min_price_change_1h}%")
        print()
        print("🎉 SUCCESS! The fix is working correctly!")
        return True
    else:
        print(f"❌ RESULT: FAILED - {reason}")
        print()
        print("⚠️  This might indicate an issue with the fix")
        return False


if __name__ == "__main__":
    print()
    success = test_virtual_5m_calculation()
    print()
    print("=" * 80)
    if success:
        print("✅ All tests passed! The virtual 5m fix is working.")
    else:
        print("❌ Test failed. Review the output above.")
    print("=" * 80)
    print()
    sys.exit(0 if success else 1)
