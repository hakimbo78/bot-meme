"""
Quick test for secondary scanner RPC fix
"""
from web3 import Web3

# Test topic format
test_topic = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612"

# Before: topics as string (WRONG - causes -32602 error)
wrong_payload = {
    'address': '0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6',
    'topics': test_topic,  # ❌ String
    'fromBlock': '0x1000000',
    'toBlock': '0x1000100'
}

# After: topics as array (CORRECT)
correct_payload = {
    'address': '0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6',
    'topics': [test_topic],  # ✅ Array
    'fromBlock': '0x1000000',
    'toBlock': '0x1000100'
}

print("❌ WRONG format (causes error):")
print(f"   topics type: {type(wrong_payload['topics'])}")
print(f"   topics value: {wrong_payload['topics']}")
print()
print("✅ CORRECT format (fixed):")
print(f"   topics type: {type(correct_payload['topics'])}")
print(f"   topics value: {correct_payload['topics']}")
print()
print("🔧 The fix changes topics from string to array format:")
print("   - Before: topics = signature")
print("   - After:  topics = [signature]")
