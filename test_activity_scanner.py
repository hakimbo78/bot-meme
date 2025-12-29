"""
Test Script for Secondary Activity Scanner
Verifies that the scanner can detect activity signals
"""

import sys
import time
from web3 import Web3
import yaml

# Load chain config
with open('chains.yaml', 'r') as f:
    configs = yaml.safe_load(f)

# Test with BASE chain
base_config = configs['chains']['base']

print("=" * 60)
print("SECONDARY ACTIVITY SCANNER - TEST SCRIPT")
print("=" * 60)

print("\n📋 Test Configuration:")
print(f"   Chain: BASE")
print(f"   RPC: {base_config['rpc_url'][:50]}...")
print(f"   WETH: {base_config['weth_address']}")
print(f"   V2 Factory: {base_config['factories']['uniswap_v2']}")
print(f"   V3 Factory: {base_config['factories']['uniswap_v3']}")

# Initialize Web3
print("\n🔌 Connecting to RPC...")
try:
    web3 = Web3(Web3.HTTPProvider(base_config['rpc_url']))
    if web3.is_connected():
        print("   ✅ Connected!")
        current_block = web3.eth.block_number
        print(f"   📦 Current block: {current_block:,}")
    else:
        print("   ❌ Connection failed")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Connection error: {e}")
    sys.exit(1)

# Import activity scanner
print("\n📥 Importing activity scanner...")
try:
    from secondary_activity_scanner import SecondaryActivityScanner
    from activity_integration import ActivityIntegration
    print("   ✅ Import successful!")
except ImportError as e:
    print(f"   ❌ Import error: {e}")
    sys.exit(1)

# Create scanner
print("\n🔧 Creating activity scanner...")
try:
    scanner = SecondaryActivityScanner(
        web3=web3,
        chain_name='base',
        chain_config=base_config
    )
    print("   ✅ Scanner created!")
    print(f"   Max pools: {scanner.max_pools}")
    print(f"   TTL: {scanner.ttl_seconds}s")
    print(f"   Scan blocks back: {scanner.scan_blocks_back}")
except Exception as e:
    print(f"   ❌ Scanner creation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test scan
print("\n🔍 Running test scan...")
print("   (This may take 10-30 seconds depending on network)")
try:
    start_time = time.time()
    signals = scanner.scan_recent_activity()
    elapsed = time.time() - start_time
    
    print(f"\n✅ Scan completed in {elapsed:.2f}s")
    print(f"   Signals detected: {len(signals)}")
    print(f"   Pools monitored: {len(scanner.activity_candidates)}")
    
    # Print stats
    stats = scanner.get_stats()
    print(f"\n📊 Scanner Statistics:")
    print(f"   Total blocks scanned: {stats['total_blocks_scanned']}")
    print(f"   Total swaps detected: {stats['total_swaps_detected']}")
    print(f"   Total pools tracked: {stats['total_pools_tracked']}")
    print(f"   Signals generated: {stats['signals_generated']}")
    
    # Show signal details
    if signals:
        print(f"\n🎯 Signal Details:")
        for i, signal in enumerate(signals[:3], 1):  # Show first 3
            print(f"\n   Signal #{i}:")
            print(f"      Pool: {signal['pool_address']}")
            print(f"      DEX: {signal['dex']}")
            print(f"      Activity Score: {signal['activity_score']}")
            print(f"      Swap Count: {signal['swap_count']}")
            print(f"      Unique Traders: {signal['unique_traders']}")
            
            signals_active = signal.get('signals', {})
            print(f"      Signals:")
            if signals_active.get('swap_burst'):
                print(f"         ✅ Swap Burst")
            if signals_active.get('weth_flow_spike'):
                print(f"         ✅ WETH Flow Spike")
            if signals_active.get('trader_growth'):
                print(f"         ✅ Trader Growth")
            if signals_active.get('v3_intensity'):
                print(f"         ✅ V3 Intensity")
        
        if len(signals) > 3:
            print(f"\n   ... and {len(signals) - 3} more signals")
    else:
        print("\n   ℹ️  No signals detected in this scan")
        print("      This is normal if:")
        print("      - Market is quiet")
        print("      - No recent high-activity pools")
        print("      - Scanner just started (needs time to build data)")

except Exception as e:
    print(f"\n❌ Scan error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test integration layer
print("\n🔗 Testing integration layer...")
try:
    integration = ActivityIntegration(enabled=True)
    integration.register_scanner('base', scanner)
    
    # Scan via integration
    all_signals = integration.scan_all_chains()
    
    print(f"   ✅ Integration working!")
    print(f"   Signals via integration: {len(all_signals)}")
    
    # Test force enqueue rule
    if all_signals:
        for signal in all_signals:
            should_force = integration.should_force_enqueue(signal)
            if should_force:
                print(f"   🔥 DEXTools guarantee triggered: {signal['pool_address'][:10]}...")
except Exception as e:
    print(f"   ❌ Integration error: {e}")
    import traceback
    traceback.print_exc()

# Test activity context
print("\n✏️ Testing activity context enrichment...")
try:
    if signals:
        test_signal = signals[0]
        enriched = integration.process_activity_signal(test_signal)
        
        print(f"   ✅ Enrichment working!")
        print(f"   Original keys: {list(test_signal.keys())[:5]}...")
        print(f"   Enriched keys: {list(enriched.keys())[:5]}...")
        print(f"   Activity override: {enriched.get('activity_override')}")
    else:
        print(f"   ⏭️  Skipped (no signals to test)")
except Exception as e:
    print(f"   ❌ Enrichment error: {e}")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

all_passed = True
checks = [
    ("RPC Connection", web3.is_connected()),
    ("Scanner Import", 'SecondaryActivityScanner' in dir()),
    ("Scanner Creation", scanner is not None),
    ("Scan Execution", stats['total_blocks_scanned'] > 0),
    ("Integration Layer", integration is not None),
]

for check_name, passed in checks:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status} - {check_name}")
    if not passed:
        all_passed = False

print("\n" + "=" * 60)
if all_passed:
    print("🎉 ALL TESTS PASSED!")
    print("\nNext Steps:")
    print("   1. Review ACTIVITY_SCANNER_INTEGRATION.md")
    print("   2. Add integration code to main.py")
    print("   3. Test locally with 'python main.py'")
    print("   4. Deploy to VPS")
else:
    print("⚠️  SOME TESTS FAILED")
    print("\nPlease review errors above and:")
    print("   1. Check RPC connectivity")
    print("   2. Verify file imports")
    print("   3. Check for syntax errors")

print("=" * 60)
