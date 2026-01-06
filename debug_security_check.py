import sys
from tokensniffer_analyzer import TokenSnifferAnalyzer

def test_security(chain, address, mock_liq=0):
    print(f"DEBUGGING: {chain} - {address}")
    
    try:
        analyzer = TokenSnifferAnalyzer(None, chain)
        print("Calling analyze_comprehensive...")
        result = analyzer.analyze_comprehensive(address, external_liquidity_usd=mock_liq)
        print("\nRAW RESULT:")
        print(result)
        
        print("\nChecking keys...")
        dex_lock = result.get('liquidity_analysis', {}).get('liquidity_locked_percent', 'N/A')
        print(f"Liquidity Locked: {dex_lock}")
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_security_check.py <chain> <address>")
        sys.exit(1)
        
    chain_arg = sys.argv[1]
    addr_arg = sys.argv[2]
    test_security(chain_arg, addr_arg)
