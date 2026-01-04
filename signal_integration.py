"""
Signal Integration Module
Orchestrates the signal-only mode flow:
1. Age Filter (< 1 hour)
2. Moralis Bonding Curve Check (Solana)
3. Security Analysis
4. BUY/WATCH Recommendation Dispatch
"""

import logging
from typing import Dict, Optional, Tuple

from moralis_client import get_moralis_client
from signal_notifier import SignalNotifier, get_signal_notifier
from trading_config import TRADING_CONFIG

logger = logging.getLogger(__name__)


class SignalIntegration:
    """
    Signal-Only Mode Integration.
    
    Replaces trading execution with recommendation alerts.
    """
    
    def __init__(self, telegram_notifier=None):
        self.moralis = get_moralis_client()
        self.signal_notifier = None
        
        if telegram_notifier:
            self.signal_notifier = SignalNotifier(telegram_notifier)
        
        # Config
        signal_config = TRADING_CONFIG.get('signal_mode', {})
        self.enabled = signal_config.get('enabled', False)
        self.max_age_hours = signal_config.get('max_age_hours', 1.0)
        
        # Score thresholds
        thresholds = signal_config.get('score_thresholds', {})
        self.threshold_buy = thresholds.get('buy', 70)
        self.threshold_watch = thresholds.get('watch', 50)
        
        # Stats
        self.stats = {
            'processed': 0,
            'age_filtered': 0,
            'bc_filtered': 0,
            'buy_signals': 0,
            'watch_signals': 0,
            'skipped_low_score': 0,
        }
        
        logger.info(f"[SignalIntegration] Initialized (enabled={self.enabled}, max_age={self.max_age_hours}h)")
    
    def check_age_filter(self, pair_data: Dict) -> Tuple[bool, str]:
        """
        Check if token is within age limit (< max_age_hours).
        
        Returns:
            (passed, reason)
        """
        age_hours = pair_data.get('pair_age_hours', 0)
        if age_hours == 0:
            # Try age_days conversion
            age_days = pair_data.get('age_days', 0)
            age_hours = age_days * 24
        
        if age_hours > self.max_age_hours:
            self.stats['age_filtered'] += 1
            return False, f"Age {age_hours:.2f}h > {self.max_age_hours}h limit"
        
        return True, ""
    
    def check_bonding_curve(self, token_address: str, chain: str) -> Tuple[bool, float, str]:
        """
        Check bonding curve graduation status (Solana only).
        
        Returns:
            (passed, progress, reason)
        """
        # Only check for Solana tokens
        if chain.lower() != 'solana':
            return True, 100.0, "Not Solana (skip BC check)"
        
        result = self.moralis.check_bonding_status(token_address)
        
        if result['is_graduated']:
            return True, result['progress'], "Graduated"
        else:
            self.stats['bc_filtered'] += 1
            return False, result['progress'], f"Bonding Curve {result['progress']:.1f}% (Not Graduated)"
    
    async def process_signal(self, pair_data: Dict, score_data: Dict, 
                              security_data: Dict = None) -> Optional[str]:
        """
        Process a pair through signal-only flow.
        
        Flow:
        1. Age Filter
        2. Moralis BC Check (Solana)
        3. Score Threshold Check
        4. Send Recommendation
        
        Returns:
            'BUY', 'WATCH', or None
        """
        if not self.enabled:
            return None
        
        self.stats['processed'] += 1
        
        token_address = pair_data.get('token_address', pair_data.get('address', ''))
        chain = pair_data.get('chain', 'unknown')
        symbol = pair_data.get('symbol', pair_data.get('token_symbol', '???'))
        
        # 1. AGE FILTER
        age_passed, age_reason = self.check_age_filter(pair_data)
        if not age_passed:
            logger.debug(f"[Signal] {symbol} skipped: {age_reason}")
            return None
        
        # 2. BONDING CURVE CHECK (Solana only)
        bc_passed, bc_progress, bc_reason = self.check_bonding_curve(token_address, chain)
        if not bc_passed:
            logger.info(f"[Signal] ⏳ {symbol} skipped: {bc_reason}")
            return None
        
        # 3. SCORE THRESHOLD CHECK
        score = score_data.get('final_score', score_data.get('offchain_score', 0))
        
        if score >= self.threshold_buy:
            tier = 'BUY'
        elif score >= self.threshold_watch:
            tier = 'WATCH'
        else:
            self.stats['skipped_low_score'] += 1
            logger.debug(f"[Signal] {symbol} skipped: Score {score:.0f} < {self.threshold_watch}")
            return None
        
        # 4. SEND RECOMMENDATION
        if self.signal_notifier:
            # Prepare token_data with required fields
            token_data = {
                'name': pair_data.get('name', pair_data.get('token_name', symbol)),
                'symbol': symbol,
                'chain': chain,
                'address': token_address,
                'liquidity_usd': pair_data.get('liquidity', pair_data.get('liquidity_usd', 0)),
                'volume_24h': pair_data.get('volume_24h', 0),
                'price_change_h1': pair_data.get('price_change_1h', pair_data.get('price_change_h1', 0)),
                'pair_age_hours': pair_data.get('pair_age_hours', pair_data.get('age_days', 0) * 24),
                'url': pair_data.get('url', ''),
            }
            
            await self.signal_notifier.send_recommendation(token_data, score_data, security_data)
            
            if tier == 'BUY':
                self.stats['buy_signals'] += 1
            else:
                self.stats['watch_signals'] += 1
        
        return tier
    
    def get_stats(self) -> Dict:
        """Get signal integration statistics."""
        return {
            'signal_mode_enabled': self.enabled,
            'max_age_hours': self.max_age_hours,
            **self.stats
        }
    
    def print_stats(self):
        """Print formatted statistics."""
        print(f"\n📊 Signal Integration Stats:")
        print(f"   Processed: {self.stats['processed']}")
        print(f"   Age Filtered: {self.stats['age_filtered']}")
        print(f"   BC Filtered: {self.stats['bc_filtered']}")
        print(f"   BUY Signals: {self.stats['buy_signals']}")
        print(f"   WATCH Signals: {self.stats['watch_signals']}")
        print(f"   Low Score Skipped: {self.stats['skipped_low_score']}")


# Singleton instance
_signal_integration = None

def get_signal_integration(telegram_notifier=None) -> SignalIntegration:
    """Get or create singleton SignalIntegration instance."""
    global _signal_integration
    if _signal_integration is None:
        _signal_integration = SignalIntegration(telegram_notifier)
    return _signal_integration
