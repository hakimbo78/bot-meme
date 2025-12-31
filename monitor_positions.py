#!/usr/bin/env python3
"""
Position Monitor - Real-time P&L Tracking
Shows all open positions with current value, PnL%, and status
"""

import asyncio
import os
from dotenv import load_dotenv
from colorama import Fore, Style, init
from trading.position_tracker import PositionTracker
from trading.trading_db import TradingDB
from trading.okx_client import OKXDexClient
from trading.config_manager import ConfigManager

init(autoreset=True)
load_dotenv()

async def monitor_positions():
    """Monitor all open positions with live P&L calculation"""
    
    # Initialize
    db = TradingDB()
    position_tracker = PositionTracker(db)
    okx_client = OKXDexClient()
    
    # Get all open positions
    positions = position_tracker.get_open_positions()
    
    if not positions:
        print(f"{Fore.YELLOW}📭 No open positions")
        print(f"{Fore.CYAN}ℹ️  All positions are closed or no trades executed yet")
        return
    
    print(f"{Fore.GREEN}{'='*80}")
    print(f"{Fore.GREEN}📊 POSITION MONITOR - Live P&L Tracking")
    print(f"{Fore.GREEN}{'='*80}\n")
    
    total_entry_value = 0
    total_current_value = 0
    
    for idx, pos in enumerate(positions, 1):
        try:
            print(f"{Fore.CYAN}Position #{pos['id']} - {pos.get('status', 'OPEN')}")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Basic Info
            print(f"Token:    {pos['token_address'][:10]}...{pos['token_address'][-8:]}")
            print(f"Chain:    {pos['chain'].upper()}")
            print(f"Opened:   {pos.get('timestamp', 'Unknown')}")
            
            # Entry Details
            entry_usd = float(pos['entry_value_usd'])
            entry_amount = float(pos['entry_amount'])
            print(f"\n💰 Entry:")
            print(f"  Amount:  {entry_amount:,.0f} tokens")
            print(f"  Value:   ${entry_usd:.2f}")
            
            # Get current value via quote
            chain = pos['chain']
            token_addr = pos['token_address']
            
            # Native token config
            chain_config = ConfigManager.get_chain_config(chain)
            native_token = "So11111111111111111111111111111111111111112" if chain == 'solana' else "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
            
            # Get quote for selling
            amount_in = str(int(entry_amount))
            quote = await okx_client.get_quote(
                chain=chain,
                from_token=token_addr,
                to_token=native_token,
                amount=amount_in,
                slippage=0.01
            )
            
            if quote:
                # Calculate current value
                raw_out = float(quote.get('toTokenAmount', '0'))
                decimals = 9 if chain == 'solana' else 18
                real_out = raw_out / (10 ** decimals)
                
                # Estimate native token price (rough)
                native_price = 200.0 if chain == 'solana' else 3500.0
                current_usd = real_out * native_price
                
                # Calculate P&L
                pnl_usd = current_usd - entry_usd
                pnl_pct = ((current_usd - entry_usd) / entry_usd) * 100 if entry_usd > 0 else 0
                
                # Display current value
                color = Fore.GREEN if pnl_pct >= 0 else Fore.RED
                arrow = "📈" if pnl_pct >= 0 else "📉"
                
                print(f"\n{arrow} Current:")
                print(f"  Value:   ${current_usd:.2f}")
                print(f"{color}  P&L:     ${pnl_usd:+.2f} ({pnl_pct:+.1f}%){Style.RESET_ALL}")
                
                # Exit strategy warnings
                exit_config = ConfigManager.get_config().get('exit_strategy', {})
                if exit_config.get('enabled', False):
                    tp = exit_config.get('take_profit_percent', 100)
                    sl = exit_config.get('stop_loss_percent', -30)
                    
                    if pnl_pct >= tp:
                        print(f"{Fore.GREEN}  🎯 TAKE-PROFIT TRIGGERED! Bot will auto-sell 50%")
                    elif pnl_pct <= sl:
                        print(f"{Fore.RED}  🛑 STOP-LOSS TRIGGERED! Bot will auto-sell 100%")
                
                total_entry_value += entry_usd
                total_current_value += current_usd
            else:
                print(f"\n{Fore.YELLOW}⚠️  Unable to fetch current price (low liquidity or API error)")
                print(f"  Last Value: ${entry_usd:.2f}")
                total_entry_value += entry_usd
                total_current_value += entry_usd
            
            print()
            
        except Exception as e:
            print(f"{Fore.RED}  Error processing position: {e}\n")
    
    # Summary
    print(f"{Fore.GREEN}{'='*80}")
    print(f"{Fore.CYAN}📊 PORTFOLIO SUMMARY")
    print(f"{Fore.GREEN}{'='*80}")
    print(f"Open Positions:    {len(positions)}")
    print(f"Total Entry Value: ${total_entry_value:.2f}")
    print(f"Total Current Val: ${total_current_value:.2f}")
    
    if total_entry_value > 0:
        total_pnl = total_current_value - total_entry_value
        total_pnl_pct = (total_pnl / total_entry_value) * 100
        color = Fore.GREEN if total_pnl >= 0 else Fore.RED
        print(f"{color}Total P&L:         ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%){Style.RESET_ALL}")
    
    print(f"{Fore.GREEN}{'='*80}\n")
    
    # Close client
    await okx_client.close()

if __name__ == "__main__":
    asyncio.run(monitor_positions())
