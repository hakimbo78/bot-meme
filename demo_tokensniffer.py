"""
Demo TokenSniffer-Style Security Analysis

Mendemonstrasikan audit security komprehensif seperti TokenSniffer
"""

import asyncio
import sys
from colorama import Fore, init
from tokensniffer_analyzer import TokenSnifferAnalyzer
from multi_scanner import MultiChainScanner
from config import CHAIN_CONFIGS

init(autoreset=True)


async def demo_tokensniffer_analysis(chain: str, token_address: str):
    """Demo TokenSniffer-style analysis."""
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}TOKENSNIFFER-STYLE SECURITY ANALYSIS".center(80))
    print(f"{Fore.CYAN}{'='*80}\n")
    
    print(f"{Fore.WHITE}Chain: {Fore.CYAN}{chain.upper()}")
    print(f"{Fore.WHITE}Token: {Fore.CYAN}{token_address}\n")
    
    # Initialize scanner
    scanner = MultiChainScanner([chain], CHAIN_CONFIGS.get('chains', {}))
    adapter = scanner.get_adapter(chain)
    
    if not adapter:
        print(f"{Fore.RED}❌ No adapter for {chain}")
        return
    
    # Initialize TokenSniffer analyzer
    ts_analyzer = TokenSnifferAnalyzer(adapter.w3, chain)
    
    # Run comprehensive analysis
    print(f"{Fore.YELLOW}Running comprehensive security checks...\n")
    result = ts_analyzer.analyze_comprehensive(token_address)
    
    # Display results
    print(f"\n{Fore.CYAN}{'─'*80}")
    print(f"{Fore.CYAN}📊 SWAP ANALYSIS (Honeypot Detection)")
    print(f"{Fore.CYAN}{'─'*80}")
    for detail in result['swap_analysis'].get('details', []):
        print(f"  {detail}")
    
    print(f"\n{Fore.CYAN}{'─'*80}")
    print(f"{Fore.CYAN}📜 CONTRACT ANALYSIS")
    print(f"{Fore.CYAN}{'─'*80}")
    for detail in result['contract_analysis'].get('details', []):
        print(f"  {detail}")
    
    print(f"\n{Fore.CYAN}{'─'*80}")
    print(f"{Fore.CYAN}👥 HOLDER ANALYSIS")
    print(f"{Fore.CYAN}{'─'*80}")
    for detail in result['holder_analysis'].get('details', []):
        print(f"  {detail}")
    
    print(f"\n{Fore.CYAN}{'─'*80}")
    print(f"{Fore.CYAN}💧 LIQUIDITY ANALYSIS")
    print(f"{Fore.CYAN}{'─'*80}")
    for detail in result['liquidity_analysis'].get('details', []):
        print(f"  {detail}")
    
    # Overall score
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}OVERALL ASSESSMENT".center(80))
    print(f"{Fore.CYAN}{'='*80}\n")
    
    score = result.get('overall_score', 0)
    risk_level = result.get('risk_level', 'UNKNOWN')
    
    # Color based on score
    if score >= 90:
        score_color = Fore.GREEN
    elif score >= 75:
        score_color = Fore.CYAN
    elif score >= 60:
        score_color = Fore.YELLOW
    else:
        score_color = Fore.RED
    
    print(f"{Fore.WHITE}TokenSniffer Score: {score_color}{score}/100")
    print(f"{Fore.WHITE}Risk Level: {score_color}{risk_level}\n")
    
    # Recommendation
    if score >= 90:
        print(f"{Fore.GREEN}✅ EXCELLENT - Very safe for trading")
    elif score >= 75:
        print(f"{Fore.CYAN}✅ GOOD - Safe for trading with standard risk management")
    elif score >= 60:
        print(f"{Fore.YELLOW}⚠️  MODERATE - Trade with caution")
    elif score >= 40:
        print(f"{Fore.RED}⚠️  HIGH RISK - Trade with extreme caution, small position only")
    else:
        print(f"{Fore.RED}🚫 CRITICAL RISK - DO NOT TRADE")
    
    print(f"\n{Fore.CYAN}{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"{Fore.RED}Usage: python demo_tokensniffer.py <chain> <token_address>")
        print(f"{Fore.YELLOW}Example: python demo_tokensniffer.py base 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8")
        sys.exit(1)
    
    chain = sys.argv[1]
    token_address = sys.argv[2]
    
    asyncio.run(demo_tokensniffer_analysis(chain, token_address))
