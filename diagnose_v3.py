"""
Comprehensive V3 test - check if RPC returns any V3 events
"""
from web3 import Web3
import yaml

# Load config
with open('chains.yaml', 'r') as f:
    config = yaml.safe_load(f)

def test_chain_v3(chain_name, chain_config):
    print("="*80)
    print(f"TESTING {chain_name.upper()} V3")
    print("="*80)
    
    web3 = Web3(Web3.HTTPProvider(chain_config['rpc_url']))
    v3_factory = chain_config['factories']['uniswap_v3']
    
    print(f"V3 Factory: {v3_factory}")
    
    # Check if connected
    if not web3.is_connected():
        print("ERROR: Not connected to RPC")
        return
    
    # Get latest block
    latest_block = web3.eth.block_number
    from_block = latest_block - 3000
    
    print(f"Block range: {from_block} to {latest_block} (3000 blocks)")
    
    # V3 PoolCreated signature
    v3_sig = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()
    print(f"V3 PoolCreated signature: {v3_sig}")
    
    # Test 1: Check factory contract exists
    print(f"\n[Test 1] Check if factory contract exists")
    try:
        code = web3.eth.get_code(v3_factory)
        if code and code != b'\x00':
            print(f"  OK: Contract exists, code size: {len(code)} bytes")
        else:
            print(f"  ERROR: No contract at {v3_factory}")
            return
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    
    # Test 2: Query with just signature
    print(f"\n[Test 2] Query V3 PoolCreated events")
    try:
        logs = web3.eth.get_logs({
            'address': v3_factory,
            'topics': [v3_sig],
            'fromBlock': hex(from_block),
            'toBlock': hex(latest_block)
        })
        print(f"  Result: {len(logs)} events found")
        
        if logs:
            first = logs[0]
            print(f"\n  First event details:")
            print(f"    Block: {first['blockNumber']}")
            print(f"    Tx: {first['transactionHash'].hex()}")
            print(f"    Topics: {len(first['topics'])}")
            for i, topic in enumerate(first['topics']):
                print(f"      [{i}]: {topic.hex()}")
            print(f"    Data: {first['data'].hex()[:100]}...")
            
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Try wider range (10k blocks)
    print(f"\n[Test 3] Try 10,000 blocks")
    try:
        from_block_wide = latest_block - 10000
        logs_wide = web3.eth.get_logs({
            'address': v3_factory,
            'topics': [v3_sig],
            'fromBlock': hex(from_block_wide),
            'toBlock': hex(latest_block)
        })
        print(f"  Result: {len(logs_wide)} events in 10k blocks")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 4: Query without topics (all events from factory)
    print(f"\n[Test 4] Query ALL events from factory (no topic filter)")
    try:
        all_logs = web3.eth.get_logs({
            'address': v3_factory,
            'fromBlock': hex(from_block),
            'toBlock': hex(latest_block)
        })
        print(f"  Result: {len(all_logs)} total events from factory")
        
        if all_logs:
            # Count by event signature
            signatures = {}
            for log in all_logs:
                sig = log['topics'][0].hex() if log['topics'] else 'no_topic'
                signatures[sig] = signatures.get(sig, 0) + 1
            
            print(f"\n  Event signatures found:")
            for sig, count in signatures.items():
                print(f"    {sig}: {count} events")
                
    except Exception as e:
        print(f"  ERROR: {e}")

# Test BASE
base_config = config['chains']['base']
test_chain_v3('BASE', base_config)

print("\n\n")

# Test ETHEREUM
eth_config = config['chains']['ethereum']
test_chain_v3('ETHEREUM', eth_config)
