#!/usr/bin/env python3
"""
LP Monitor Daemon - Continuous Real-Time LP Tracking
Monitors open positions for liquidity rugpull signals and auto-exits if detected.
"""

import asyncio
import os
import time
from dotenv import load_dotenv
from colorama import Fore, Style, init
from trading.position_tracker import PositionTracker
from trading.db_handler import TradingDB
from trading.trade_executor import TradeExecutor
from lp_intent_analyzer import LPIntentAnalyzer
import requests

init(autoreset=True)
load_dotenv()


class LPMonitorDaemon:
    """Continuous LP monitor that tracks open positions and auto-exits on rugpull signals."""
    
    def __init__(self):
        from trading.wallet_manager import WalletManager
        from trading.okx_client import OKXDexClient
        
        self.db = TradingDB()
        self.position_tracker = PositionTracker(self.db)
        
        # Initialize trade executor dependencies
        self.wallet_manager = WalletManager()
        self.okx_client = OKXDexClient()
        self.trade_executor = TradeExecutor(
            wallet_manager=self.wallet_manager,
            okx_client=self.okx_client,
            position_tracker=self.position_tracker
        )
        
        # LP analyzers per chain
        self.lp_analyzers = {
            'solana': LPIntentAnalyzer('solana'),
            'base': LPIntentAnalyzer('base'),
            'ethereum': LPIntentAnalyzer('ethereum')
        }
        
        # Tracking
        self.last_check = {}
        self.exit_triggered = set()  # Track which positions already exited
        
    async def get_pair_data(self, token_address: str, chain: str) -> dict:
        """Fetch latest pair data from DexScreener."""
        try:
            # DexScreener API
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            pairs = data.get('pairs', [])
            
            if not pairs:
                return None
            
            # Find best pair for this chain
            chain_map = {'solana': 'solana', 'base': 'base', 'ethereum': 'ethereum'}
            target_chain = chain_map.get(chain, chain)
            
            for pair in pairs:
                if pair.get('chainId', '').lower() == target_chain:
                    return pair
            
            # Fallback to first pair if exact chain not found
            return pairs[0]
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Error fetching pair data: {e}")
            return None
    
    async def check_position_lp(self, position: dict) -> tuple[bool, str, dict]:
        """
        Check LP risk for a position.
        
        Returns:
            (should_exit: bool, reason: str, lp_risk: dict)
        """
        try:
            token_address = position['token_address']
            chain = position['chain']
            position_id = position['id']
            
            # Get current pair data
            pair_data = await self.get_pair_data(token_address, chain)
            
            if not pair_data:
                # Can't fetch data, don't exit
                return (False, "No pair data available", {})
            
            # Get LP analyzer for this chain
            analyzer = self.lp_analyzers.get(chain)
            if not analyzer:
                return (False, f"No analyzer for chain {chain}", {})
            
            # Calculate LP risk
            lp_risk = analyzer.calculate_risk(pair_data)
            
            # Check for emergency exit (ULTRA-AGGRESSIVE MODE)
            # Criteria 1: Risk score > 50 (was 70 - more aggressive)
            if lp_risk['risk_score'] > 50:
                return (True, f"LP Intent Risk HIGH ({lp_risk['risk_score']:.0f}/100 > 50)", lp_risk)
            
            # Criteria 2: LP drop > 2% in 5 minutes (was 5% - more sensitive)
            lp_delta_5m = analyzer.get_lp_delta(token_address, minutes=5)
            if lp_delta_5m is not None and lp_delta_5m < -2:
                return (True, f"LP dropped {abs(lp_delta_5m):.1f}% in 5 minutes (>2% threshold)", lp_risk)
            
            # Criteria 3: Emergency exit check
            should_exit, reason = analyzer.should_emergency_exit(token_address)
            if should_exit:
                return (True, reason, lp_risk)
            
            # All good
            return (False, "", lp_risk)
            
        except Exception as e:
            print(f"{Fore.RED}Error checking position LP: {e}")
            return (False, f"Error: {e}", {})
    
    async def execute_emergency_exit(self, position: dict, reason: str):
        """Execute emergency exit for a position."""
        try:
            position_id = position['id']
            token_address = position['token_address']
            chain = position['chain']
            
            print(f"\n{Fore.RED}{'='*60}")
            print(f"{Fore.RED}🚨 EMERGENCY EXIT TRIGGERED")
            print(f"{Fore.RED}{'='*60}")
            print(f"Position: #{position_id}")
            print(f"Token: {token_address[:10]}...{token_address[-8:]}")
            print(f"Chain: {chain.upper()}")
            print(f"Reason: {reason}")
            print(f"{Fore.RED}{'='*60}\n")
            
            # Execute market sell
            result = await self.trade_executor.emergency_sell(
                position_id=position_id,
                reason=reason
            )
            
            if result:
                print(f"{Fore.GREEN}✅ Emergency exit executed successfully")
                self.exit_triggered.add(position_id)
                
                # Clear LP history
                analyzer = self.lp_analyzers.get(chain)
                if analyzer:
                    analyzer.clear_history(token_address)
            else:
                print(f"{Fore.YELLOW}⚠️ Emergency exit failed (may retry next check)")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error executing emergency exit: {e}")
    
    async def monitor_loop(self):
        """Main monitoring loop (runs every 30 seconds)."""
        
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}🛡️ LP MONITOR DAEMON STARTED")
        print(f"{Fore.CYAN}{'='*60}")
        print(f"Monitoring frequency: Every 5 seconds [ULTRA-AGGRESSIVE]")
        print(f"Auto-exit triggers:")
        print(f"  - LP Risk Score > 50 (was 70 - more aggressive)")
        print(f"  - LP Drop > 2% in 5 minutes (was 5% - more sensitive)")
        print(f"  - Market Divergence detected (LP↓ + Vol↑)")
        print(f"{Fore.CYAN}{'='*60}\n")
        
        iteration = 0
        
        while True:
            try:
                iteration += 1
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"\n{Fore.CYAN}[{current_time}] Check #{iteration}")
                print(f"{Fore.CYAN}{'━'*60}")
               
                # Get all open positions
                positions = self.position_tracker.get_open_positions()
                
                if not positions:
                    print(f"{Fore.YELLOW}📭 No open positions to monitor")
                else:
                    print(f"{Fore.GREEN}📊 Monitoring {len(positions)} open position(s)...")
                    
                    for pos in positions:
                        position_id = pos['id']
                        
                        # Skip if already exited
                        if position_id in self.exit_triggered:
                            continue
                        
                        token_addr_short = f"{pos['token_address'][:10]}...{pos['token_address'][-8:]}"
                        print(f"\n  Position #{position_id} ({pos['chain'].upper()}): {token_addr_short}")
                        
                        # Check LP risk
                        should_exit, reason, lp_risk = await self.check_position_lp(pos)
                        
                        if lp_risk:
                            risk_score = lp_risk.get('risk_score', 0)
                            risk_level = lp_risk.get('risk_level', 'UNKNOWN')
                            
                            # Color-code based on risk
                            if risk_score < 25:
                                color = Fore.GREEN
                                icon = "✅"
                            elif risk_score < 50:
                                color = Fore.YELLOW
                                icon = "⚠️"
                            elif risk_score < 70:
                                color = Fore.LIGHTYELLOW_EX
                                icon = "⚠️"
                            else:
                                color = Fore.RED
                                icon = "🚨"
                            
                            print(f"  {color}{icon} LP Intent Risk: {risk_score:.0f}/100 ({risk_level}){Style.RESET_ALL}")
                            
                            # Show components
                            components = lp_risk.get('components', {})
                            if components:
                                print(f"     Control: {components.get('control_risk', 0):.0f}, " 
                                      f"Economic: {components.get('economic_risk', 0):.0f}, "
                                      f"Behavior: {components.get('behavior_risk', 0):.0f}, "
                                      f"Divergence: {components.get('divergence_risk', 0):.0f}")
                        
                        # Execute emergency exit if needed
                        if should_exit:
                            await self.execute_emergency_exit(pos, reason)
                
                print(f"\n{Fore.CYAN}{'━'*60}")
                print(f"{Fore.GREEN}✅ Check #{iteration} completed. Next check in 5s... [ULTRA-AGGRESSIVE]")
                
                # Wait 5 seconds (was 30s - faster detection)
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}🛑 Monitor daemon stopped by user")
                break
            except Exception as e:
                print(f"\n{Fore.RED}❌ Error in monitor loop: {e}")
                print(f"{Fore.YELLOW}Retrying in 5 seconds...")
                await asyncio.sleep(5)
    
    async def run(self):
        """Start the monitoring daemon."""
        await self.monitor_loop()


async def main():
    """Main entry point."""
    daemon = LPMonitorDaemon()
    await daemon.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Daemon stopped.")
