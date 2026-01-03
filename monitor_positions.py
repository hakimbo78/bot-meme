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
from trading.db_handler import TradingDB  # FIXED: db_handler instead of trading_db
from trading.okx_client import OKXDexClient
from trading.config_manager import ConfigManager
from trading.wallet_manager import WalletManager
from trading.trade_executor import TradeExecutor
from trading.trading_state_machine import TradingStateMachine
import aiohttp

init(autoreset=True)
# Robust .env loading
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)
print(f"DEBUG: Loaded .env from {env_path}")

async def monitor_positions():
    """Monitor all open positions with live P&L calculation (FOREVER LOOP)"""
    
    # Initialize active trading components
    db = TradingDB()
    position_tracker = PositionTracker(db)
    
    # NOTE: OKX Client needs to be managed carefully inside the loop or persistent
    okx_client = OKXDexClient()
    wallet_manager = WalletManager()
    
    # Import Wallets for Active Trading
    # Try multiple common names
    evm_key = os.getenv('EVM_PRIVATE_KEY') or os.getenv('PRIVATE_KEY') or os.getenv('ETH_PRIVATE_KEY')
    sol_key = os.getenv('SOLANA_PRIVATE_KEY') or os.getenv('SOL_PRIVATE_KEY')
    
    if evm_key:
        wallet_manager.import_wallet_evm(evm_key, 'ethereum')
        wallet_manager.import_wallet_evm(evm_key, 'base')
    else:
        print(f"{Fore.RED}⚠️  EVM_PRIVATE_KEY missing! Auto-sell will fail for EVM.")
        
    if sol_key:
        wallet_manager.import_wallet_solana(sol_key)
    else:
        # Warn only if we have Solana positions? Or generic warning
        print(f"{Fore.YELLOW}⚠️  SOLANA_PRIVATE_KEY missing.")

    # DEBUG: Verify Wallet Import
    base_addr = wallet_manager.get_address('base')
    print(f"{Fore.MAGENTA}DEBUG: Wallet Manager State:")
    print(f"  - Base Address: {base_addr}")
    if not base_addr:
         print(f"{Fore.RED}  ❌ CRITICAL: Base Address is NONE. Auto-Trade will FAIL.")

    trade_executor = TradeExecutor(wallet_manager, okx_client, position_tracker)
    state_machine = TradingStateMachine(trade_executor, position_tracker)
    
    print(f"{Fore.GREEN}🚀 Active Position Monitor Started (Background Service)")
    print(f"{Fore.CYAN}ℹ️  Press Ctrl+C to stop monitoring manually")

    while True:
        try:
            # Get all open positions
            positions = position_tracker.get_open_positions()
            
            if not positions:
                # Optional: reduce log spam for empty state
                # print(f"{Fore.YELLOW}📭 No open positions (Waiting...)")
                pass
            else:
                print(f"{Fore.GREEN}{'='*80}")
                print(f"{Fore.GREEN}📊 POSITION MONITOR - Live P&L Tracking & Active Management")
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
                        
                        # --- FEATURE 1: WALLET SYNC (Manual Sell Detection) ---
                        real_balance = wallet_manager.get_token_balance(chain, token_addr)
                        
                        if real_balance >= 0:
                            # 5% threshold: If we have less than 5% of entry amount, assume sold
                            if real_balance < (entry_amount * 0.05):
                                print(f"{Fore.YELLOW}⚠️  MANUAL SELL DETECTED (Balance: {real_balance:,.0f} < {entry_amount:,.0f})")
                                print(f"{Fore.RED}🛑 Closing position in DB...")
                                position_tracker.update_status(pos['id'], 'CLOSED_MANUAL', exit_price=0, exit_value=0)
                                continue # Skip to next position
                        # -------------------------------------------------------

                        # --- FEATURE 2: RUG PULL / LIQUIDITY CHECK ---
                        # Fetch DexScreener Data for accurate Liquidity & Price
                        # (We use direct specific token endpoint to save calls compared to search)
                        current_liquidity = 0
                        ds_price = 0
                        try:
                            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                            async with aiohttp.ClientSession() as session:
                                async with session.get(url, timeout=5) as resp:
                                    if resp.status == 200:
                                        ds_data = await resp.json()
                                        pairs = ds_data.get('pairs', [])
                                        
                                        if pairs:
                                            primary_pair = pairs[0]
                                            current_liquidity = float(primary_pair.get('liquidity', {}).get('usd', 0))
                                            ds_price = float(primary_pair.get('priceUsd', 0))
                                            
                                            # RUG CHECK: Liquidity < $500 (Extreme drop)
                                            if current_liquidity < 500:
                                                print(f"{Fore.RED}💀 RUG PULL DETECTED! Liquidity dropped to ${current_liquidity:,.2f}")
                                                print(f"{Fore.RED}🛑 Closing position as RUGGED...")
                                                position_tracker.update_status(pos['id'], 'CLOSED_RUG', exit_price=ds_price, exit_value=ds_price*real_balance)
                                                continue
                                        else:
                                            print(f"{Fore.YELLOW}⚠️  DexScreener: No pairs found (Possible Delist/Rug)")
                                    else:
                                        print(f"{Fore.YELLOW}⚠️  DexScreener API Error: {resp.status}")
                                
                        except Exception as req_e:
                            print(f"{Fore.YELLOW}⚠️  Market Data Fetch Error: {req_e}")
                            ds_price = 0 # Fallback to quote calculation below
                        # -------------------------------------------------------

                        # Get quote for selling (Estimate Value)
                        amount_in = str(int(entry_amount))
                        quote = await okx_client.get_quote(
                            chain=chain,
                            from_token=token_addr,
                            to_token=native_token,
                            amount=amount_in,
                            slippage=0.01
                        )
                        
                        current_usd = 0
                        
                        if quote:
                            # Calculate current value
                            raw_out = float(quote.get('toTokenAmount', '0'))
                            decimals = 9 if chain == 'solana' else 18
                            real_out = raw_out / (10 ** decimals)
                            
                            # Estimate native token price (rough)
                            native_price = 200.0 if chain == 'solana' else 3500.0
                            current_usd = real_out * native_price
                        elif ds_price > 0:
                            # Fallback to DexScreener price if quote fails
                            decimals = 9 if chain == 'solana' else 18
                            normalized_amount = entry_amount / (10 ** decimals)
                            current_usd = ds_price * normalized_amount
                            print(f"{Fore.YELLOW}ℹ️  Using DexScreener Price (Quote Failed). Normalized Amt: {normalized_amount:.4f}")

                        if current_usd > 0:
                            # Calculate P&L
                            pnl_usd = current_usd - entry_usd
                            pnl_pct = ((current_usd - entry_usd) / entry_usd) * 100 if entry_usd > 0 else 0
                            
                            # Display current value
                            color = Fore.GREEN if pnl_pct >= 0 else Fore.RED
                            arrow = "📈" if pnl_pct >= 0 else "📉"
                            
                            print(f"\n{arrow} Current:")
                            print(f"  Value:   ${current_usd:.2f}")
                            print(f"{color}  P&L:     ${pnl_usd:+.2f} ({pnl_pct:+.1f}%){Style.RESET_ALL}")
                            # Warn if Liquidity Low
                            if current_liquidity > 0 and current_liquidity < 5000:
                                print(f"{Fore.RED}⚠️  LOW LIQUIDITY: ${current_liquidity:,.0f} (High Risk)")

                            # ------ STATE MACHINE INTEGRATION ------
                            # Pass data to State Machine for active management (Stop Loss / Take Profit)
                            
                            # Use DexScreener price if available, else implied
                            final_price = ds_price if ds_price > 0 else (current_usd / entry_amount)
                            
                            market_data = {
                                'price_usd': final_price,
                                'liquidity_usd': current_liquidity
                            }
                            
                            print(f"{Fore.CYAN}  🤖 Checking Exit Rules...")
                            
                            # Process via State Machine
                            sm_success, sm_msg = await state_machine.process_signal(
                                chain=chain,
                                token_address=token_addr,
                                signal_score=0, 
                                market_data=market_data
                            )
                            
                            if sm_success and "Execute" in sm_msg:
                                 print(f"{Fore.MAGENTA}  ⚡ ACTION TRIGGERED: {sm_msg}")
                            elif sm_success:
                                 print(f"{Fore.GREEN}  ✅ Status: {sm_msg}")
                            else:
                                 print(f"{Fore.YELLOW}  ⚠️ Status: {sm_msg}")

                            # ----------------------------------------
                            
                            total_entry_value += entry_usd
                            total_current_value += current_usd
                        else:
                            print(f"\n{Fore.YELLOW}⚠️  Unable to fetch current price (Quote Failed & API Error)")
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
            
            # Wait for next cycle
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"{Fore.RED}Monitor Loop Error: {e}")
            await asyncio.sleep(10)
            
    # Close client (Unreachable in infinite loop unless break)
    await okx_client.close()

if __name__ == "__main__":
    asyncio.run(monitor_positions())
