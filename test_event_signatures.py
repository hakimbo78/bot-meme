"""
Test untuk validate event signatures
"""
import hashlib
from web3 import Web3

# Keccak-256 hash untuk event signatures
def get_event_signature(event_sig_string):
    """Get keccak256 hash of event signature"""
    return Web3.keccak(text=event_sig_string).hex()

# Uniswap V2 PairCreated event
v2_pair_created = "PairCreated(address,address,address,uint256)"
v2_hash = get_event_signature(v2_pair_created)
print(f"Uniswap V2 PairCreated: {v2_hash}")
print(f"Length: {len(v2_hash)} chars (should be 66 with 0x)")

# Uniswap V3 PoolCreated event  
v3_pool_created = "PoolCreated(address,address,uint24,int24,address)"
v3_hash = get_event_signature(v3_pool_created)
print(f"\nUniswap V3 PoolCreated: {v3_hash}")
print(f"Length: {len(v3_hash)} chars (should be 66 with 0x)")

# Swap events
v2_swap = "Swap(address,uint256,uint256,uint256,uint256,address)"
v2_swap_hash = get_event_signature(v2_swap)
print(f"\nUniswap V2 Swap: {v2_swap_hash}")
print(f"Length: {len(v2_swap_hash)} chars")

v3_swap = "Swap(address,address,int256,int256,uint160,uint128,int24)"
v3_swap_hash = get_event_signature(v3_swap)
print(f"\nUniswap V3 Swap: {v3_swap_hash}")
print(f"Length: {len(v3_swap_hash)} chars")

# Current values in code (WRONG - have extra chars)
print("\n" + "="*60)
print("CURRENT VALUES (WRONG):")
current_v2 = '0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612'
current_v3 = '0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee871103'
print(f"V2: {current_v2} (length: {len(current_v2)})")
print(f"V3: {current_v3} (length: {len(current_v3)})")

current_v2_swap = '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822e'
current_v3_swap = '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67b'
print(f"V2 Swap: {current_v2_swap} (length: {len(current_v2_swap)})")
print(f"V3 Swap: {current_v3_swap} (length: {len(current_v3_swap)})")
