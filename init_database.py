"""
Initialize trading database with proper schema
"""
from trading.db_handler import TradingDB

print("\n" + "="*60)
print("INITIALIZING TRADING DATABASE")
print("="*60 + "\n")

# Initialize DB (will create tables if not exist)
db = TradingDB()

print(f"✅ Database initialized at: {db.db_path}")

# Verify tables exist
import sqlite3
conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print(f"\nTables created:")
for table in tables:
    print(f"  - {table[0]}")

conn.close()

print("\n" + "="*60)
print("✅ DATABASE READY")
print("="*60 + "\n")
