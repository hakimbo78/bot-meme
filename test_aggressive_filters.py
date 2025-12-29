"""
TEST SCRIPT - AGGRESSIVE MODE FILTERS

Test the new 3-level filtering system with realistic scenarios.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from offchain.filters import OffChainFilter
from offchain_config import get_offchain_config

def test_filters():
    """Test filters with various scenarios."""
    
    config = get_offchain_config()
    filter_obj = OffChainFilter(config['filters'])
    
    print("="*60)
    print("TESTING AGGRESSIVE MODE FILTERS")
    print("="*60)
    
    # Test cases
    test_cases = [
        {
            "name": "Early Solana - Low volume but has txns",
            "pair": {
                "pair_address": "0xSOLANA1",
                "chain": "solana",
                "liquidity": 15000,
                "volume_1h": 0,  # NO h1 volume yet
                "volume_24h": 220,
                "tx_1h": 1,  # 1 transaction in 1h
                "tx_24h": 6,
                "price_change_1h": 0.4,
                "price_change_24h": 6.2,
            },
            "expected": True,  # Should PASS
            "reason": "Has tx_1h=1 (+1), price_change_1h>0 (+1), price_change_24h>5% (+1) = score 3"
        },
        {
            "name": "Base New Pair - Zero h1 but active 24h",
            "pair": {
                "pair_address": "0xBASE1",
                "chain": "base",
                "liquidity": 12000,
                "volume_1h": 0,
                "volume_24h": 500,
                "tx_1h": 0,
                "tx_24h": 8,
                "price_change_1h": 0,
                "price_change_24h": 12.5,
            },
            "expected": False,  # Should FAIL at Level-1 (score too low)
            "reason": "Level-0 passes (24h activity), but Level-1 score=1 (D24h>5%) < 3 → FAIL"
        },
        {
            "name": "Dead Pair - No activity",
            "pair": {
                "pair_address": "0xDEAD1",
                "chain": "base",
                "liquidity": 50000,
                "volume_1h": 0,
                "volume_24h": 0,
                "tx_1h": 0,
                "tx_24h": 0,
                "price_change_1h": 0,
                "price_change_24h": 0,
            },
            "expected": False,  # Should FAIL at Level-0
            "reason": "No activity in 24h"
        },
        {
            "name": "Active Pair - Good momentum",
            "pair": {
                "pair_address": "0xACTIVE1",
                "chain": "base",
                "liquidity": 85000,
                "volume_1h": 55,
                "volume_24h": 1200,
                "tx_1h": 4,
                "tx_24h": 42,
                "price_change_1h": 8.5,
                "price_change_24h": 25.3,
            },
            "expected": True,  # Should PASS
            "reason": "Vol1h>=50 (+2), Tx1h>=3 (+2), D1h>0 (+1), D24h>5% (+1) = score 6"
        },
        {
            "name": "Fake Liquidity Pool",
            "pair": {
                "pair_address": "0xFAKE1",
                "chain": "ethereum",
                "liquidity": 600000,  # High liquidity
                "volume_1h": 0,
                "volume_24h": 50,  # Very low volume
                "tx_1h": 0,
                "tx_24h": 2,  # Very low txns
                "price_change_1h": 0,
                "price_change_24h": 0.1,
            },
            "expected": False,  # Should FAIL at Level-2
            "reason": "Fake liquidity: liq>500k but vol24h<200 and tx24h<10"
        },
        {
            "name": "Medium Momentum - Edge case",
            "pair": {
                "pair_address": "0xEDGE1",
                "chain": "base",
                "liquidity": 18000,
                "volume_1h": 25,  # >= 20
                "volume_24h": 300,
                "tx_1h": 2,  # < 3
                "tx_24h": 15,
                "price_change_1h": 2.1,
                "price_change_24h": 7.8,
            },
            "expected": True,  # Should PASS
            "reason": "Vol1h>=20 (+1), D1h>0 (+1), D24h>5% (+1) = score 3"
        },
    ]
    
    print("\n")
    passed_count = 0
    failed_count = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}: {test['name']}")
        print(f"{'='*60}")
        
        pair = test['pair']
        expected = test['expected']
        
        print(f"Input:")
        print(f"  Liq: ${pair['liquidity']:,}")
        print(f"  Vol1h: ${pair['volume_1h']}, Vol24h: ${pair['volume_24h']}")
        print(f"  Tx1h: {pair['tx_1h']}, Tx24h: {pair['tx_24h']}")
        print(f"  D1h: {pair['price_change_1h']:+.1f}%, D24h: {pair['price_change_24h']:+.1f}%")
        
        # Run filter
        passed, reason, metadata = filter_obj.apply_filters(pair)
        
        print(f"\nResult:")
        print(f"  Passed: {passed}")
        if not passed:
            print(f"  Reason: {reason}")
        if metadata:
            print(f"  Metadata: {metadata}")
        
        print(f"\nExpected: {expected}")
        print(f"Reasoning: {test['reason']}")
        
        # Check if result matches expectation
        if passed == expected:
            print(f"[PASS] TEST PASSED")
            passed_count += 1
        else:
            print(f"[FAIL] TEST FAILED - Expected {expected}, got {passed}")
            failed_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed_count}/{len(test_cases)}")
    print(f"Failed: {failed_count}/{len(test_cases)}")
    
    # Stats
    print("\n" + "="*60)
    print("FILTER STATS")
    print("="*60)
    stats = filter_obj.get_stats()
    for key, value in stats.items():
        if 'pct' in key:
            print(f"{key}: {value:.1f}%")
        else:
            print(f"{key}: {value}")
    
    return passed_count == len(test_cases)


if __name__ == "__main__":
    success = test_filters()
    sys.exit(0 if success else 1)
