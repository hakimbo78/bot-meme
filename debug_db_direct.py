"""
Direct database query to check ALL positions (OPEN and CLOSED)
"""
import sqlite3
from datetime import datetime

# Connect to DB
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("\n" + "="*80)
print("DATABASE DIRECT QUERY - ALL POSITIONS")
print("="*80 + "\n")

# Get all positions
cursor.execute("SELECT id, token_address, chain, status, entry_timestamp, exit_timestamp, exit_tx_hash FROM positions ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()

print(f"Last 10 positions:\n")

for row in rows:
    pos_id, token, chain, status, entry_time, exit_time, exit_tx = row
    
    entry_dt = datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S") if entry_time else "N/A"
    exit_dt = datetime.fromtimestamp(exit_time).strftime("%Y-%m-%d %H:%M:%S") if exit_time else "N/A"
    
    print(f"ID: {pos_id}")
    print(f"  Token: {token[:10]}...{token[-8:]}")
    print(f"  Chain: {chain}")
    print(f"  Status: {status}")
    print(f"  Entry: {entry_dt}")
    print(f"  Exit: {exit_dt}")
    print(f"  Exit TX: {exit_tx if exit_tx else 'None'}")
    print()

# Count by status
cursor.execute("SELECT status, COUNT(*) FROM positions GROUP BY status")
status_counts = cursor.fetchall()

print("="*80)
print("POSITION COUNTS BY STATUS:")
print("="*80)
for status, count in status_counts:
    print(f"  {status}: {count}")

conn.close()
print()
