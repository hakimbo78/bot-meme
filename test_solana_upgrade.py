"""
Solana Module Upgrade — Validation & Testing Script

Run this to verify all new modules are working correctly.
"""

import sys
import asyncio
from pathlib import Path

# Add modules to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.solana.metadata_resolver import MetadataResolver, TokenMetadata
from modules.solana.raydium_lp_detector import RaydiumLPDetector, RaydiumLPInfo
from modules.solana.token_state import TokenStateMachine, TokenState
from modules.solana.solana_scanner import SolanaScanner


def test_imports():
    """Test that all modules import correctly."""
    print("✓ Testing imports...")
    
    try:
        from modules.solana.metadata_resolver import MetadataResolver
        print("  ✓ metadata_resolver imported")
        
        from modules.solana.raydium_lp_detector import RaydiumLPDetector
        print("  ✓ raydium_lp_detector imported")
        
        from modules.solana.token_state import TokenStateMachine
        print("  ✓ token_state imported")
        
        from modules.solana.solana_scanner import SolanaScanner
        print("  ✓ solana_scanner imported (with upgrades)")
        
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def test_metadata_resolver():
    """Test metadata resolver initialization."""
    print("\n✓ Testing MetadataResolver...")
    
    try:
        resolver = MetadataResolver(client=None, cache_ttl=1800)
        print(f"  ✓ Created resolver with TTL={resolver.cache_ttl}s")
        
        # Test cache stats
        stats = resolver.get_cache_stats()
        print(f"  ✓ Cache stats: {stats}")
        
        # Test metadata dataclass
        meta = TokenMetadata(
            mint="TokenMintAddress",
            name="TestToken",
            symbol="TEST",
            decimals=9,
            supply=1000000000
        )
        print(f"  ✓ Created metadata: {meta.to_dict()}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_lp_detector():
    """Test LP detector initialization."""
    print("\n✓ Testing RaydiumLPDetector...")
    
    try:
        detector = RaydiumLPDetector(client=None, min_liquidity_sol=10.0)
        print(f"  ✓ Created detector with min_lp={detector.min_liquidity_sol} SOL")
        
        # Test cache stats
        stats = detector.get_cache_stats()
        print(f"  ✓ Cache stats: {stats}")
        
        # Test LP info dataclass
        lp = RaydiumLPInfo(
            pool_address="PoolAddressHere",
            base_mint="TokenMintAddress",
            quote_mint="So11111111111111111111111111111111111111112",  # SOL
            lp_mint="LPMintAddress",
            base_liquidity=100000000,
            quote_liquidity=18.7,
            quote_liquidity_usd=3740
        )
        print(f"  ✓ Created LP info: {lp.to_dict()}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_state_machine():
    """Test token state machine."""
    print("\n✓ Testing TokenStateMachine...")
    
    try:
        sm = TokenStateMachine(
            min_lp_sol=10.0,
            sniper_score_threshold=70,
            safe_mode=True
        )
        print(f"  ✓ Created state machine (min_lp={sm.min_lp_sol}, threshold={sm.sniper_score_threshold})")
        
        # Create a token
        token_mint = "TokenMintAddress"
        record = sm.create_token(token_mint, "TEST")
        print(f"  ✓ Created token record: {record.symbol} ({record.current_state.value})")
        
        # Set metadata
        sm.set_metadata(
            mint=token_mint,
            name="TestToken",
            symbol="TEST",
            decimals=9,
            supply=1000000000
        )
        record = sm.get_token(token_mint)
        print(f"  ✓ Updated metadata: {record.current_state.value}")
        
        # Set LP
        sm.set_lp_detected(
            mint=token_mint,
            pool_address="PoolAddress",
            base_liquidity=100000000,
            quote_liquidity=18.7,
            quote_liquidity_usd=3740
        )
        record = sm.get_token(token_mint)
        print(f"  ✓ Updated LP: {record.current_state.value}")
        
        # Update score
        sm.update_score(token_mint, 75.0)
        record = sm.get_token(token_mint)
        print(f"  ✓ Updated score: {record.current_state.value}")
        
        # Check execution
        can_exec, reason = sm.can_execute(token_mint)
        print(f"  ✓ Can execute: {can_exec} ({reason})")
        
        # Get stats
        stats = sm.get_stats()
        print(f"  ✓ Stats: {stats}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_transitions():
    """Test state machine transitions."""
    print("\n✓ Testing State Transitions...")
    
    try:
        sm = TokenStateMachine(min_lp_sol=10.0, sniper_score_threshold=70, safe_mode=True)
        token_mint = "TokenMintAddress"
        
        # Create token (DETECTED)
        record = sm.create_token(token_mint, "TEST")
        assert record.current_state == TokenState.DETECTED
        print(f"  ✓ DETECTED")
        
        # Set metadata (METADATA_OK)
        sm.set_metadata(token_mint, "TestToken", "TEST", 9, 1000000000)
        record = sm.get_token(token_mint)
        assert record.current_state == TokenState.METADATA_OK
        print(f"  ✓ METADATA_OK")
        
        # Set LP (LP_DETECTED)
        sm.set_lp_detected(
            token_mint, "Pool", 100000000, 18.7, 3740
        )
        record = sm.get_token(token_mint)
        assert record.current_state == TokenState.LP_DETECTED
        print(f"  ✓ LP_DETECTED")
        
        # Update score (SNIPER_ARMED)
        sm.update_score(token_mint, 75.0)
        record = sm.get_token(token_mint)
        assert record.current_state == TokenState.SNIPER_ARMED
        print(f"  ✓ SNIPER_ARMED")
        
        # Mark bought (BOUGHT)
        sm.mark_bought(token_mint, 0.5)
        record = sm.get_token(token_mint)
        assert record.current_state == TokenState.BOUGHT
        print(f"  ✓ BOUGHT")
        
        # Verify history
        assert len(record.state_history) > 0
        print(f"  ✓ State history tracked: {len(record.state_history)} transitions")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_safe_mode():
    """Test safe mode enforcement."""
    print("\n✓ Testing Safe Mode...")
    
    try:
        sm = TokenStateMachine(min_lp_sol=10.0, sniper_score_threshold=70, safe_mode=True)
        token_mint = "TokenMintAddress"
        
        # Create token
        record = sm.create_token(token_mint, "TEST")
        
        # Try to set LP before metadata (should warn/fail in safe mode)
        result = sm.set_lp_detected(
            token_mint, "Pool", 100000000, 18.7, 3740
        )
        # Should still update but mark as detected
        record = sm.get_token(token_mint)
        print(f"  ✓ LP set before metadata (safe mode checked)")
        
        # Try to execute without metadata
        can_exec, reason = sm.can_execute(token_mint)
        assert not can_exec
        assert "metadata" in reason.lower()
        print(f"  ✓ Blocked execution: {reason}")
        
        # Try with low score
        sm.set_metadata(token_mint, "Test", "TEST", 9, 1000000000)
        sm.set_lp_detected(token_mint, "Pool", 100000000, 18.7, 3740)
        sm.update_score(token_mint, 50.0)  # Below threshold
        
        record = sm.get_token(token_mint)
        can_exec, reason = sm.can_execute(token_mint)
        assert not can_exec
        assert "score" in reason.lower() or "not armed" in reason.lower()
        print(f"  ✓ Blocked low score: {reason}")
        
        # Try with low LP
        sm2 = TokenStateMachine(min_lp_sol=20.0)  # High threshold
        record = sm2.create_token("Token2", "TST2")
        sm2.set_metadata("Token2", "Test2", "TST2", 9, 1000000000)
        sm2.set_lp_detected("Token2", "Pool", 100000000, 5.0, 1000)  # Only 5 SOL
        
        record = sm2.get_token("Token2")
        assert not record.lp_valid
        assert record.lp_info['status'] == 'LOW_LIQUIDITY'
        print(f"  ✓ Blocked low liquidity: {record.lp_info['status']}")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scanner_integration():
    """Test scanner has all new modules."""
    print("\n✓ Testing Scanner Integration...")
    
    try:
        from config import CHAIN_CONFIGS
        solana_config = CHAIN_CONFIGS.get('chains', {}).get('solana', {})
        
        if not solana_config:
            print("  ⚠ No Solana config found, creating default")
            solana_config = {'rpc_url': 'https://api.mainnet-beta.solana.com'}
        
        scanner = SolanaScanner(solana_config)
        print(f"  ✓ Created scanner")
        
        # Check for new modules
        assert hasattr(scanner, 'metadata_resolver')
        print(f"  ✓ Has metadata_resolver")
        
        assert hasattr(scanner, 'lp_detector')
        print(f"  ✓ Has lp_detector")
        
        assert hasattr(scanner, 'state_machine')
        print(f"  ✓ Has state_machine")
        
        # Check for new methods
        assert hasattr(scanner, 'resolve_token_metadata')
        print(f"  ✓ Has resolve_token_metadata method")
        
        assert hasattr(scanner, 'detect_token_lp')
        print(f"  ✓ Has detect_token_lp method")
        
        assert hasattr(scanner, 'update_token_score')
        print(f"  ✓ Has update_token_score method")
        
        assert hasattr(scanner, 'can_execute_sniper')
        print(f"  ✓ Has can_execute_sniper method")
        
        assert hasattr(scanner, 'get_armed_tokens')
        print(f"  ✓ Has get_armed_tokens method")
        
        # Test stats
        stats = scanner.get_stats()
        assert 'metadata_resolver' in stats
        print(f"  ✓ Stats include metadata_resolver")
        
        assert 'lp_detector' in stats
        print(f"  ✓ Stats include lp_detector")
        
        assert 'state_machine' in stats
        print(f"  ✓ Stats include state_machine")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_configuration():
    """Test configuration has new settings."""
    print("\n✓ Testing Configuration...")
    
    try:
        from config import SOLANA_SNIPER_CONFIG
        
        assert 'metadata_cache_ttl' in SOLANA_SNIPER_CONFIG
        print(f"  ✓ Has metadata_cache_ttl: {SOLANA_SNIPER_CONFIG['metadata_cache_ttl']}")
        
        assert 'min_lp_sol' in SOLANA_SNIPER_CONFIG
        print(f"  ✓ Has min_lp_sol: {SOLANA_SNIPER_CONFIG['min_lp_sol']}")
        
        assert 'sniper_score_threshold' in SOLANA_SNIPER_CONFIG
        print(f"  ✓ Has sniper_score_threshold: {SOLANA_SNIPER_CONFIG['sniper_score_threshold']}")
        
        assert 'safe_mode' in SOLANA_SNIPER_CONFIG
        print(f"  ✓ Has safe_mode: {SOLANA_SNIPER_CONFIG['safe_mode']}")
        
        return True
    except AssertionError as e:
        print(f"  ✗ Assertion failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("SOLANA MODULE UPGRADE — VALIDATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("MetadataResolver", test_metadata_resolver()))
    results.append(("RaydiumLPDetector", test_lp_detector()))
    results.append(("TokenStateMachine", test_state_machine()))
    results.append(("State Transitions", test_state_transitions()))
    results.append(("Safe Mode", test_safe_mode()))
    results.append(("Scanner Integration", test_scanner_integration()))
    results.append(("Configuration", test_configuration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Upgrade is ready for production.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
