"""
Pattern Memory - SQLite Storage for Token Patterns

Stores historical token performance patterns to enable
similarity matching for new tokens.

Schema:
- id: Auto-inc
- chain: Chain name
- source: Source (pumpfun, uniswap)
- initial_score: First score
- liquidity: Initial liquidity
- momentum_confirmed: Boolean
- holder_concentration: Top 10 %
- phase: 'SNIPER', 'TRADE', 'WATCH'
- outcome: 'SUCCESS_2X', 'SUCCESS_3X', 'STALLED', 'DUMP'
- timestamp: Unix timestamp
"""
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

class PatternMemory:
    """
    Manages SQLite database for token patterns.
    """
    
    def __init__(self, db_path: str = "data/patterns.db"):
        self.db_path = Path(db_path)
        self._ensure_db()
        
    def _ensure_db(self):
        """Initialize database and schema."""
        if not self.db_path.parent.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain TEXT NOT NULL,
                source TEXT,
                initial_score INTEGER,
                liquidity REAL,
                momentum_confirmed BOOLEAN,
                holder_concentration REAL,
                phase TEXT,
                outcome TEXT,
                timestamp REAL
            )
        """)
        
        # Index for faster retrieval by chain
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_chain 
            ON patterns (chain, timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        
    def add_pattern(self, 
                   chain: str, 
                   source: str, 
                   initial_score: int, 
                   liquidity: float,
                   momentum_confirmed: bool,
                   holder_concentration: float,
                   phase: str,
                   outcome: str):
        """
        Store a new completed pattern.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO patterns 
                (chain, source, initial_score, liquidity, momentum_confirmed, holder_concentration, phase, outcome, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chain, source, initial_score, liquidity, 
                1 if momentum_confirmed else 0, 
                holder_concentration, phase, outcome, time.time()
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Pattern DB Error: {e}")
            
    def get_recent_patterns(self, chain: str, limit: int = 100) -> List[Dict]:
        """
        Get recent patterns for a chain to use in matching.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM patterns 
                WHERE chain = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (chain, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"⚠️ Pattern DB Read Error: {e}")
            return []
            
    def get_stats(self) -> Dict:
        """Get database statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*), chain FROM patterns GROUP BY chain")
            rows = cursor.fetchall()
            conn.close()
            
            return {row[1]: row[0] for row in rows}
        except Exception:
            return {}
