#!/usr/bin/env python3
"""Test get_transaction with signature conversion"""

from solana.rpc.api import Client
from solders.signature import Signature
from solders.pubkey import Pubkey

print("Testing get_transaction with signature conversion...")

client = Client("https://api.mainnet-beta.solana.com")

# Get a recent signature from Pumpfun
program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
program_key = Pubkey.from_string(program_id)

print(f"\nGetting signatures for {program_id[:8]}...")
response = client.get_signatures_for_address(program_key, limit=5)

if response.value:
    print(f"Found {len(response.value)} signatures")
    
    # Try first signature
    sig_str = str(response.value[0].signature)
    print(f"\nTesting signature: {sig_str[:16]}...")
    
    try:
        # Convert to Signature object
        sig_obj = Signature.from_string(sig_str)
        print(f"✅ Signature object created: {type(sig_obj)}")
        
        # Try get_transaction
        print("Calling get_transaction...")
        tx_response = client.get_transaction(
            sig_obj,
            encoding="jsonParsed",
            max_supported_transaction_version=0
        )
        
        if tx_response.value:
            print(f"✅ Transaction fetched! Has meta: {hasattr(tx_response.value, 'meta')}")
        else:
            print("⚠️ No transaction data")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No signatures found")
