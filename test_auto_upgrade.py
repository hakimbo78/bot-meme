"""
Test Script for Auto-Upgrade System

Tests all components of the TRADE → SNIPER upgrade workflow:
1. Priority Detector
2. Smart Wallet Detector
3. Auto-Upgrade Engine
4. Integration Module
"""

import json
import time
from pathlib import Path


def test_priority_detector():
    """Test TX priority detection."""
    print("\n" + "="*60)
    print("TEST 1: Priority Detector")
    print("="*60)
    
    try:
        from solana.priority_detector import SolanaPriorityDetector
        
        detector = SolanaPriorityDetector()
        
        # Mock transaction with high compute and priority fee
        mock_tx = {
            'signature': 'test_sig_123',
            'meta': {
                'computeUnitsConsumed': 250000,  # High compute (>200k)
                'fee': 25000  # Priority fee (20k above base 5k)
            },
            'transaction': {
                'message': {
                    'accountKeys': [],
                    'instructions': []
                }
            }
        }
        
        result = detector.analyze_transaction(mock_tx)
        
        print(f"✓ Priority Score: {result['priority_score']}/50")
        print(f"✓ Is Priority: {result['is_priority']}")
        print(f"✓ Reasons: {len(result['priority_reasons'])}")
        for reason in result['priority_reasons']:
            print(f"  - {reason}")
        
        assert result['is_priority'], "Expected priority flag to be True"
        assert result['priority_score'] > 0, "Expected priority score > 0"
        
        print("\n✅ Priority Detector: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Priority Detector: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_smart_wallet_detector():
    """Test smart wallet detection."""
    print("\n" + "="*60)
    print("TEST 2: Smart Wallet Detector")
    print("="*60)
    
    try:
        from solana.smart_wallet_detector import SmartWalletDetector
        
        # Ensure database exists
        db_path = Path("data/smart_wallets.json")
        if not db_path.exists():
            print("⚠️  Creating test wallet database...")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            test_db = {
                "test_elite_wallet": {
                    "address": "TestEliteWallet",
                    "total_trades": 15,
                    "wins": 12,
                    "avg_profit_multiplier": 3.2,
                    "early_entries": 10,
                    "last_updated": int(time.time())
                }
            }
            with open(db_path, 'w') as f:
                json.dump(test_db, f, indent=2)
        
        detector = SmartWalletDetector()
        
        # Test with known elite wallet
        result = detector.analyze_wallets(['TestEliteWallet', 'unknown_wallet'])
        
        print(f"✓ Smart Wallet Score: {result['smart_wallet_score']}/40")
        print(f"✓ Is Smart Money: {result['is_smart_money']}")
        print(f"✓ Highest Tier: {result['highest_tier']}")
        print(f"✓ Detected Wallets: {len(result['detected_wallets'])}")
        for wallet in result['detected_wallets']:
            print(f"  - {wallet['tier_name']}: {wallet['address']} ({wallet['wins']}/{wallet['total_trades']} wins)")
        
        assert result['is_smart_money'], "Expected smart money flag to be True"
        assert result['smart_wallet_score'] > 0, "Expected smart wallet score > 0"
        assert result['highest_tier'] == 1, "Expected tier 1 (elite) wallet"
        
        # Test tier stats
        stats = detector.get_tier_stats()
        print(f"✓ Database Stats: {stats['total']} total, {stats['tier1']} tier-1")
        
        print("\n✅ Smart Wallet Detector: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Smart Wallet Detector: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_upgrade_engine():
    """Test auto-upgrade engine."""
    print("\n" + "="*60)
    print("TEST 3: Auto-Upgrade Engine")
    print("="*60)
    
    try:
        from sniper.auto_upgrade import AutoUpgradeEngine
        
        engine = AutoUpgradeEngine({
            'enabled': True,
            'upgrade_threshold': 85,
            'max_monitoring_minutes': 30
        })
        
        # Test registration
        mock_token_data = {
            'address': 'test_token_abc123',
            'name': 'Test Token',
            'symbol': 'TEST',
            'chain': 'solana',
            'liquidity_usd': 100000,
            'age_minutes': 5.0
        }
        
        mock_score_data = {
            'score': 72,
            'alert_level': 'TRADE',
            'verdict': 'TRADE'
        }
        
        registered = engine.register_trade_alert(mock_token_data, mock_score_data)
        print(f"✓ Token Registered: {registered}")
        assert registered, "Expected token to be registered"
        
        # Test upgrade check with signals
        new_signals = {
            'priority_score': 20,
            'smart_wallet_score': 40,
            'priority_reasons': ['High priority fee'],
            'smart_wallet_reasons': ['Elite wallet detected']
        }
        
        upgrade_result = engine.check_upgrade('test_token_abc123', new_signals)
        
        print(f"✓ Should Upgrade: {upgrade_result['should_upgrade']}")
        print(f"✓ Final Score: {upgrade_result['final_score']}")
        print(f"✓ Score Breakdown:")
        for key, value in upgrade_result['score_breakdown'].items():
            print(f"  - {key}: {value}")
        
        # 72 (base) + 20 (priority) + 40 (smart wallet) = 132, capped at 95
        # Should upgrade if final_score >= 85
        assert upgrade_result['final_score'] >= 85, f"Expected final score >= 85, got {upgrade_result['final_score']}"
        assert upgrade_result['should_upgrade'], "Expected upgrade to be approved"
        
        # Test monitoring summary
        summary = engine.get_monitoring_summary()
        print(f"✓ Monitoring Summary:")
        print(f"  - Active: {summary['active_count']}")
        print(f"  - Upgraded: {summary['upgraded_count']}")
        
        print("\n✅ Auto-Upgrade Engine: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Auto-Upgrade Engine: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """Test full integration."""
    print("\n" + "="*60)
    print("TEST 4: Integration Module")
    print("="*60)
    
    try:
        from upgrade_integration import UpgradeIntegration
        from config import PRIORITY_DETECTOR_CONFIG, SMART_WALLET_CONFIG, AUTO_UPGRADE_ENGINE_CONFIG
        
        integration = UpgradeIntegration({
            'priority_detector': PRIORITY_DETECTOR_CONFIG,
            'smart_wallet': SMART_WALLET_CONFIG,
            'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
        })
        
        print(f"✓ Integration Enabled: {integration.enabled}")
        
        # Test signal checking
        mock_tx = {
            'signature': 'test_sig_456',
            'meta': {
                'computeUnitsConsumed': 220000,
                'fee': 15000
            },
            'transaction': {
                'message': {
                    'accountKeys': [],
                    'instructions': []
                }
            }
        }
        
        signals = integration.check_signals(
            'test_token_xyz',
            transaction_data=mock_tx,
            wallet_addresses=['TestEliteWallet']  # From test database
        )
        
        print(f"✓ Signals Detected:")
        print(f"  - Priority Score: {signals['priority_score']}/50")
        print(f"  - Smart Wallet Score: {signals['smart_wallet_score']}/40")
        print(f"  - Is Priority: {signals['is_priority']}")
        print(f"  - Is Smart Money: {signals['is_smart_money']}")
        
        # Test monitoring summary
        summary = integration.get_monitoring_summary()
        print(f"✓ Monitoring Summary:")
        for key, value in summary.items():
            print(f"  - {key}: {value}")
        
        print("\n✅ Integration Module: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration Module: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AUTO-UPGRADE SYSTEM TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Priority Detector", test_priority_detector()))
    results.append(("Smart Wallet Detector", test_smart_wallet_detector()))
    results.append(("Auto-Upgrade Engine", test_auto_upgrade_engine()))
    results.append(("Integration Module", test_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review errors above.")
    
    print("="*60)


if __name__ == "__main__":
    main()
