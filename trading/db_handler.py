"""
Database Handler for Trading Module
Handles SQLite connection and schema initialization.
"""

import sqlite3
import os
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.getcwd(), 'database', 'trading.db')

class TradingDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        directory = os.path.dirname(self.db_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database schema."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Table: positions
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT NOT NULL,
                chain TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                
                -- Entry
                entry_price REAL NOT NULL,
                entry_amount REAL NOT NULL,
                entry_value_usd REAL NOT NULL,
                entry_tx_hash TEXT NOT NULL,
                entry_timestamp INTEGER NOT NULL,
                
                -- Current
                current_price REAL,
                current_value_usd REAL,
                pnl_usd REAL,
                pnl_percent REAL,
                
                -- Exit (NULL if still open)
                exit_price REAL,
                exit_amount REAL,
                exit_value_usd REAL,
                exit_tx_hash TEXT,
                exit_timestamp INTEGER,
                
                -- Metadata
                signal_score REAL,
                status TEXT DEFAULT 'OPEN',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            ''')
            
            # Indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_address)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_wallet ON positions(wallet_address)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)')
            
            # Table: limit_orders
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS limit_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                trigger_price REAL NOT NULL,
                trigger_percent REAL NOT NULL,
                amount_percent REAL NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
            ''')
            
            # Table: trade_history
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                value_usd REAL NOT NULL,
                tx_hash TEXT NOT NULL,
                gas_fee REAL,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY (position_id) REFERENCES positions(id)
            )
            ''')
            
            conn.commit()
            conn.close()
            
            # Run migrations to ensure schema is up to date
            self._migrate_db()
            
            logger.info("Trading database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize trading database: {e}")
            raise

    def _migrate_db(self):
        """Check for missing columns and add them (Safe Migration)."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Check existing columns in positions
            cursor.execute("PRAGMA table_info(positions)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # Add 'high_pnl' if missing
            if 'high_pnl' not in columns:
                logger.info("MIGRATION: Adding 'high_pnl' column to positions table...")
                cursor.execute("ALTER TABLE positions ADD COLUMN high_pnl REAL DEFAULT 0.0")
                
            # Add 'trailing_stop_price' if missing
            if 'trailing_stop_price' not in columns:
                logger.info("MIGRATION: Adding 'trailing_stop_price' column to positions table...")
                cursor.execute("ALTER TABLE positions ADD COLUMN trailing_stop_price REAL DEFAULT 0.0")
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Database Migration Failed: {e}")

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            conn = self._get_conn()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM positions WHERE status IN ('OPEN', 'PARTIAL_OPEN')")
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching open positions: {e}")
            return []

    def create_position(self, data: Dict) -> int:
        """Create a new position record."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))
            sql = f"INSERT INTO positions ({columns}) VALUES ({placeholders})"
            
            cursor.execute(sql, list(data.values()))
            position_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            return position_id
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return -1

    def update_high_pnl(self, position_id: int, high_pnl: float):
        """Update the High Watermark PnL for trailing stop."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE positions SET high_pnl = ?, updated_at = ? WHERE id = ?",
                (high_pnl, int(time.time()), position_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating high pnl: {e}")
