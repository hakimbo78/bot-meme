#!/usr/bin/env python3
"""
Secondary Scanner Test Script

Tests the secondary market scanner RPC fixes.
"""

import time
from web3 import Web3
from secondary_scanner.secondary_market.secondary_scanner import SecondaryScanner
from config import load_chain_configs

def test_secondary_scanner():
    """Test secondary scanner functionality"""
    print("Secondary Market Scanner Test")
    print("=" * 50)

    # Load configurations
    configs = load_chain_configs()

    for chain_name in ['base', 'ethereum']:
        if chain_name not in configs['chains']:
            continue

        chain_config = configs['chains'][chain_name]
        if not chain_config.get('enabled', False):
            continue

        if not chain_config.get('secondary_scanner', {}).get('enabled', False):
            print(f"WARNING: {chain_name.upper()}: Secondary scanner not enabled")
            continue

        print(f"\n📊 Testing {chain_name.upper()} Chain")
        print("-" * 30)

        try:
            # Initialize Web3
            rpc_url = chain_config['rpc_url']
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))

            if not w3.is_connected():
                print(f"❌ Failed to connect to {chain_name} RPC")
                continue

            print(f"✅ Connected to {chain_name} RPC")

            # Initialize secondary scanner
            scanner = SecondaryScanner(w3, chain_config)

            if not scanner.is_enabled():
                print(f"⚠️  {chain_name.upper()}: Secondary scanner disabled")
                continue

            print(f"✅ Secondary scanner initialized")

            # Test pair discovery
            print("🔄 Testing pair discovery...")
            start_time = time.time()
            pairs = scanner.discover_pairs()
            discovery_time = time.time() - start_time

            print(f"⏱️  Discovery took {discovery_time:.2f}s")
            print(f"🔍 Pairs found: {len(pairs)}")

            if pairs:
                print("✅ Pair discovery successful!")
                for pair in pairs[:3]:  # Show first 3
                    token_addr = pair.get('token_address', 'unknown')[:8]
                    dex_type = pair.get('dex_type', 'unknown')
                    print(f"      • {token_addr}... ({dex_type})")

                # Add pairs to monitor
                for pair in pairs:
                    scanner.add_pair_to_monitor(**pair)

                print(f"📊 Monitoring {len(scanner.monitored_pairs)} pairs")

                # Test scanning (quick test)
                print("🔄 Testing pair scanning...")
                import asyncio

                async def test_scan():
                    signals = await scanner.scan_all_pairs()
                    return signals

                signals = asyncio.run(test_scan())
                print(f"🎯 Signals detected: {len(signals)}")

                if signals:
                    print("✅ Pair scanning successful!")
                    for signal in signals[:2]:  # Show first 2
                        token_addr = signal.get('token_address', 'unknown')[:8]
                        state = signal.get('state', 'unknown')
                        print(f"      • {token_addr}... ({state})")
                else:
                    print("ℹ️ No signals in this scan (normal)")

            else:
                print("ℹ️ No pairs found in this scan (normal for test)")

            # Show stats
            stats = scanner.get_stats()
            print(f"📈 Stats: {stats}")

        except Exception as e:
            print(f"❌ Error testing {chain_name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print("🎯 SECONDARY SCANNER TEST COMPLETE")

if __name__ == "__main__":
    test_secondary_scanner()