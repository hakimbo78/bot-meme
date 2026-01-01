import asyncio
import sys
from tokensniffer_analyzer import TokenSnifferAnalyzer
from colorama import init, Fore, Style

init(autoreset=True)

async def test_security(chain, address, mock_liq=0):
    print(f"\n🔍 DEBUGGING SECURITY LOGIC FOR: {chain.upper()} - {address}")
    print(f"Using Analyzer Logic: tokensniffer_analyzer.py")
    print(f"Simulated DexScreener Liquidity: ${mock_liq:,}")
    print("-" * 60)
    
    # Init Analyzer (Pass None for Web3 since we confirm logic only)
    try:
        analyzer = TokenSnifferAnalyzer(None, chain)
        
        # 1. Calling API
        print(f"{Fore.CYAN}📡 Calling Real-time Security API (GoPlus/RugCheck)...")
        # analyze_comprehensive is synchronous in current implementation using requests
        result = analyzer.analyze_comprehensive(address, external_liquidity_usd=mock_liq)
        
        # 2. Validasi Liquidity
        print(f"\n{Fore.YELLOW}1. LIQUIDITY AUDIT (Rule: > 80% Locked)")
        liq = result.get('liquidity_analysis', {})
        locked = liq.get('liquidity_locked_percent', 0)
        
        # Show details
        for det in liq.get('details', []):
            print(f"   - Info: {det}")
            
        print(f"   > DETECTED LOCKED %: {Fore.WHITE}{locked}%")
        
        if locked < 80:
            print(f"   {Fore.RED}❌ RESULT: FAIL (Sent to Bot -> BLOCK BUY)")
        else:
            print(f"   {Fore.GREEN}✅ RESULT: PASS (Sent to Bot -> ALLOW)")

        # 3. Validasi Drivers (Holders)
        print(f"\n{Fore.YELLOW}2. HOLDER AUDIT (Rule: Top 10 < 70%)")
        holder = result.get('holder_analysis', {})
        top10 = holder.get('top10_holders_percent', 0)
        creator = holder.get('creator_wallet_percent', 0)
        
        print(f"   - Top 10 Holders Own: {top10:.2f}%")
        print(f"   - Creator Wallet Owns: {creator:.2f}%")
        
        if top10 > 70:
            print(f"   {Fore.RED}❌ RESULT: FAIL (High Concentration -> BLOCK BUY)")
        else:
            print(f"   {Fore.GREEN}✅ RESULT: PASS (Distribution -> ALLOW)")

        # 4. Validasi Risk
        print(f"\n{Fore.YELLOW}3. RISK AUDIT (Rule: NO CRITICAL FLAGS)")
        risk = result.get('risk_level', 'UNKNOWN')
        contract = result.get('contract_analysis', {})
        swap = result.get('swap_analysis', {})
        
        print(f"   - Calculated Risk Level: {risk}")
        print(f"   - Is Honeypot: {swap.get('is_honeypot', False)}")
        print(f"   - Is Mintable: {contract.get('has_mint_function', False)}")
        
        if risk in ['CRITICAL']:
            print(f"   {Fore.RED}❌ RESULT: FAIL (Critical Risk -> BLOCK BUY)")
        elif risk == 'HIGH':
             print(f"   {Fore.RED}⚠️ RESULT: WARNING (High Risk -> BLOCK BUY)")
        else:
            print(f"   {Fore.GREEN}✅ RESULT: PASS (Safety -> ALLOW)")

    except Exception as e:
        print(f"{Fore.RED}❌ Error running test: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_security_check.py <chain> <address>")
        print("Example: python debug_security_check.py solana 7EYnhQoR9YM3N7ebhcXaCdcprylnHbbprQsZ1wfwdog")
        sys.exit(1)
        
    chain_arg = sys.argv[1]
    addr_arg = sys.argv[2]
    liq_arg = 0
    if len(sys.argv) > 3:
        try:
            liq_arg = float(sys.argv[3])
        except:
            print("Invalid liquidity amount, using 0")
    
    # Run loop
    asyncio.run(test_security(chain_arg, addr_arg, liq_arg))
