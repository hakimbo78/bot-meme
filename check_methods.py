from trading.db_handler import TradingDB
from trading.position_tracker import PositionTracker

db = TradingDB()
pt = PositionTracker(db)

# Check the class
import inspect
methods = [m for m in dir(pt) if not m.startswith('_')]
print("Available methods:")
for m in methods:
    print(f"  - {m}")
