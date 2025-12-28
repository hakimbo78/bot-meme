"""
Deep investigation: Why Uniswap V3 always returns 0 pairs
"""
from web3 import Web3

print("="*80)
print("UNISWAP V3 INVESTIGATION")
print("="*80)

# V3 PoolCreated event signature
v3_event_string = "PoolCreated(address,address,uint24,int24,address)"
v3_signature = Web3.keccak(text=v3_event_string).hex()

print(f"\n📋 V3 PoolCreated Event:")
print(f"   String: {v3_event_string}")
print(f"   Keccak-256: {v3_signature}")
print(f"   Length: {len(v3_signature)} chars")

# Current signature in code
current_v3_sig = "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718"
print(f"\n🔍 Comparison:")
print(f"   Generated:  {v3_signature}")
print(f"   In code:    {current_v3_sig}")
print(f"   Match: {v3_signature == current_v3_sig}")

# V3 Factory addresses
print(f"\n🏭 V3 Factory Addresses:")
print(f"   BASE:     0x1F98431c8aD98523631AE4a59f267346ea31F984")
print(f"   ETHEREUM: 0x1F98431c8aD98523631AE4a59f267346ea31F984")
print(f"   Note: Same address on both chains (canonical deployment)")

# V2 for comparison
v2_event_string = "PairCreated(address,address,address,uint256)"
v2_signature = Web3.keccak(text=v2_event_string).hex()
print(f"\n📋 V2 PairCreated Event (for comparison):")
print(f"   String: {v2_event_string}")
print(f"   Keccak-256: {v2_signature}")

print("\n" + "="*80)
print("POTENTIAL ISSUES TO CHECK:")
print("="*80)
print("""
1. ✅ Event signature - Verify it's correct
2. ❓ Factory address - Verify it's deployed on both chains
3. ❓ RPC query format - V3 might need different topics structure
4. ❓ Block range - Maybe V3 activity is lower, need more blocks
5. ❓ Event indexing - V3 has 3 indexed params vs V2's 2

V3 PoolCreated Event Structure:
    event PoolCreated(
        address indexed token0,      // topics[1]
        address indexed token1,      // topics[2]
        uint24 indexed fee,          // topics[3] ← EXTRA INDEXED PARAM!
        int24 tickSpacing,           // data field 1
        address pool                 // data field 2
    );

V2 PairCreated Event Structure:
    event PairCreated(
        address indexed token0,      // topics[1]
        address indexed token1,      // topics[2]
        address pair,                // data field 1
        uint256                      // data field 2
    );

KEY DIFFERENCE: V3 has 3 indexed params, V2 has 2 indexed params!
This means topics array for V3 should have 4 elements (event sig + 3 params)
""")
