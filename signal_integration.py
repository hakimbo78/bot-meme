"""
Signal Integration Module
Orchestrates the signal-only mode flow:
1. Age Filter (< 3 hours)
2. Moralis Bonding Curve Check (Solana)
3. Liquidity Filter (>= $20K)
4. Security Audit (RugCheck/GoPlus)
5. Score Threshold Check
6. BUY/WATCH Recommendation Dispatch
"""

import logging
from typing import Dict, Optional, Tuple

from signal_notifier import SignalNotifier, get_signal_notifier
from trading_config import TRADING_CONFIG
from security_audit import audit_token, check_bonding_curve

logger = logging.getLogger(__name__)


class SignalIntegration:
    """
    Signal-Only Mode Integration.
    
    Replaces trading execution with recommendation alerts.
    """
    
    def __init__(self, telegram_notifier=None):
        self.moralis = None # Removed direct moralis client usage
        self.signal_notifier = None
        
        if telegram_notifier:
            self.signal_notifier = SignalNotifier(telegram_notifier)
        
        # Config
        signal_config = TRADING_CONFIG.get('signal_mode', {})
        self.enabled = signal_config.get('enabled', False)
        self.max_age_hours = signal_config.get('max_age_hours', 24.0)
        self.min_age_hours = signal_config.get('min_age_hours', 1.0)    # NEW: Min age 1h
        self.min_liquidity = signal_config.get('min_liquidity', 20000)  # $20K default
        
        # Score thresholds
        thresholds = signal_config.get('score_thresholds', {})
        self.threshold_buy = thresholds.get('buy', 70)
        self.threshold_watch = thresholds.get('watch', 50)
        
        # Stats
        self.stats = {
            'processed': 0,
            'age_filtered': 0,
            'bc_filtered': 0,
            'liquidity_filtered': 0,
            'security_filtered': 0,
            'buy_signals': 0,
            'watch_signals': 0,
            'skipped_low_score': 0,
        }
        
        print(f"[SIGNAL] 🚀 Signal Mode Initialized (enabled={self.enabled}, age={self.min_age_hours}h-{self.max_age_hours}h, min_liq=${self.min_liquidity:,.0f})")
    
    def check_age_filter(self, pair_data: Dict) -> Tuple[bool, str]:
        """
        Check if token is within age range (min_age < age < max_age).
        """
        age_hours = pair_data.get('pair_age_hours', pair_data.get('age_days', 0) * 24)
        
        if age_hours < self.min_age_hours:
            self.stats['age_filtered'] += 1
            return False, f"Age {age_hours:.2f}h < {self.min_age_hours}h min limit"
            
        if age_hours > self.max_age_hours:
            self.stats['age_filtered'] += 1
            return False, f"Age {age_hours:.2f}h > {self.max_age_hours}h limit"
        
        return True, ""
    
    def check_bonding_curve(self, token_address: str, chain: str) -> Tuple[bool, float, str]:
        """
        Check bonding curve graduation status (Solana only).
        Uses security_audit module (RugCheck + Moralis fallback).
        
        Returns:
            (passed, progress, reason)
        """
        # Only check for Solana tokens
        if chain.lower() != 'solana':
            return True, 100.0, "Not Solana (skip BC check)"
        
        # Use improved check from security_audit
        result = check_bonding_curve(token_address, chain)
        
        if result['is_bonding_curve']:
            self.stats['bc_filtered'] += 1
            return False, result['progress'], f"Bonding Curve {result['progress']:.1f}% ({result['reason']})"
        
        return True, 100.0, "Graduated"
    
    async def process_signal(self, pair_data: Dict, score_data: Dict, 
                              security_data: Dict = None) -> Optional[str]:
        """
        Process a pair through signal-only flow.
        
        Flow:
        1. Age Filter (< max_age_hours)
        2. Moralis BC Check (Solana only)
        3. Liquidity Filter (>= $20K)
        4. Score Threshold Check (BUY >= 70, WATCH >= 50)
        5. Send Recommendation
        
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
            print(f"[SIGNAL] ⏳ {symbol} skipped: {age_reason}")
            return None
        
        # 2. BONDING CURVE CHECK (Solana only)
        bc_passed, bc_progress, bc_reason = self.check_bonding_curve(token_address, chain)
        if not bc_passed:
            print(f"[SIGNAL] ⛔ {symbol} skipped: {bc_reason}")
            return None
        
        # 3. LIQUIDITY FILTER (Minimum $20K)
        liquidity = pair_data.get('liquidity', pair_data.get('liquidity_usd', 0))
        if liquidity < self.min_liquidity:
            self.stats['liquidity_filtered'] += 1
            print(f"[SIGNAL] 💰 {symbol} skipped: Liq ${liquidity:,.0f} < ${self.min_liquidity:,.0f}")
            return None
        
        # 4. SECURITY AUDIT (RugCheck for Solana, GoPlus for EVM)
        print(f"[SIGNAL] 🔐 Running security audit for {symbol}...")
        security_data = audit_token(token_address, chain)
        
        if security_data.get('risk_level') == 'FAIL':
            self.stats['security_filtered'] += 1
            risks = security_data.get('risks', ['Unknown risk'])
            risk_str = ', '.join(risks[:2]) if risks else 'High risk score'
            print(f"[SIGNAL] 🚫 {symbol} skipped: SECURITY FAIL - {risk_str}")
            return None
        
        print(f"[SIGNAL] ✅ {symbol} security: {security_data.get('risk_level')} (Score: {security_data.get('risk_score', 0)})")
        
        # 5. SCORE THRESHOLD CHECK
        score = score_data.get('final_score', score_data.get('offchain_score', 0))
        
        if score >= self.threshold_buy:
            tier = 'BUY'
        elif score >= self.threshold_watch:
            tier = 'WATCH'
        else:
            self.stats['skipped_low_score'] += 1
            print(f"[SIGNAL] 📉 {symbol} skipped: Score {score:.0f} < {self.threshold_watch}")
            return None
        
        # 6. SEND RECOMMENDATION
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
            
            # Pass REAL security data from audit
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
