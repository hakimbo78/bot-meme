
import logging
import base58
from solders.keypair import Keypair
from trading.wallet_manager import WalletManager

logging.basicConfig(level=logging.INFO)

def test_imports():
    print("--- Testing Imports ---")
    wm = WalletManager()
    
    # 1. Test EVM Import
    # Generate mock EVM key (64 chars hex)
    dummy_evm = "0x" + "1" * 64
    print(f"Testing EVM Import with dummy key...")
    res_evm = wm.import_wallet_evm(dummy_evm, 'base')
    print(f"EVM Import Result: {res_evm}")
    if res_evm:
        print(f"EVM Address: {wm.get_address('base')}")
    else:
        print("❌ EVM Import Failed")

    # 2. Test Solana Import
    # Generate mock Solana keypair and encode to Base58
    print(f"\nTesting Solana Import...")
    dummy_kp = Keypair()
    dummy_bytes = bytes(dummy_kp) # 64 bytes
    dummy_b58 = base58.b58encode(dummy_bytes).decode('utf-8')
    
    print(f"Dummy Solana PK (Base58): {dummy_b58[:10]}...")
    
    res_sol = wm.import_wallet_solana(dummy_b58)
    print(f"Solana Import Result: {res_sol}")
    if res_sol:
        print(f"Solana Address: {wm.get_address('solana')}")
    else:
        print("❌ Solana Import Failed")

if __name__ == "__main__":
    test_imports()
