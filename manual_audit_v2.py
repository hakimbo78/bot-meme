"""
Manual Token Audit Tool

Comprehensive on-chain analysis and security audit for tokens on Base, Ethereum, and Solana.
Provides deep insights, risk assessment, and trading recommendations.

Usage:
    python manual_audit.py <chain> <token_address>
    
Examples:
    python manual_audit.py base 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b
    python manual_audit.py ethereum 0x6982508145454Ce325dDbE47a25d4ec3d2311933
    python manual_audit.py solana 9BB62h9yHqMq9EkUNs2nH8P3Cc8wZ79S96H9FofAyxYw
"""

import asyncio
import sys
from colorama import Fore, Style, init
from typing import Dict, Optional
import time

from analyzer import TokenAnalyzer
from scorer import TokenScorer
from multi_scanner import MultiChainScanner
from config import CHAIN_CONFIGS
from telegram_notifier import TelegramNotifier
from tokensniffer_analyzer import TokenSnifferAnalyzer

init(autoreset=True)


class ManualTokenAuditor:
    """Comprehensive manual token audit system."""
    
    def __init__(self):
        """Initialize auditor with all chain adapters."""
        self.scanner = MultiChainScanner(['base', 'ethereum'], CHAIN_CONFIGS.get('chains', {}))
        self.scorer = TokenScorer()
        self.telegram = TelegramNotifier()
        
        # Initialize Solana components
        self.solana_scanner = None
        self.solana_score_engine = None
        try:
            from modules.solana import SolanaScanner, SolanaScoreEngine
            solana_config = CHAIN_CONFIGS.get('chains', {}).get('solana', {})
            self.solana_scanner = SolanaScanner(solana_config)
            self.solana_scanner.connect()
            self.solana_score_engine = SolanaScoreEngine(solana_config)
            print(f"{Fore.GREEN}✅ Solana audit engine initialized")
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Solana audit unavailable: {e}")
    
    def print_header(self, title: str):
        """Print formatted section header."""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}{title.center(80)}")
        print(f"{Fore.CYAN}{'='*80}\n")
    
    def print_section(self, title: str):
        """Print formatted subsection."""
        print(f"\n{Fore.YELLOW}{'─'*80}")
        print(f"{Fore.YELLOW}{title}")
        print(f"{Fore.YELLOW}{'─'*80}")
    
    def format_risk_level(self, level: str) -> str:
        """Format risk level with color."""
        colors = {
            'LOW': Fore.GREEN,
            'MEDIUM': Fore.YELLOW,
            'HIGH': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT
        }
        return f"{colors.get(level, Fore.WHITE)}{level}{Style.RESET_ALL}"
    
    async def audit_evm_token(self, chain: str, token_address: str) -> Optional[Dict]:
        """
        Perform comprehensive audit on EVM token (Base/Ethereum).
        
        Returns:
            Audit report dict with analysis, score, and recommendations
        """
        self.print_header(f"🔍 AUDITING {chain.upper()} TOKEN")
        print(f"{Fore.CYAN}Token Address: {Fore.WHITE}{token_address}\n")
        
        # Get chain adapter
        adapter = self.scanner.get_adapter(chain)
        if not adapter:
            print(f"{Fore.RED}❌ No adapter available for {chain}")
            return None
        
        # Step 1: Token Analysis
        self.print_section("📊 STEP 1: ON-CHAIN ANALYSIS")
        print(f"{Fore.CYAN}Fetching token data from {chain.upper()} RPC...")
        
        try:
            analyzer = TokenAnalyzer(adapter=adapter)
            
            # Create minimal pair data for analysis
            # Try to find pair address if not provided
            pair_address = None
            try:
                # Try to get the main trading pair for this token
                from web3 import Web3
                token_checksum = Web3.to_checksum_address(token_address)
                
                # For now, we'll let the analyzer handle finding the pair
                # or we can set it to None and analyzer will try to find it
                pair_data = {
                    'token_address': token_address,
                    'address': token_address,
                    'chain': chain,
                    'timestamp': int(time.time())
                }
                
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Address validation warning: {e}")
                pair_data = {
                    'token_address': token_address,
                    'address': token_address,
                    'chain': chain,
                    'timestamp': int(time.time())
                }
            
            analysis = analyzer.analyze_token(pair_data)
            
            if not analysis:
                print(f"{Fore.RED}❌ Failed to analyze token")
                return None
            
            print(f"{Fore.GREEN}✅ Analysis complete\n")
            
            # Display basic info
            print(f"{Fore.WHITE}Token Name:     {Fore.CYAN}{analysis.get('name', 'UNKNOWN')}")
            print(f"{Fore.WHITE}Symbol:         {Fore.CYAN}{analysis.get('symbol', 'UNKNOWN')}")
            print(f"{Fore.WHITE}Decimals:       {Fore.CYAN}{analysis.get('decimals', 0)}")
            print(f"{Fore.WHITE}Total Supply:   {Fore.CYAN}{analysis.get('total_supply', 0):,.0f}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Analysis error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Step 2: Liquidity & Market Analysis
        self.print_section("💧 STEP 2: LIQUIDITY & MARKET ANALYSIS")
        
        liquidity_usd = analysis.get('liquidity_usd', 0)
        pair_address = analysis.get('pair_address', 'N/A')
        age_minutes = analysis.get('age_minutes', 0)
        
        print(f"{Fore.WHITE}Pair Address:   {Fore.CYAN}{pair_address}")
        print(f"{Fore.WHITE}Liquidity:      {Fore.CYAN}${liquidity_usd:,.2f}")
        print(f"{Fore.WHITE}Age:            {Fore.CYAN}{age_minutes:.1f} minutes ({age_minutes/60:.1f} hours)")
        
        # Liquidity assessment
        if liquidity_usd >= 100000:
            liq_status = f"{Fore.GREEN}EXCELLENT - High liquidity"
        elif liquidity_usd >= 50000:
            liq_status = f"{Fore.GREEN}GOOD - Adequate liquidity"
        elif liquidity_usd >= 10000:
            liq_status = f"{Fore.YELLOW}MODERATE - Medium liquidity"
        elif liquidity_usd >= 1000:
            liq_status = f"{Fore.YELLOW}LOW - Limited liquidity"
        else:
            liq_status = f"{Fore.RED}CRITICAL - Very low liquidity"
        
        print(f"{Fore.WHITE}Assessment:     {liq_status}")
        
        # Step 3: Security Audit
        self.print_section("🛡️  STEP 3: SECURITY AUDIT")
        
        renounced = analysis.get('renounced', False)
        is_honeypot = analysis.get('is_honeypot', False)
        has_mint = analysis.get('has_mint_function', False)
        has_pause = analysis.get('has_pause_function', False)
        has_blacklist = analysis.get('has_blacklist', False)
        
        print(f"{Fore.WHITE}Ownership Renounced:  {Fore.GREEN + '✅ YES' if renounced else Fore.RED + '❌ NO'}")
        print(f"{Fore.WHITE}Honeypot Detected:    {Fore.RED + '⚠️  YES' if is_honeypot else Fore.GREEN + '✅ NO'}")
        print(f"{Fore.WHITE}Mint Function:        {Fore.YELLOW + '⚠️  YES' if has_mint else Fore.GREEN + '✅ NO'}")
        print(f"{Fore.WHITE}Pause Function:       {Fore.YELLOW + '⚠️  YES' if has_pause else Fore.GREEN + '✅ NO'}")
        print(f"{Fore.WHITE}Blacklist Function:   {Fore.YELLOW + '⚠️  YES' if has_blacklist else Fore.GREEN + '✅ NO'}")
        
        # Calculate security score
        security_score = 100
        if not renounced:
            security_score -= 30
        if is_honeypot:
            security_score -= 50
        if has_mint:
            security_score -= 10
        if has_pause:
            security_score -= 5
        if has_blacklist:
            security_score -= 5
        
        security_level = 'HIGH' if security_score >= 80 else 'MEDIUM' if security_score >= 50 else 'LOW'
        print(f"\n{Fore.WHITE}Security Score:       {Fore.CYAN}{security_score}/100 ({self.format_risk_level(security_level)})")
        
        # Step 3.5: TokenSniffer-Style Analysis
        self.print_section("🔬 STEP 3.5: TOKENSNIFFER-STYLE ANALYSIS")
        print(f"{Fore.CYAN}Running comprehensive security checks...")
        
        tokensniffer_result = None
        try:
            ts_analyzer = TokenSnifferAnalyzer(adapter.w3, chain)
            tokensniffer_result = ts_analyzer.analyze_comprehensive(token_address, pair_address)
            
            # Display Swap Analysis
            print(f"\n{Fore.YELLOW}📊 Swap Analysis (Honeypot Detection):")
            for detail in tokensniffer_result['swap_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Contract Analysis  
            print(f"\n{Fore.YELLOW}📜 Contract Analysis:")
            for detail in tokensniffer_result['contract_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Holder Analysis
            print(f"\n{Fore.YELLOW}👥 Holder Analysis:")
            for detail in tokensniffer_result['holder_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Liquidity Analysis
            print(f"\n{Fore.YELLOW}💧 Liquidity Analysis:")
            for detail in tokensniffer_result['liquidity_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display TokenSniffer Score
            ts_score = tokensniffer_result.get('overall_score', 0)
            ts_risk = tokensniffer_result.get('risk_level', 'UNKNOWN')
            print(f"\n{Fore.WHITE}TokenSniffer Score:   {Fore.CYAN}{ts_score}/100 ({self.format_risk_level(ts_risk)})")
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  TokenSniffer analysis unavailable: {e}")
            tokensniffer_result = None
        
        # Step 4: Risk Scoring
        self.print_section("⚖️  STEP 4: COMPREHENSIVE RISK SCORING")
        
        chain_config = self.scanner.get_chain_config(chain)
        score_data = self.scorer.score_token(analysis, chain_config)
        
        final_score = score_data.get('score', 0)
        verdict = score_data.get('verdict', 'UNKNOWN')
        risk_flags = score_data.get('risk_flags', [])
        
        print(f"{Fore.WHITE}Final Score:    {Fore.CYAN}{final_score:.1f}/100")
        print(f"{Fore.WHITE}Verdict:        {Fore.CYAN}{verdict}")
        
        if risk_flags:
            print(f"\n{Fore.YELLOW}⚠️  Risk Flags Detected:")
            for flag in risk_flags:
                print(f"  • {Fore.YELLOW}{flag}")
        else:
            print(f"\n{Fore.GREEN}✅ No major risk flags detected")
        
        # Step 5: Trading Recommendation
        self.print_section("💡 STEP 5: TRADING RECOMMENDATION")
        
        # Determine overall risk
        overall_risk = 'LOW'
        if is_honeypot or security_score < 30:
            overall_risk = 'CRITICAL'
        elif not renounced or liquidity_usd < 5000:
            overall_risk = 'HIGH'
        elif has_mint or has_pause or liquidity_usd < 20000:
            overall_risk = 'MEDIUM'
        
        print(f"{Fore.WHITE}Overall Risk:   {self.format_risk_level(overall_risk)}")
        
        # Generate recommendation
        if overall_risk == 'CRITICAL':
            recommendation = "🚫 DO NOT TRADE - Critical security issues detected"
            rec_color = Fore.RED
        elif overall_risk == 'HIGH':
            recommendation = "⚠️  HIGH RISK - Trade with extreme caution, small position only"
            rec_color = Fore.RED
        elif overall_risk == 'MEDIUM':
            recommendation = "⚠️  MODERATE RISK - Acceptable for experienced traders with risk management"
            rec_color = Fore.YELLOW
        else:
            recommendation = "✅ LOW RISK - Suitable for trading with standard risk management"
            rec_color = Fore.GREEN
        
        print(f"\n{rec_color}{recommendation}{Style.RESET_ALL}")
        
        # Additional insights
        print(f"\n{Fore.CYAN}📋 Key Insights:")
        if liquidity_usd < 10000:
            print(f"  • {Fore.YELLOW}Low liquidity may cause high slippage")
        if age_minutes < 60:
            print(f"  • {Fore.YELLOW}Very new token - higher volatility expected")
        if not renounced:
            print(f"  • {Fore.RED}Owner can modify contract - rug pull risk")
        if has_mint:
            print(f"  • {Fore.YELLOW}Token supply can be increased - dilution risk")
        
        # Compile audit report
        audit_report = {
            'chain': chain,
            'token_address': token_address,
            'analysis': analysis,
            'score_data': score_data,
            'security_score': security_score,
            'tokensniffer_result': tokensniffer_result,  # Add TokenSniffer data
            'overall_risk': overall_risk,
            'recommendation': recommendation,
            'timestamp': time.time()
        }
        
        return audit_report
    
    async def audit_solana_token(self, token_address: str) -> Optional[Dict]:
        """
        Perform comprehensive audit on Solana token.
        
        Returns:
            Audit report dict with analysis, score, and recommendations
        """
        self.print_header("🔍 AUDITING SOLANA TOKEN")
        print(f"{Fore.CYAN}Token Mint: {Fore.WHITE}{token_address}\n")
        
        if not self.solana_scanner:
            print(f"{Fore.RED}❌ Solana scanner not available")
            return None
        
        # Step 1: Token Analysis
        self.print_section("📊 STEP 1: ON-CHAIN ANALYSIS")
        print(f"{Fore.CYAN}Fetching token data from Solana RPC...")
        
        try:
            # Use the unified event wrapper for enrichment
            sol_input = {
                'token_address': token_address,
                'tx_signature': None
            }
            
            analysis = await self.solana_scanner._create_unified_event_async_wrapper(sol_input)
            
            if not analysis:
                print(f"{Fore.RED}❌ Failed to analyze token")
                return None
            
            print(f"{Fore.GREEN}✅ Analysis complete\n")
            
            # Display basic info
            print(f"{Fore.WHITE}Token Name:     {Fore.CYAN}{analysis.get('name', 'UNKNOWN')}")
            print(f"{Fore.WHITE}Symbol:         {Fore.CYAN}{analysis.get('symbol', 'UNKNOWN')}")
            print(f"{Fore.WHITE}Decimals:       {Fore.CYAN}{analysis.get('decimals', 0)}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Analysis error: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Step 2: Liquidity & Market Analysis
        self.print_section("💧 STEP 2: LIQUIDITY & MARKET ANALYSIS")
        
        liquidity_sol = analysis.get('liquidity_sol', 0)
        pool_address = analysis.get('pool_address', 'N/A')
        lp_valid = analysis.get('lp_valid', False)
        
        print(f"{Fore.WHITE}Pool Address:   {Fore.CYAN}{pool_address}")
        print(f"{Fore.WHITE}Liquidity:      {Fore.CYAN}{liquidity_sol:.2f} SOL")
        print(f"{Fore.WHITE}LP Valid:       {Fore.GREEN + '✅ YES' if lp_valid else Fore.RED + '❌ NO'}")
        
        # Liquidity assessment
        if liquidity_sol >= 100:
            liq_status = f"{Fore.GREEN}EXCELLENT - High liquidity"
        elif liquidity_sol >= 50:
            liq_status = f"{Fore.GREEN}GOOD - Adequate liquidity"
        elif liquidity_sol >= 10:
            liq_status = f"{Fore.YELLOW}MODERATE - Medium liquidity"
        elif liquidity_sol >= 1:
            liq_status = f"{Fore.YELLOW}LOW - Limited liquidity"
        else:
            liq_status = f"{Fore.RED}CRITICAL - Very low liquidity"
        
        print(f"{Fore.WHITE}Assessment:     {liq_status}")
        
        # Step 3: Security Audit
        self.print_section("🛡️  STEP 3: SECURITY AUDIT")
        
        metadata_ok = analysis.get('metadata_ok', False)
        state = analysis.get('state', 'UNKNOWN')
        
        print(f"{Fore.WHITE}Metadata Resolved:    {Fore.GREEN + '✅ YES' if metadata_ok else Fore.RED + '❌ NO'}")
        print(f"{Fore.WHITE}Token State:          {Fore.CYAN}{state}")
        print(f"{Fore.WHITE}LP Validation:        {Fore.GREEN + '✅ PASSED' if lp_valid else Fore.YELLOW + '⚠️  PENDING'}")
        
        # Calculate security score
        security_score = 100
        if not metadata_ok:
            security_score -= 20
        if not lp_valid:
            security_score -= 30
        if liquidity_sol < 5:
            security_score -= 20
        
        security_level = 'HIGH' if security_score >= 80 else 'MEDIUM' if security_score >= 50 else 'LOW'
        print(f"\n{Fore.WHITE}Security Score:       {Fore.CYAN}{security_score}/100 ({self.format_risk_level(security_level)})")
        
        # Step 3.5: TokenSniffer-Style Analysis
        self.print_section("🔬 STEP 3.5: TOKENSNIFFER-STYLE ANALYSIS")
        print(f"{Fore.CYAN}Running comprehensive security checks...")
        
        tokensniffer_result = None
        try:
            ts_analyzer = TokenSnifferAnalyzer(adapter.w3, chain)
            tokensniffer_result = ts_analyzer.analyze_comprehensive(token_address, pair_address)
            
            # Display Swap Analysis
            print(f"\n{Fore.YELLOW}📊 Swap Analysis (Honeypot Detection):")
            for detail in tokensniffer_result['swap_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Contract Analysis  
            print(f"\n{Fore.YELLOW}📜 Contract Analysis:")
            for detail in tokensniffer_result['contract_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Holder Analysis
            print(f"\n{Fore.YELLOW}👥 Holder Analysis:")
            for detail in tokensniffer_result['holder_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display Liquidity Analysis
            print(f"\n{Fore.YELLOW}💧 Liquidity Analysis:")
            for detail in tokensniffer_result['liquidity_analysis'].get('details', []):
                print(f"  {detail}")
            
            # Display TokenSniffer Score
            ts_score = tokensniffer_result.get('overall_score', 0)
            ts_risk = tokensniffer_result.get('risk_level', 'UNKNOWN')
            print(f"\n{Fore.WHITE}TokenSniffer Score:   {Fore.CYAN}{ts_score}/100 ({self.format_risk_level(ts_risk)})")
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  TokenSniffer analysis unavailable: {e}")
            tokensniffer_result = None
        
        # Step 4: Risk Scoring
        self.print_section("⚖️  STEP 4: COMPREHENSIVE RISK SCORING")
        
        score_data = self.solana_score_engine.calculate_score(analysis)
        
        final_score = score_data.get('score', 0)
        verdict = score_data.get('verdict', 'UNKNOWN')
        
        print(f"{Fore.WHITE}Final Score:    {Fore.CYAN}{final_score:.1f}/100")
        print(f"{Fore.WHITE}Verdict:        {Fore.CYAN}{verdict}")
        
        # Step 5: Trading Recommendation
        self.print_section("💡 STEP 5: TRADING RECOMMENDATION")
        
        # Determine overall risk
        overall_risk = 'LOW'
        if not metadata_ok or security_score < 30:
            overall_risk = 'CRITICAL'
        elif not lp_valid or liquidity_sol < 5:
            overall_risk = 'HIGH'
        elif liquidity_sol < 20:
            overall_risk = 'MEDIUM'
        
        print(f"{Fore.WHITE}Overall Risk:   {self.format_risk_level(overall_risk)}")
        
        # Generate recommendation
        if overall_risk == 'CRITICAL':
            recommendation = "🚫 DO NOT TRADE - Critical security issues detected"
            rec_color = Fore.RED
        elif overall_risk == 'HIGH':
            recommendation = "⚠️  HIGH RISK - Trade with extreme caution, small position only"
            rec_color = Fore.RED
        elif overall_risk == 'MEDIUM':
            recommendation = "⚠️  MODERATE RISK - Acceptable for experienced traders with risk management"
            rec_color = Fore.YELLOW
        else:
            recommendation = "✅ LOW RISK - Suitable for trading with standard risk management"
            rec_color = Fore.GREEN
        
        print(f"\n{rec_color}{recommendation}{Style.RESET_ALL}")
        
        # Additional insights
        print(f"\n{Fore.CYAN}📋 Key Insights:")
        if liquidity_sol < 10:
            print(f"  • {Fore.YELLOW}Low liquidity may cause high slippage")
        if not lp_valid:
            print(f"  • {Fore.RED}LP not validated - potential rug pull risk")
        if not metadata_ok:
            print(f"  • {Fore.YELLOW}Metadata not resolved - limited token information")
        
        # Compile audit report
        audit_report = {
            'chain': 'solana',
            'token_address': token_address,
            'analysis': analysis,
            'score_data': score_data,
            'security_score': security_score,
            'tokensniffer_result': tokensniffer_result,  # Add TokenSniffer data
            'overall_risk': overall_risk,
            'recommendation': recommendation,
            'timestamp': time.time()
        }
        
        return audit_report
    
    async def send_audit_to_telegram(self, audit_report: Dict):
        """Send improved, readable audit report to Telegram."""
        if not self.telegram.enabled:
            print(f"\n{Fore.YELLOW}⚠️  Telegram not configured - skipping notification")
            return
        
        chain = audit_report['chain'].upper()
        token_address = audit_report['token_address']
        analysis = audit_report['analysis']
        score_data = audit_report['score_data']
        security_score = audit_report['security_score']
        tokensniffer_result = audit_report.get('tokensniffer_result')
        overall_risk = audit_report['overall_risk']
        recommendation = audit_report['recommendation']
        
        # Risk emoji
        risk_emoji = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🔴',
            'CRITICAL': '⛔',
            'VERY_LOW': '🟢'
        }
        
        # === HEADER ===
        message = f"""🔍 *MANUAL TOKEN AUDIT REPORT*

*Chain:* {chain}
*Token:* {analysis.get('name', 'UNKNOWN')} (`{analysis.get('symbol', '???')}`)
*Address:* `{token_address[:8]}...{token_address[-6:]}`

"""
        
        # === QUICK SUMMARY ===
        message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *QUICK SUMMARY*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        # Security Score
        sec_emoji = '🟢' if security_score >= 80 else '🟡' if security_score >= 50 else '🔴'
        message += f"{sec_emoji} *Security Score:* `{security_score}/100`\n"
        
        # TokenSniffer Score (if available)
        if tokensniffer_result:
            ts_score = tokensniffer_result.get('overall_score', 0)
            ts_emoji = '🟢' if ts_score >= 80 else '🟡' if ts_score >= 60 else '🔴'
            message += f"{ts_emoji} *TokenSniffer Score:* `{ts_score}/100`\n"
        
        # Trading Score
        final_score = score_data.get('score', 0)
        verdict = score_data.get('verdict', 'UNKNOWN')
        score_emoji = '🟢' if final_score >= 75 else '🟡' if final_score >= 60 else '🔴'
        message += f"{score_emoji} *Trading Score:* `{final_score:.0f}/100` ({verdict})\n"
        
        # Overall Risk
        message += f"\n{risk_emoji.get(overall_risk, '⚪')} *Overall Risk:* *{overall_risk}*\n"
        
        # === MARKET DATA ===
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 *MARKET DATA*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        if chain == 'SOLANA':
            liquidity_sol = analysis.get('liquidity_sol', 0)
            message += f"💰 *Liquidity:* `{liquidity_sol:.2f} SOL`\n"
        else:
            liquidity_usd = analysis.get('liquidity_usd', 0)
            age_minutes = analysis.get('age_minutes', 0)
            message += f"💰 *Liquidity:* `${liquidity_usd:,.0f}`\n"
            message += f"⏰ *Age:* `{age_minutes/60:.1f} hours`\n"
        
        # === SECURITY CHECKS ===
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *SECURITY CHECKS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        if chain != 'SOLANA':
            renounced = analysis.get('renounced', False)
            is_honeypot = analysis.get('is_honeypot', False)
            has_mint = analysis.get('has_mint_function', False)
            
            message += f"{'✅' if renounced else '❌'} Ownership Renounced\n"
            message += f"{'✅' if not is_honeypot else '⚠️'} Not a Honeypot\n"
            message += f"{'✅' if not has_mint else '⚠️'} No Mint Function\n"
        
        # === TOKENSNIFFER ANALYSIS ===
        if tokensniffer_result and chain != 'SOLANA':
            message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 *TOKENSNIFFER ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            
            # Swap Analysis
            swap = tokensniffer_result.get('swap_analysis', {})
            if not swap.get('is_honeypot', False):
                message += f"✅ Token is sellable\n"
            else:
                message += f"⚠️ Honeypot detected!\n"
            
            buy_fee = swap.get('buy_fee_percent', 0)
            sell_fee = swap.get('sell_fee_percent', 0)
            message += f"💸 Buy Fee: `{buy_fee:.1f}%` | Sell Fee: `{sell_fee:.1f}%`\n"
            
            # Contract Analysis
            contract = tokensniffer_result.get('contract_analysis', {})
            if contract.get('is_verified'):
                message += f"✅ Contract Verified\n"
            if contract.get('ownership_renounced'):
                message += f"✅ Ownership Renounced\n"
            
            # Holder Analysis
            holder = tokensniffer_result.get('holder_analysis', {})
            creator_pct = holder.get('creator_wallet_percent', 0)
            top10_pct = holder.get('top10_holders_percent', 0)
            
            if creator_pct < 5:
                message += f"✅ Creator holds `{creator_pct:.1f}%` (< 5%)\n"
            else:
                message += f"⚠️ Creator holds `{creator_pct:.1f}%` (≥ 5%)\n"
            
            if top10_pct < 70:
                message += f"✅ Top 10 holders: `{top10_pct:.1f}%` (< 70%)\n"
            else:
                message += f"⚠️ Top 10 holders: `{top10_pct:.1f}%` (≥ 70%)\n"
            
            # Liquidity Lock
            liq = tokensniffer_result.get('liquidity_analysis', {})
            liq_locked = liq.get('liquidity_locked_percent', 0)
            if liq_locked >= 95:
                message += f"✅ Liquidity Locked: `{liq_locked:.0f}%`\n"
            elif liq_locked > 0:
                message += f"⚠️ Liquidity Locked: `{liq_locked:.0f}%`\n"
            else:
                message += f"❌ Liquidity Not Locked\n"
        
        # === RISK FLAGS ===
        risk_flags = score_data.get('risk_flags', [])
        if risk_flags:
            message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *RISK FLAGS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for flag in risk_flags[:5]:  # Limit to 5 flags
                message += f"• {flag}\n"
        
        # === RECOMMENDATION ===
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *RECOMMENDATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{recommendation}

"""
        
        # === FOOTER ===
        message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ _Manual audit - Always DYOR before trading_
_Not financial advice_
"""
        
        try:
            await self.telegram.send_message_async(message)
            print(f"\n{Fore.GREEN}✅ Audit report sent to Telegram")
        except Exception as e:
            print(f"\n{Fore.RED}❌ Failed to send to Telegram: {e}")
            import traceback
            traceback.print_exc()
    
    async def audit_token(self, chain: str, token_address: str, send_telegram: bool = True):
        """
        Main audit function - routes to appropriate chain auditor.
        
        Args:
            chain: Chain name (base, ethereum, solana)
            token_address: Token contract/mint address
            send_telegram: Whether to send report to Telegram
        """
        chain = chain.lower()
        
        if chain not in ['base', 'ethereum', 'solana']:
            print(f"{Fore.RED}❌ Unsupported chain: {chain}")
            print(f"{Fore.YELLOW}Supported chains: base, ethereum, solana")
            return None
        
        # Route to appropriate auditor
        if chain in ['base', 'ethereum']:
            audit_report = await self.audit_evm_token(chain, token_address)
        else:
            audit_report = await self.audit_solana_token(token_address)
        
        if not audit_report:
            return None
        
        # Send to Telegram if requested
        if send_telegram:
            await self.send_audit_to_telegram(audit_report)
        
        self.print_header("✅ AUDIT COMPLETE")
        
        return audit_report


async def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print(f"{Fore.RED}Usage: python manual_audit.py <chain> <token_address> [--no-telegram]")
        print(f"{Fore.YELLOW}Example: python manual_audit.py base 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b")
        sys.exit(1)
    
    chain = sys.argv[1]
    token_address = sys.argv[2]
    send_telegram = '--no-telegram' not in sys.argv
    
    auditor = ManualTokenAuditor()
    await auditor.audit_token(chain, token_address, send_telegram)


if __name__ == "__main__":
    asyncio.run(main())
