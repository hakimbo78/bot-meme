"""
TEST SUITE - MODE C: DEGEN SNIPER

Comprehensive test scenarios to validate the DEGEN SNIPER filter implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from degen_sniper_config import get_degen_sniper_config
from degen_sniper_filter import DegenSniperFilter


def test_degen_sniper():
    """Test DEGEN SNIPER filter with various scenarios."""
    
    config = get_degen_sniper_config()
    filter_obj = DegenSniperFilter(config)
    
    print("=" * 80)
    print("MODE C: DEGEN SNIPER - TEST SUITE")
    print("=" * 80)
    print()
    
    # Test cases
    test_cases = [
        {
            "name": "GUARDRAIL REJECT - Low Liquidity",
            "pair": {
                "pair_address": "0xGUARD_LIQ",
                "chain": "base",
                "liquidity": 2500,  # < 3000
                "volume_1h": 100,
                "volume_24h": 5000,
                "tx_1h": 5,
                "tx_24h": 50,
                "price_change_1h": 2.5,
                "price_change_24h": 10.0,
            },
            "expected": False,
            "reason": "Liquidity < $3k (guardrail)",
        },
        {
            "name": "GUARDRAIL REJECT - Zero h24 Volume",
            "pair": {
                "pair_address": "0xGUARD_VOL",
                "chain": "base",
                "liquidity": 15000,
                "volume_1h": 50,
                "volume_24h": 0,  # ZERO
                "tx_1h": 2,
                "tx_24h": 10,
                "price_change_1h": 1.0,
                "price_change_24h": 3.0,
            },
            "expected": False,
            "reason": "Zero h24 volume (guardrail)",
        },
        {
            "name": "LEVEL-0 FAIL - No Viability Signal",
            "pair": {
                "pair_address": "0xLVL0_FAIL",
                "chain": "base",
                "liquidity": 4000,  # < 5000
                "volume_1h": 0,
                "volume_24h": 1500,  # < 2000
                "tx_1h": 0,
                "tx_24h": 3,
                "price_change_1h": 0,
                "price_change_24h": 0.5,
            },
            "expected": False,
            "reason": "No Level-0 viability (Liq<5k AND Vol24h<2k)",
        },
        {
            "name": "ULTRA-EARLY Solana - Pass on Minimal Activity",
            "pair": {
                "pair_address": "0xSOL_EARLY",
                "chain": "solana",
                "liquidity": 8000,  # >= 5000 (Level-0 PASS)
                "volume_1h": 0,  # Ignored for Solana
                "volume_24h": 500,
                "tx_1h": 1,  # Level-1 TRIGGER
                "tx_24h": 12,  # Solana bonus
                "price_change_1h": 0.2,  # Level-1 TRIGGER
                "price_change_24h": 8.5,  # Level-2 condition
            },
            "expected": True,
            "reason": "Score = L1(+1) + bonus(+1 SOL_ACTIVE) = 2... wait needs L2",
        },
        {
            "name": "Fresh LP - Early Base Pair",
            "pair": {
                "pair_address": "0xBASE_FRESH",
                "chain": "base",
                "liquidity": 12000,  # > volume_24h (fresh LP bonus)
                "volume_1h": 15,  # >= 10 (Level-1 TRIGGER)
                "volume_24h": 8000,
                "tx_1h": 2,
                "tx_24h": 25,  # >= 20 (Level-2 condition)
                "price_change_1h": 0.8,  # > 0 (Level-1 TRIGGER)
                "price_change_24h": 12.0,  # >= 5 (Level-2 condition)
            },
            "expected": True,
            "reason": "Score = L1(+1) + L2(+2: GOOD_TXN, VOLATILE) + bonus(+1 WARMUP) = 4 >= 3",
        },
        {
            "name": "High Volume Pair - Strong Signals",
            "pair": {
                "pair_address": "0xSTRONG",
                "chain": "ethereum",
                "liquidity": 65000,  # >= 10k (Level-2 condition)
                "volume_1h": 250,
                "volume_24h": 18000,  # >= 10k (Level-2 condition)
                "tx_1h": 8,
                "tx_24h": 45,  # >= 20 (Level-2 condition)
                "price_change_1h": 5.2,  # > 0 (Level-1 TRIGGER)
                "price_change_24h": 22.5,  # >= 5 (Level-2 condition)
            },
            "expected": True,
            "reason": "Score = L1(+1) + L2(+2: all 4 conditions) + bonus(+1 WARMUP) = 4 >= 3",
        },
        {
            "name": "Low Score - Insufficient Momentum",
            "pair": {
                "pair_address": "0xLOW_SCORE",
                "chain": "base",
                "liquidity": 6000,  # Level-0 PASS
                "volume_1h": 0,  # No Level-1 trigger
                "volume_24h": 3000,  # Level-0 PASS
                "tx_1h": 0,  # No Level-1 trigger
                "tx_24h": 8,
                "price_change_1h": 0,  # No Level-1 trigger
                "price_change_24h": 2.0,  # < 5
            },
            "expected": False,
            "reason": "Score = 0 (no L1, no L2, no bonus) < 3",
        },
        {
            "name": "Edge Case - Exactly Score 3",
            "pair": {
                "pair_address": "0xEDGE_3",
                "chain": "base",
                "liquidity": 5500,
                "volume_1h": 12,  # >= 10 (Level-1 TRIGGER: EARLY_VOL)
                "volume_24h": 4000,
                "tx_1h": 1,  # >= 1 (Level-1 TRIGGER: EARLY_TX)
                "tx_24h": 22,  # >= 20 (Level-2 condition: GOOD_TXN)
                "price_change_1h": 0.1,  # > 0 (Level-1 TRIGGER: PRICE_MOVE)
                "price_change_24h": 6.5,  # >= 5 (Level-2 condition: VOLATILE)
            },
            "expected": True,
            "reason": "Score = L1(+1) + L2(+2: GOOD_TXN + VOLATILE) = 3 (exactly)",
        },
        {
            "name": "Warmup Phase - High h1/h24 Ratio",
            "pair": {
                "pair_address": "0xWARMUP",
                "chain": "base",
                "liquidity": 18000,  # >= 10k (Level-2)
                "volume_1h": 80,
                "volume_24h": 9000,
                "tx_1h": 6,  # ratio = 6/24 = 0.25 >= 0.2 (bonus)
                "tx_24h": 24,  # >= 20 (Level-2)
                "price_change_1h": 1.5,  # > 0 (Level-1)
                "price_change_24h": 8.0,  # >= 5 (Level-2)
            },
            "expected": True,
            "reason": "Score = L1(+1) + L2(+2: GOOD_LIQ + GOOD_TXN + VOLATILE) + bonus(+1 WARMUP) = 4",
        },
        {
            "name": "Solana Active Bonus",
            "pair": {
                "pair_address": "0xSOL_ACTIVE",
                "chain": "solana",
                "liquidity": 22000,  # >= 10k (Level-2)
                "volume_1h": 0,  # OK for Solana
                "volume_24h": 3500,
                "tx_1h": 2,  # >= 1 (Level-1)
                "tx_24h": 18,  # >= 10 (Solana bonus, but < 20 for Level-2)
                "price_change_1h": 2.1,  # > 0 (Level-1)
                "price_change_24h": 11.0,  # >= 5 (Level-2)
            },
            "expected": True,
            "reason": "Score = L1(+1) + L2(+2: GOOD_LIQ + VOLATILE) + bonus(+1 SOL_ACTIVE) = 4",
        },
        {
            "name": "Level-2 Only 1 Condition - Fail",
            "pair": {
                "pair_address": "0xL2_ONLY1",
                "chain": "base",
                "liquidity": 12000,  # >= 10k (Level-2: 1 condition)
                "volume_1h": 15,  # >= 10 (Level-1 TRIGGER)
                "volume_24h": 800,  # < 10k
                "tx_1h": 1,  # >= 1 (Level-1 TRIGGER)
                "tx_24h": 8,  # < 20
                "price_change_1h": 0.5,  # > 0 (Level-1 TRIGGER)
                "price_change_24h": 2.0,  # < 5
            },
            "expected": False,
            "reason": "Score = L1(+1) + L2(0: only GOOD_LIQ, need 2) = 1 < 3",
        },
    ]
    
    print()
    passed_count = 0
    failed_count = 0
    
    for i, test in enumerate(test_cases, 1):
        print("=" * 80)
        print(f"TEST {i}: {test['name']}")
        print("=" * 80)
        
        pair = test['pair']
        expected = test['expected']
        
        print(f"\nInput:")
        print(f"  Chain: {pair['chain'].upper()}")
        print(f"  Liquidity: ${pair['liquidity']:,}")
        print(f"  Volume:  h1=${pair['volume_1h']}, h24=${pair['volume_24h']}")
        print(f"  Txns:    h1={pair['tx_1h']}, h24={pair['tx_24h']}")
        print(f"  ΔPrice:  h1={pair['price_change_1h']:+.1f}%, h24={pair['price_change_24h']:+.1f}%")
        
        # Run filter
        print(f"\nEvaluation:")
        passed, reason, metadata = filter_obj.apply_filters(pair)
        
        print(f"\nResult:")
        print(f"  Passed: {passed}")
        if not passed:
            print(f"  Reason: {reason}")
        if metadata:
            print(f"  Score: {metadata.get('score', 0)}")
            print(f"  Flags: {metadata.get('reason_flags', [])}")
        
        print(f"\nExpected: {expected}")
        print(f"Test Reasoning: {test['reason']}")
        
        # Check if result matches expectation
        if passed == expected:
            print(f"\n✅ [PASS] TEST PASSED")
            passed_count += 1
        else:
            print(f"\n❌ [FAIL] TEST FAILED - Expected {expected}, got {passed}")
            failed_count += 1
        
        print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed_count}/{len(test_cases)}")
    print(f"Failed: {failed_count}/{len(test_cases)}")
    
    # Filter stats
    print()
    print("=" * 80)
    print("FILTER STATISTICS")
    print("=" * 80)
    stats = filter_obj.get_stats()
    for key, value in stats.items():
        if 'pct' in key:
            print(f"{key}: {value:.1f}%")
        else:
            print(f"{key}: {value}")
    
    print()
    print("=" * 80)
    
    return passed_count == len(test_cases)


if __name__ == "__main__":
    success = test_degen_sniper()
    sys.exit(0 if success else 1)
