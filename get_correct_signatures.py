"""
Generate correct event signatures for Uniswap V2 and V3
"""
from web3 import Web3

print("="*70)
print("CORRECT EVENT SIGNATURES")
print("="*70)

# Uniswap V2 Events
print("\n📌 UNISWAP V2:")
v2_pair_created = Web3.keccak(text="PairCreated(address,address,address,uint256)").hex()
v2_swap = Web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()
print(f"PairCreated: {v2_pair_created}")
print(f"Swap:        {v2_swap}")

# Uniswap V3 Events
print("\n📌 UNISWAP V3:")
v3_pool_created = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()
v3_swap = Web3.keccak(text="Swap(address,address,int256,int256,uint160,uint128,int24)").hex()
print(f"PoolCreated: {v3_pool_created}")
print(f"Swap:        {v3_swap}")

print("\n" + "="*70)
print("CURRENT VALUES IN CODE (WRONG - have extra characters):")
print("="*70)
print("\n📌 UNISWAP V2:")
print(f"PairCreated: 0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612")
print(f"Swap:        0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822e")

print("\n📌 UNISWAP V3:")
print(f"PoolCreated: 0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee871103")
print(f"Swap:        0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67b")

print("\n" + "="*70)
print("FIX REQUIRED:")
print("="*70)
print("Remove extra characters from the end of each signature!")
