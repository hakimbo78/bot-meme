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
print(f"\n📋 V3 PoolCreated signature: {v3_signature}")
print(f"   Factory: {base_v3_factory}")

# Get latest block
latest_block = base_web3.eth.block_number
from_block = latest_block - 3000  # Same as scanner

print(f"\n📊 Block range:")
print(f"   From: {from_block}")
print(f"   To: {latest_block}")
print(f"   Range: {3000} blocks")

# Test 1: Query with signature only
print(f"\n🧪 Test 1: Query V3 PoolCreated events (signature only)")
try:
    payload_1 = {
        'address': base_v3_factory,
        'topics': [v3_signature],
        'fromBlock': hex(from_block),
        'toBlock': hex(latest_block)
    }
    logs_1 = base_web3.eth.get_logs(payload_1)
    print(f"   ✅ Found {len(logs_1)} V3 PoolCreated events")
    
    if logs_1:
        # Show first event details
        first = logs_1[0]
        print(f"\n   📄 First event details:")
        print(f"      Block: {first['blockNumber']}")
        print(f"      Topics count: {len(first['topics'])}")
        print(f"      Topics[0] (event sig): {first['topics'][0].hex()}")
        if len(first['topics']) > 1:
            print(f"      Topics[1] (token0): 0x{first['topics'][1].hex()[-40:]}")
        if len(first['topics']) > 2:
            print(f"      Topics[2] (token1): 0x{first['topics'][2].hex()[-40:]}")
        if len(first['topics']) > 3:
            print(f"      Topics[3] (fee): {int(first['topics'][3].hex(), 16)}")
        print(f"      Data length: {len(first['data'].hex())} chars")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Compare with V2 for reference
print(f"\n🧪 Test 2: Compare with V2 (should have events)")
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
    print(f"   ✅ Found {len(logs_2)} V2 PairCreated events")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Check if factory contract exists
print(f"\n🧪 Test 3: Verify V3 factory contract exists")
try:
    code = base_web3.eth.get_code(base_v3_factory)
    if code and code != b'\x00':
        print(f"   ✅ V3 Factory contract exists at {base_v3_factory}")
        print(f"   Code size: {len(code)} bytes")
    else:
        print(f"   ❌ V3 Factory NOT deployed at {base_v3_factory}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Try wider block range
print(f"\n🧪 Test 4: Try last 10,000 blocks (wider range)")
try:
    from_block_wide = latest_block - 10000
    payload_4 = {
        'address': base_v3_factory,
        'topics': [v3_signature],
        'fromBlock': hex(from_block_wide),
        'toBlock': hex(latest_block)
    }
    logs_4 = base_web3.eth.get_logs(payload_4)
    print(f"   ✅ Found {len(logs_4)} V3 PoolCreated events in 10,000 blocks")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("""
If Test 1 returns 0 but Test 2 returns >0:
  → V3 signature or factory address is wrong

If Test 3 fails:
  → V3 factory not deployed on BASE

If Test 4 returns >0 but Test 1 returns 0:
  → V3 has lower activity, need wider block range

If all tests return 0:
  → Need to investigate V3 deployment on BASE chain
""")
