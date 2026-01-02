"""
Trading State Machine
Manages active trading states: PROBE -> WATCH -> SCALE -> EXIT
"""

import logging
from enum import Enum
from typing import Dict, Tuple, Optional
from .trade_executor import TradeExecutor
from .position_tracker import PositionTracker
from .config_manager import ConfigManager

logger = logging.getLogger(__name__)

class TradingState(Enum):
    IDLE = "IDLE"   # No position
    PROBE = "PROBE" # Initial entry (Test)
    WATCH = "WATCH" # Monitoring (Trailing SL)
    SCALE = "SCALE" # Adding to winner
    EXIT = "EXIT"   # Closing position

class TradingStateMachine:
    def __init__(self, executor: TradeExecutor, tracker: PositionTracker):
        self.executor = executor
        self.tracker = tracker
        self.config = ConfigManager.get_config()['state_machine']
        
    async def process_signal(self, chain: str, token_address: str, signal_score: float, market_data: Dict) -> bool:
        """
        Main entry point for trading signals.
        Decides whether to enter new trade or update existing one.
        """
        if not self.config.get('enabled', False):
            logger.warning("State Machine disabled in config")
            return False
            
        # Check if we already have a position for this token
        position = self.tracker.get_position_by_token(chain, token_address)
        
        if not position:
            # NEW TRADE -> PROBE STATE
            return await self._handle_new_entry(chain, token_address, signal_score, market_data)
        else:
            # EXISTING TRADE -> WATCH/SCALE STATE
            return await self._handle_existing_position(position, signal_score, market_data)

    async def _handle_new_entry(self, chain: str, token_address: str, signal_score: float, market_data: Dict) -> bool:
        """Handle initial entry (PROBE)."""
        logger.info(f"🤖 SM: New Signal for {token_address} (Score: {signal_score}) -> Entering PROBE")
        
        # Calculate PROBE size (e.g. 50%)
        probe_pct = self.config.get('probe_size_pct', 50.0) / 100.0
        
        # We need to hack the budget temporarily or pass size to executor
        # Ideally executor should accept size_multiplier, but for now we trust executor checks budget
        # TODO: Modify executor to accept custom amount. For now, we rely on budget.
        
        # Execute Buy
        success, msg = await self.executor.execute_buy(
            chain=chain,
            token_address=token_address,
            signal_score=signal_score
            # amount_multiplier=probe_pct (Future improvement)
        )
        
        if success:
            logger.info(f"✅ SM: PROBE Buy Successful. State: PROBE")
            # Position tracker automatically sets status to OPEN.
            # We can optionally tag it as 'PROBE' in metadata if we extend DB schema.
            return True
        else:
            logger.error(f"❌ SM: PROBE Buy Failed: {msg}")
            return False

    async def _handle_existing_position(self, position: Dict, signal_score: float, market_data: Dict) -> bool:
        """Handle active position updates (WATCH / SCALE / EXIT)."""
        pos_id = position['id']
        current_price = market_data.get('price_usd', 0)
        entry_price = position['entry_price']
        
        if current_price <= 0 or entry_price <= 0:
            return False
            
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        logger.info(f"🔄 SM: Monitoring Pos {pos_id} | PnL: {pnl_pct:.1f}% | Score: {signal_score}")
        
        # 1. CHECK EXIT CONDITIONS (Emergency)
        emergency_risk_limit = self.config.get('emergency_risk_exit', 80)
        if signal_score > emergency_risk_limit:
            logger.warning(f"🚨 SM: Risk Spike ({signal_score} > {emergency_risk_limit}) -> TRIGGER EXIT")
            await self.executor.execute_sell(
                chain=position['chain'],
                token_address=position['token_address'],
                amount_raw=position['amount'],
                position_id=pos_id,
                new_status='RISK_EXIT'
            )
            return True
            
        # 2. CHECK SCALE CONDITIONS (Winners)
        # Only scale if we haven't scaled yet (check open_positions count or metadata)
        # Using simplified logic: If PnL > 20% and Score < 25 (Super Safe)
        scale_profit_threshold = self.config.get('scale_profit_threshold', 20.0)
        scale_risk_max = self.config.get('scale_risk_max', 25)
        
        if self.config.get('scale_enabled') and pnl_pct > scale_profit_threshold and signal_score < scale_risk_max:
             # Check if we already double-downed? (Need metadata, skipping for MVP)
             logger.info(f"🚀 SM: SCALE SIGNAL! (+{pnl_pct:.1f}% Profit & Safe Score {signal_score})")
             # await self.executor.execute_buy(...) # TODO: Implement Scale Buy
             # For MVP, just log it.
             pass
             
        # 3. TRAILING STOP (Future)
        if self.config.get('trailing_stop_enabled'):
            # Logic to update SL in DB
            pass
            
        return True
