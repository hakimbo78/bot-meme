#!/usr/bin/env python3
"""
Quick Position Status - Fast overview without API calls
Shows position count and basic stats from DB
"""

from colorama import Fore, init
from trading.position_tracker import PositionTracker

init(autoreset=True)

def quick_status():
    """Quick position status from database"""
    
    position_tracker = PositionTracker()
    
    # Get all positions
    all_positions = position_tracker.db._get_conn().execute(
        "SELECT status, COUNT(*) as count, SUM(entry_value_usd) as total_usd FROM positions GROUP BY status"
    ).fetchall()
    
    print(f"{Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{Fore.GREEN}📊 QUICK STATUS")
    print(f"{Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if not all_positions:
        print(f"{Fore.YELLOW}No positions yet")
        return
    
    for status, count, total_usd in all_positions:
        icon = "🟢" if status == "OPEN" else "🔵" if status == "MOONBAG" else "⚪"
        print(f"{icon} {status:10s}: {count:2d} positions (${total_usd or 0:.2f})")
    
    # Get open positions detail
    open_positions = position_tracker.get_open_positions()
    
    if open_positions:
        print(f"\n{Fore.YELLOW}🟢 OPEN POSITIONS:")
        for pos in open_positions:
            token_short = f"{pos['token_address'][:6]}...{pos['token_address'][-4:]}"
            print(f"  #{pos['id']} | {pos['chain'].upper():7s} | {token_short} | ${pos['entry_value_usd']:.2f}")
    
    print(f"{Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{Fore.CYAN}💡 Run 'python monitor_positions.py' for live P&L")
    print(f"{Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

if __name__ == "__main__":
    quick_status()
