import sys
import os

# Ensure we can import modules from current directory
sys.path.append(os.getcwd())

from tokensniffer_analyzer import TokenSnifferAnalyzer

# Mock Web3 not needed for RugCheck API
w3 = None

analyzer = TokenSnifferAnalyzer(w3, 'solana')

token_address = "82hVfzp5MV97cdztarpsn4EhgVCdMpYzkcwMQmWTwK6T"

print(f"\nrunning Score-Based Analysis for: {token_address}")
print("-" * 50)

# Create a mock result structure to pass to internal method or use analyze_comprehensive
# Since analyze_comprehensive expects pair_address too (can be None) and checks external liquidity
# We'll test the internal method directly or analyze_comprehensive

# Create empty result dict structure expected by _analyze_solana_rugcheck
result = {
    'contract_analysis': {'details': []},
    'holder_analysis': {'details': []},
    'liquidity_analysis': {'details': []},
    'swap_analysis': {'details': []},
    'risk_score': 0,
    'risk_level': 'UNKNOWN'
}

# Run analysis
try:
    analyzer._analyze_solana_rugcheck(token_address, result)
    
    print(f"\nRESULTS:")
    print(f"Risk Score: {result.get('risk_score')}/100")
    print(f"Risk Level: {result.get('risk_level')}")
    
    print("\nDETAILS:")
    for section in ['contract_analysis', 'holder_analysis', 'liquidity_analysis', 'swap_analysis']:
        details = result.get(section, {}).get('details', [])
        if details:
            print(f"[{section.upper()}]")
            for d in details:
                print(f"  {d}")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("-" * 50)
