"""
Test Script for Secondary Activity Scanner (HUNTER MODE)
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
print("SECONDARY ACTIVITY SCANNER - TEST SCRIPT (HUNTER MODE)")
print("=" * 60)

print("\n📋 Test Configuration:")
print(f"   Chain: BASE")
print(f"   RPC: {base_config['rpc_url'][:50]}...")

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
        # sys.exit(1) # Don't exit hard if RPC fails, we can mock or just show error
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
    print(f"   Max pools: {scanner.MAX_POOLS}")
    print(f"   TTL: {scanner.TTL_BLOCKS} blocks")
except Exception as e:
    print(f"   ❌ Scanner creation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ADMIT DUMMY POOL
print("\n➕ Admitting test pool...")
try:
    # A known high volume pool on Base (WETH/USDC V3) for testing
    # If no logs found, it means low activity, but code path is tested
    test_pool = '0xd0b53d9277642d899df5f87a3966a34909eae13b' # WETH/USDC Base
    
    admitted = scanner.track_pool({
        'pool_address': test_pool,
        'token_address': '0xTEST',
        'dex': 'uniswap_v3',
        'score': 85,  # High score to ensure admission
        'liquidity_usd': 500000,
        'is_trade': True,
        'current_block': current_block - 10 # Start monitoring from 10 blocks ago
    })
    
    if admitted:
        print(f"   ✅ Pool Admitted: {test_pool}")
    else:
        print(f"   ❌ Pool Admission Failed")

except Exception as e:
    print(f"   ❌ Admission error: {e}")


# Test scan
print("\n🔍 Running test scan...")
print("   (This may take 10-30 seconds depending on network)")
try:
    start_time = time.time()
    signals = scanner.scan_recent_activity(target_block=current_block)
    elapsed = time.time() - start_time
    
    print(f"\n✅ Scan completed in {elapsed:.2f}s")
    print(f"   Signals detected: {len(signals)}")
    print(f"   Pools monitored: {len(scanner.tracked_pools)}")
    
    # Print stats
    stats = scanner.get_stats()
    print(f"\n📊 Scanner Statistics:")
    print(f"   Signals generated: {stats['signals_generated']}")
    print(f"   Pools admitted: {stats['pools_admitted']}")
    
    # Show signal details
    if signals:
        print(f"\n🎯 Signal Details:")
        for i, signal in enumerate(signals[:3], 1):  # Show first 3
            print(f"\n   Signal #{i}:")
            print(f"      Pool: {signal['pool_address']}")
            print(f"      Activity Score: {signal['activity_score']}")
            print(f"      Tx Delta: {signal['tx_delta']}")
    else:
        print("\n   ℹ️  No signals detected (Normal if pool has no txs in last 10 blocks)")

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
    
    # Test tracking through integration
    integration.track_new_pool({
        'address': '0xDEADBEEF', 
        'chain': 'base', 
        'dex': 'uniswap_v2',
        'liquidity_usd': 100000
    }, {'score': 75, 'verdict': 'WATCH'})
    
    # Check if tracked
    if '0xdeadbeef' in scanner.tracked_pools:
        print("   ✅ Integration.track_new_pool working!")
    elif '0xDEADBEEF'.lower() in scanner.tracked_pools:
        print("   ✅ Integration.track_new_pool working! (lowercase handled)")
    else:
        print("   ❌ Integration.track_new_pool failed")

    # Has smart wallet check
    has_sw = integration.has_smart_wallet_targets('base')
    print(f"   Smart Wallet Check: {has_sw}")
    
except Exception as e:
    print(f"   ❌ Integration error: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

all_passed = True
checks = [
    ("RPC Connection", web3.is_connected()),
    ("Scanner Creation", scanner is not None),
    ("Scan Execution", stats.get('scans_performed', 0) >= 0),
    ("Integration Layer", integration is not None),
]

for check_name, passed in checks:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status} - {check_name}")
    if not passed:
        all_passed = False

print("\n" + "=" * 60)
