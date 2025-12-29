"""
Direct verification: Do V3 PoolCreated events actually exist?
This will query the blockchain directly to confirm.
"""
from web3 import Web3
import yaml

# Load config
with open('chains.yaml', 'r') as f:
    config = yaml.safe_load(f)

def test_v3_events(chain_name, rpc_url, v3_factory):
    print("="*80)
    print(f"{chain_name.upper()} V3 VERIFICATION")
    print("="*80)
    
    web3 = Web3(Web3.HTTPProvider(rpc_url))
    
    if not web3.is_connected():
        print(f"ERROR: Cannot connect to {chain_name} RPC")
        return
    
    latest_block = web3.eth.block_number
    print(f"\nLatest block: {latest_block}")
    
    # Test 1: Check if factory exists
    print(f"\n[Test 1] Check V3 factory contract")
    print(f"  Address: {v3_factory}")
    try:
        code = web3.eth.get_code(v3_factory)
        if code and code != b'\x00':
            print(f"  Result: Contract EXISTS (code size: {len(code)} bytes)")
        else:
            print(f"  Result: NO CONTRACT at this address!")
            return
    except Exception as e:
        print(f"  ERROR: {e}")
        return
    
    # Test 2: Try querying ALL events from factory (no topic filter)
    print(f"\n[Test 2] Query ALL events from factory (last 1000 blocks)")
    try:
        from_block = latest_block - 1000
        all_events = web3.eth.get_logs({
            'address': v3_factory,
            'fromBlock': hex(from_block),
            'toBlock': hex(latest_block)
        })
        print(f"  Result: {len(all_events)} total events from factory")
        
        if all_events:
            # Group by event signature
            sigs = {}
            for evt in all_events:
                sig = evt['topics'][0].hex() if evt['topics'] else 'no_topic'
                sigs[sig] = sigs.get(sig, 0) + 1
            
            print(f"\n  Event signatures found:")
            for sig, count in sorted(sigs.items(), key=lambda x: -x[1])[:5]:
                print(f"    {sig}: {count} events")
        else:
            print(f"  Warning: Factory exists but NO events in 1000 blocks")
            
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Test 3: Query with PoolCreated signature
    print(f"\n[Test 3] Query PoolCreated events specifically")
    pool_created_sig = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()
    print(f"  Signature: {pool_created_sig}")
    
    # Try different block ranges
    for blocks in [1000, 10000, 50000]:
        try:
            from_block = latest_block - blocks
            events = web3.eth.get_logs({
                'address': v3_factory,
                'topics': [pool_created_sig],
                'fromBlock': hex(from_block),
                'toBlock': hex(latest_block)
            })
            print(f"  Last {blocks:6d} blocks: {len(events)} PoolCreated events")
            
            if events:
                first = events[0]
                print(f"    First event block: {first['blockNumber']}")
                print(f"    Tx: {first['transactionHash'].hex()}")
                break
                
        except Exception as e:
            print(f"  Last {blocks:6d} blocks: ERROR - {e}")
    
    # Test 4: Check a known V3 pool exists
    print(f"\n[Test 4] Try to find any V3 pool on {chain_name}")
    try:
        # Query factory for owner (should return deployer if it's a real V3 factory)
        # V3 factory has owner() function
        factory_abi = [{
            "inputs": [],
            "name": "owner",
            "outputs": [{"type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }]
        
        factory = web3.eth.contract(address=v3_factory, abi=factory_abi)
        try:
            owner = factory.functions.owner().call()
            print(f"  Factory owner: {owner}")
            print(f"  This confirms it's a real Uniswap V3 factory")
        except:
            print(f"  Note: Cannot call owner() (might not be V3 factory)")
            
    except Exception as e:
        print(f"  ERROR: {e}")

# Test BASE
base_config = config['chains']['base']
test_v3_events(
    'BASE',
    base_config['rpc_url'],
    base_config['factories']['uniswap_v3']
)

print("\n\n")

# Test ETHEREUM
eth_config = config['chains']['ethereum']
test_v3_events(
    'ETHEREUM',
    eth_config['rpc_url'],
    eth_config['factories']['uniswap_v3']
)

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("""
If Test 2 shows many events BUT Test 3 shows 0 PoolCreated:
  -> Event signature might be wrong OR V3 rarely creates pools

If Test 2 shows 0 events:
  -> Factory address might be wrong OR it's not the V3 factory

If Test 3 shows PoolCreated events in 50k blocks but not in 10k:
  -> V3 activity is VERY low, need even wider lookback
""")
