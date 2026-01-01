"""
Debug script to check open positions in database
"""
from trading.db_handler import TradingDB
from trading.position_tracker import PositionTracker

db = TradingDB()
pt = PositionTracker(db)

print("\n" + "="*60)
print("POSITION TRACKER DEBUG")
print("="*60 + "\n")

# Get open positions
positions = pt.get_open_positions()

print(f"Total OPEN positions: {len(positions)}\n")

if positions:
    for p in positions:
        print(f"Position ID: {p['id']}")
        print(f"  Token: {p['token_address'][:10]}...{p['token_address'][-8:]}")
        print(f"  Chain: {p['chain']}")
        print(f"  Status: {p['status']}")
        print(f"  Entry Time: {p.get('entry_timestamp', 'N/A')}")
        print(f"  Entry Value: ${p.get('entry_value_usd', 0):.2f}")
        print(f"  Exit TX: {p.get('exit_tx_hash', 'None')}")
        print()
else:
    print("✅ No open positions found (all positions properly closed)")

print("="*60 + "\n")
