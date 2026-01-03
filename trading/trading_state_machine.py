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
        
    async def process_signal(self, chain: str, token_address: str, signal_score: float, market_data: Dict) -> Tuple[bool, str]:
        """
        Main entry point for trading signals.
        Decides whether to enter new trade or update existing one.
        Returns: (Success, Message)
        """
        if not self.config.get('enabled', False):
            logger.warning("State Machine disabled in config")
            return False, "State Machine Disabled"
            
        # Check if we already have a position for this token
        position = self.tracker.get_position_by_token(token_address)
        
        if not position:
            # NEW TRADE -> PROBE STATE
            return await self._handle_new_entry(chain, token_address, signal_score, market_data)
        else:
            # EXISTING TRADE -> WATCH/SCALE STATE
            return await self._handle_existing_position(position, signal_score, market_data)

    async def _handle_new_entry(self, chain: str, token_address: str, signal_score: float, market_data: Dict) -> Tuple[bool, str]:
        """Handle initial entry (PROBE)."""
        logger.info(f"🤖 SM: New Signal for {token_address} (Score: {signal_score}) -> Entering PROBE")
        
        # Calculate PROBE size (e.g. 50%)
        probe_pct = self.config.get('probe_size_pct', 50.0) / 100.0
        
        # Execute Buy
        success, msg = await self.executor.execute_buy(
            chain=chain,
            token_address=token_address,
            signal_score=signal_score
        )
        
        if success:
            logger.info(f"✅ SM: PROBE Buy Successful. State: PROBE")
            return True, "PROBE Entry Successful"
        else:
            logger.error(f"❌ SM: PROBE Buy Failed: {msg}")
            return False, msg

    async def _handle_existing_position(self, position: Dict, signal_score: float, market_data: Dict) -> Tuple[bool, str]:
        """Handle active position updates (WATCH / SCALE / EXIT)."""
        pos_id = position['id']
        current_price = market_data.get('price_usd', 0)
        entry_price = position['entry_price']
        
        if current_price <= 0 or entry_price <= 0:
            return False, "Invalid Price Data"
            
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
            return True, "Risk Exit Triggered"
            
        # 2. CHECK SCALE CONDITIONS (Winners)
        scale_profit_threshold = self.config.get('scale_profit_threshold', 20.0)
        scale_risk_max = self.config.get('scale_risk_max', 25)
        
        # Scaling logic TODO: Uncomment when confident
        # if self.config.get('scale_enabled') and pnl_pct > scale_profit_threshold and signal_score < scale_risk_max:
        #      logger.info(f"🚀 SM: SCALE SIGNAL! (+{pnl_pct:.1f}% Profit & Safe Score {signal_score})")
        #      # await self.executor.execute_buy(...) 

        # 3. GET EXIT CONFIG
        # State machine config takes precedence, but we fall back to global exit strategy if needed
        # Or better: check global exit strategies from main config passed via ConfigManager
        
        # For now, let's use the standard configurable values
        # If 'exit_strategy' is in self.config, use it. Otherwise use defaults.
        # Ideally, we should pull from ConfigManager.get_config()['exit_strategy']
        
        full_config = ConfigManager.get_config()
        exit_config = full_config.get('exit_strategy', {})
        
        stop_loss_pct = exit_config.get('stop_loss_percent', -50.0)
        take_profit_pct = exit_config.get('take_profit_percent', 150.0)
        trailing_stop_enabled = self.config.get('trailing_stop_enabled', False)
        
        # 4. HARD STOP LOSS
        if pnl_pct <= stop_loss_pct:
            logger.warning(f"🛑 SM: STOP LOSS Triggered ({pnl_pct:.1f}% <= {stop_loss_pct}%)")
            await self.executor.execute_sell(
                chain=position['chain'],
                token_address=position['token_address'],
                amount_raw=position['amount'],
                position_id=pos_id,
                new_status='STOP_LOSS'
            )
            return True, "Stop Loss Execute"

        # 5. TAKE PROFIT
        if pnl_pct >= take_profit_pct:
            logger.info(f"💎 SM: TAKE PROFIT Triggered (+{pnl_pct:.1f}% >= +{take_profit_pct}%)")
            await self.executor.execute_sell(
                chain=position['chain'],
                token_address=position['token_address'],
                amount_raw=position['amount'],
                position_id=pos_id,
                new_status='TAKE_PROFIT'
            )
            return True, "Take Profit Execute"
            
        # 6. TRAILING STOP
        if trailing_stop_enabled:
            # Trailing Logic:
            # If PnL > Activation (e.g. 20%), set/update trailing floor
            # If PnL drops below floor, exit
            activation_pct = self.config.get('trailing_activation', 20.0)
            distance_pct = self.config.get('trailing_distance', 10.0)
            
            # Check highest PnL recorded for this position (Need to support tracking high-water mark)
            # For now, we use current PnL as simplified check if we don't have high-water mark in DB yet
            # TODO: Improve PositionTracker to store 'highest_pnl'
            
            # Simplified Trailing: If we are deep in profit but dropped X% from perceived peak?
            # Without DB support for high-water mark, we can't implement true trailing yet.
            # We will rely on simple Hard SL/TP for now or dynamic SL adjustments
            pass

        return True, "Position Monitored"
