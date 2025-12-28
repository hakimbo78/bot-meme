#!/usr/bin/env python3
"""Test Solana dependencies and RPC connection"""

print("Testing Solana libraries...")

try:
    from solana.rpc.api import Client
    from solana.rpc.types import TxOpts
    from solders.pubkey import Pubkey
    print("✅ Solana libraries imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)

# Test RPC connection
print("\nTesting Solana RPC connection...")
try:
    client = Client("https://api.mainnet-beta.solana.com")
    slot = client.get_slot()
    print(f"✅ RPC connected! Current slot: {slot.value}")
except Exception as e:
    print(f"❌ RPC error: {e}")
    exit(1)

# Test Pumpfun program ID
print("\nTesting Pumpfun program ID...")
try:
    program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    program_key = Pubkey.from_string(program_id)
    print(f"✅ Program key: {program_key}")
    
    # Try to get signatures
    response = client.get_signatures_for_address(program_key, limit=5)
    if response.value:
        print(f"✅ Found {len(response.value)} signatures for Pumpfun program")
        print(f"   Latest signature: {response.value[0].signature}")
    else:
        print("⚠️ No signatures found")
except Exception as e:
    print(f"❌ Pumpfun test error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n✅ All tests passed!")
