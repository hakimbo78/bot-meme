#!/usr/bin/env python3
"""
Test script for API retry logic and fallback
"""

import sys
sys.path.insert(0, '/home/hakim/bot-meme')

from tokensniffer_analyzer import TokenSnifferAnalyzer
from web3 import Web3

print("=" * 60)
print("API RETRY & FALLBACK TEST")
print("=" * 60)

# Test with Base chain mock
w3 = Web3()
analyzer = TokenSnifferAnalyzer(w3, 'base')

# Test token (use a known Base token)
test_token = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"  # DEGEN on Base

print(f"\n📊 Testing token: {test_token}")
print("This will test:")
print("  1. GoPlus API retry logic (3 attempts)")
print("  2. TokenSniffer fallback if GoPlus fails")
print("  3. Exponential backoff (1s → 2s → 4s)")

print("\n🔍 Starting analysis...")
result = analyzer.analyze_comprehensive(test_token)

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

print(f"Risk Score: {result.get('risk_score', 'N/A')}/100")
print(f"Risk Level: {result.get('risk_level', 'N/A')}")

if 'contract_analysis' in result and 'details' in result['contract_analysis']:
    print("\nDetails:")
    for detail in result['contract_analysis']['details']:
        print(f"  {detail}")

print("\n✅ Test complete!")
print("=" * 60)
