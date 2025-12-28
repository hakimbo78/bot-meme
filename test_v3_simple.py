"""
Direct RPC test for Uniswap V3 PoolCreated events
"""
from web3 import Web3
import yaml

# Load config
with open('chains.yaml', 'r') as f:
    config = yaml.safe_load(f)

# BASE chain
base_config = config['chains']['base']
base_web3 = Web3(Web3.HTTPProvider(base_config['rpc_url']))
base_v3_factory = base_config['factories']['uniswap_v3']

print("="*80)
print("TESTING UNISWAP V3 POOLCREATED EVENTS - DIRECT RPC")
print("="*80)

# V3 PoolCreated signature
v3_signature = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()
print(f"\nV3 PoolCreated signature: {v3_signature}")
print(f"Factory: {base_v3_factory}")

# Get latest block
latest_block = base_web3.eth.block_number
from_block = latest_block - 3000

print(f"\nBlock range:")
print(f"  From: {from_block}")
print(f"  To: {latest_block}")
print(f"  Range: 3000 blocks")

# Test 1: Query V3 events
print(f"\nTest 1: Query V3 PoolCreated events")
try:
    payload_1 = {
        'address': base_v3_factory,
        'topics': [v3_signature],
        'fromBlock': hex(from_block),
        'toBlock': hex(latest_block)
    }
    logs_1 = base_web3.eth.get_logs(payload_1)
    print(f"  Result: Found {len(logs_1)} V3 events")
    
    if len(logs_1) > 0:
        first = logs_1[0]
        print(f"\n  First event:")
        print(f"    Block: {first['blockNumber']}")
        print(f"    Topics count: {len(first['topics'])}")
        print(f"    Data length: {len(first['data'].hex())} chars")
    
except Exception as e:
    print(f"  ERROR: {e}")

# Test 2: V2 for comparison
print(f"\nTest 2: Query V2 PairCreated events (comparison)")
v2_signature = Web3.keccak(text="PairCreated(address,address,address,uint256)").hex()
v2_factory = base_config['factories']['uniswap_v2']
try:
    payload_2 = {
        'address': v2_factory,
        'topics': [v2_signature],
        'fromBlock': hex(from_block),
        'toBlock': hex(latest_block)
    }
    logs_2 = base_web3.eth.get_logs(payload_2)
    print(f"  Result: Found {len(logs_2)} V2 events")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 3: Check factory exists
print(f"\nTest 3: Verify V3 factory exists")
try:
    code = base_web3.eth.get_code(base_v3_factory)
    exists = code and code != b'\x00'
    print(f"  Result: Factory exists = {exists}")
    if exists:
        print(f"  Code size: {len(code)} bytes")
except Exception as e:
    print(f"  ERROR: {e}")

# Test 4: Wider range
print(f"\nTest 4: Try 10,000 blocks")
try:
    from_block_wide = latest_block - 10000
    payload_4 = {
        'address': base_v3_factory,
        'topics': [v3_signature],
        'fromBlock': hex(from_block_wide),
        'toBlock': hex(latest_block)
    }
    logs_4 = base_web3.eth.get_logs(payload_4)
    print(f"  Result: Found {len(logs_4)} V3 events in 10k blocks")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
