"""
VERIFICATION SCRIPT: SECONDARY & ACTIVITY SCANNERS
==================================================

Purpose: Verify that both secondary scanners are correctly implemented and functional.
1. Secondary Scanner (Breakout Mode) - secondary_scanner/secondary_market/secondary_scanner.py
2. Activity Scanner (Hunter Mode) - secondary_activity_scanner.py
"""

import asyncio
import sys
import yaml
import time
from web3 import Web3
from colorama import init, Fore, Style

init(autoreset=True)

# Load config
try:
    with open('chains.yaml', 'r') as f:
        config_data = yaml.safe_load(f)
        BASE_CONFIG = config_data['chains']['base']
        print(f"{Fore.GREEN}✅ Loaded configuration")
except Exception as e:
    print(f"{Fore.RED}❌ Config load failed: {e}")
    sys.exit(1)

# Init Web3
print(f"{Fore.CYAN}🔌 Connecting to BASE RPC...")
w3 = Web3(Web3.HTTPProvider(BASE_CONFIG['rpc_url']))
if not w3.is_connected():
    print(f"{Fore.RED}❌ RPC Connection failed")
    sys.exit(1)
print(f"{Fore.GREEN}✅ Connected to RPC. Block: {w3.eth.block_number}")


async def verify_activity_scanner():
    print(f"\n{Fore.MAGENTA}=== 1. VERIFYING ACTIVITY SCANNER (HUNTER MODE) ===")
    
    try:
        from secondary_activity_scanner import SecondaryActivityScanner
        
        scanner = SecondaryActivityScanner(w3, 'base', BASE_CONFIG)
        
        # 1. Admit Pool
        pool_addr = '0xd0b53d9277642d899df5f87a3966a34909eae13b' # WETH/USDC
        admitted = scanner.track_pool({
            'pool_address': pool_addr,
            'token_address': '0xTEST',
            'dex': 'uniswap_v3',
            'score': 80,
            'liquidity_usd': 1000000,
            'is_trade': True,
            'current_block': w3.eth.block_number - 10
        })
        
        if admitted:
            print(f"{Fore.GREEN}   ✅ Pool admitted successfully")
        else:
            print(f"{Fore.RED}   ❌ Pool admission failed")
            
        if len(scanner.tracked_pools) == 1:
             print(f"{Fore.GREEN}   ✅ Access tracked_pools successful")
        
        # 2. Scan
        print(f"{Fore.CYAN}   🔍 Running scan...")
        signals = scanner.scan_recent_activity(target_block=w3.eth.block_number)
        
        # 3. Check Stats
        stats = scanner.get_stats()
        print(f"{Fore.GREEN}   ✅ Scan finished. Signals: {len(signals)}")
        print(f"      Stats: {stats}")
        
    except Exception as e:
        print(f"{Fore.RED}   ❌ Activity Scanner Error: {e}")
        import traceback
        traceback.print_exc()


async def verify_secondary_scanner():
    print(f"\n{Fore.BLUE}=== 2. VERIFYING SECONDARY SCANNER (BREAKOUT MODE) ===")
    
    try:
        from secondary_scanner.secondary_market.secondary_scanner import SecondaryScanner
        
        # Mock heatmap injection if needed by sub-components (metrics/triggers)
        # Though the scanner itself handles metrics internally
        
        scanner = SecondaryScanner(w3, {
            **BASE_CONFIG,
            'chain_name': 'base',
            'secondary_scanner': {'enabled': True, 'min_liquidity': 1000}
        })
        
        # 1. Discover Pairs
        print(f"{Fore.CYAN}   🔍 Discovering pairs...")
        # Reduce lookback to speed up test
        scanner.lookback_blocks_v2 = 1000 
        scanner.lookback_blocks_v3 = 1000
        
        pairs = scanner.discover_pairs()
        
        if len(pairs) > 0:
            print(f"{Fore.GREEN}   ✅ Discovery successful: {len(pairs)} pairs found")
            # Register them
            for p in pairs:
                scanner.add_pair_to_monitor(**p)
        else:
            print(f"{Fore.YELLOW}   ⚠️  No pairs discovered (Scan range might be empty)")
            
        # 2. Scan Pairs (Async)
        if len(scanner.monitored_pairs) > 0:
            print(f"{Fore.CYAN}   🔍 Scanning {len(scanner.monitored_pairs)} pairs...")
            signals = await scanner.scan_all_pairs()
            print(f"{Fore.GREEN}   ✅ Scan successful. Signals: {len(signals)}")
        
        stats = scanner.get_stats()
        print(f"      Stats: {stats}")

    except Exception as e:
        print(f"{Fore.RED}   ❌ Secondary Scanner Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await verify_activity_scanner()
    await verify_secondary_scanner()
    print(f"\n{Fore.GREEN}=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
