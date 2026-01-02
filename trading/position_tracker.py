"""
Position Tracker
Manages trade recording, PnL calculation, and position updates.
"""

from .db_handler import TradingDB
from typing import Dict, Optional, List
import time
import logging

logger = logging.getLogger(__name__)

class PositionTracker:
    def __init__(self, db: TradingDB):
        self.db = db

    def record_buy(
        self,
        token_address: str,
        chain: str,
        wallet_address: str,
        amount: float,
        price: float,
        value_usd: float,
        tx_hash: str,
        signal_score: float = 0
    ) -> int:
        """
        Record a new buy position.
        
        Args:
            token_address: Token contract address
            chain: Chain name
            wallet_address: Wallet used
            amount: Token amount bought
            price: Buy price per token
            value_usd: Total USD value
            tx_hash: Transaction hash
            signal_score: Score from signal detected
            
        Returns:
            position_id (int) or -1 if failed
        """
        try:
            position_data = {
                'token_address': token_address,
                'chain': chain.lower(),
                'wallet_address': wallet_address,
                'entry_price': price,
                'entry_amount': amount,
                'entry_value_usd': value_usd,
                'entry_tx_hash': tx_hash,
                'entry_timestamp': int(time.time()),
                'current_price': price,
                'current_value_usd': value_usd,
                'pnl_usd': 0.0,
                'pnl_percent': 0.0,
                'signal_score': signal_score,
                'status': 'OPEN',
                'created_at': int(time.time()),
                'updated_at': int(time.time())
            }
            
            pid = self.db.create_position(position_data)
            logger.info(f"Recorded BUY for {token_address} (ID: {pid})")
            return pid
        except Exception as e:
            logger.error(f"Failed to record buy: {e}")
            return -1

    def record_sell(
        self,
        position_id: int,
        amount: float,
        price: float,
        value_usd: float,
        tx_hash: str,
        new_status: str = 'CLOSED'
    ) -> bool:
        """
        Record a sell (close position).
        """
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            # Get entry info
            cursor.execute("SELECT entry_value_usd FROM positions WHERE id = ?", (position_id,))
            row = cursor.fetchone()
            if not row:
                return False
                
            entry_usd = row[0]
            pnl_usd = value_usd - entry_usd
            pnl_percent = (pnl_usd / entry_usd) * 100 if entry_usd > 0 else 0
            
            sql = """
            UPDATE positions SET
                exit_price = ?,
                exit_amount = ?,
                exit_value_usd = ?,
                exit_tx_hash = ?,
                exit_timestamp = ?,
                pnl_usd = ?,
                pnl_percent = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
            """
            
            cursor.execute(sql, (
                price, amount, value_usd, tx_hash, int(time.time()),
                pnl_usd, pnl_percent, new_status, int(time.time()), position_id
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Recorded SELL for Position {position_id}. PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record sell: {e}")
            return False

    def force_close_position(self, position_id: int, reason: str = "MANUAL_EXIT") -> bool:
        """Force close a position (e.g. detected manual sell)."""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            # Update status only
            sql = """
            UPDATE positions SET
                status = 'CLOSED',
                exit_tx_hash = ?,
                exit_timestamp = ?,
                updated_at = ?
            WHERE id = ?
            """
            cursor.execute(sql, (reason, int(time.time()), int(time.time()), position_id))
            conn.commit()
            conn.close()
            logger.info(f"Position {position_id} FORCE CLOSED (Reason: {reason})")
            return True
        except Exception as e:
            logger.error(f"Failed to force close pos {position_id}: {e}")
            return False

    def update_pnl(self, position_id: int, current_price: float):
        """Update realtime PnL for a position."""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("SELECT entry_amount, entry_value_usd FROM positions WHERE id = ?", (position_id,))
            row = cursor.fetchone()
            if not row:
                return
                
            amount, entry_usd = row
            current_value_usd = amount * current_price
            pnl_usd = current_value_usd - entry_usd
            pnl_percent = (pnl_usd / entry_usd) * 100 if entry_usd > 0 else 0
            
            sql = """
            UPDATE positions SET
                current_price = ?,
                current_value_usd = ?,
                pnl_usd = ?,
                pnl_percent = ?,
                updated_at = ?
            WHERE id = ?
            """
            cursor.execute(sql, (current_price, current_value_usd, pnl_usd, pnl_percent, int(time.time()), position_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update PnL for {position_id}: {e}")
    
    def get_position(self, position_id: int) -> Optional[Dict]:
        """Get a single position by ID."""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            # Get column names
            col_names = [description[0] for description in cursor.description]
            position = dict(zip(col_names, row))
            
            conn.close()
            return position
        except Exception as e:
            logger.error(f"Failed to get position {position_id}: {e}")
            return None

    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            # Select all columns
            cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
            rows = cursor.fetchall()
            
            # Get column names
            col_names = [description[0] for description in cursor.description]
            
            positions = []
            for row in rows:
                positions.append(dict(zip(col_names, row)))
                def get_position_by_token(self, token_address: str) -> Optional[Dict]:
        """Get the active OPEN position for a token address."""
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()
            
            # Find OPEN position for this token
            cursor.execute(
                "SELECT * FROM positions WHERE token_address = ? AND status = 'OPEN'", 
                (token_address,)
            )
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            # Get column names
            col_names = [description[0] for description in cursor.description]
            position = dict(zip(col_names, row))
            
            conn.close()
            return position
        except Exception as e:
            logger.error(f"Failed to get position by token {token_address}: {e}")
            return None
