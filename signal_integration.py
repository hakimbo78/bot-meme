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
            
            # PHASE 2: Initialize Circuit Breaker Telegram notifier
            from security_audit import set_telegram_notifier
            set_telegram_notifier(telegram_notifier)
        
        # Config - Stable Pump Mode
        signal_config = TRADING_CONFIG.get('signal_mode', {})
        self.enabled = signal_config.get('enabled', False) # Keep this line for the print statement
        self.max_age_hours = signal_config.get('max_age_hours', 24.0)
        self.min_age_hours = signal_config.get('min_age_hours', 1.0)
        self.min_liquidity = signal_config.get('min_liquidity', 20000)
        self.score_thresholds = signal_config.get('score_thresholds', {'buy': 70, 'watch': 50})
        
        # Config - Rebound Mode
        rebound_config = TRADING_CONFIG.get('rebound_mode', {})
        self.rebound_enabled = rebound_config.get('enabled', False)
        self.rebound_max_age = rebound_config.get('max_age_hours', 720.0)  # 30 days
        self.rebound_min_age = rebound_config.get('min_age_hours', 1.0)
        self.rebound_min_ath_drop = rebound_config.get('min_ath_drop_percent', 80.0)
        self.rebound_min_liquidity = rebound_config.get('min_liquidity', 10000)
        self.rebound_min_volume = rebound_config.get('min_volume_24h', 10000)
        self.rebound_score_threshold = rebound_config.get('score_thresholds', {}).get('rebound', 60)
        
        # Birdeye Client for ATH tracking
        if self.rebound_enabled:
            from birdeye_client import get_birdeye_client
            self.birdeye = get_birdeye_client()
        else:
            self.birdeye = None
        
        # Stats
        self.stats = {
            'total_processed': 0,
            'age_filtered': 0,
            'bc_filtered': 0,
            'liquidity_filtered': 0,
            'security_filtered': 0,
            'score_filtered': 0,
            'signals_sent': 0,
            'rebound_candidates': 0,  # NEW
            'rebound_signals': 0       # NEW
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
    
    async def check_bonding_curve(self, token_address: str, chain: str) -> Tuple[bool, float, str]:
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
        result = await check_bonding_curve(token_address, chain)
        
        if result['is_bonding_curve']:
            self.stats['bc_filtered'] += 1
            return False, result['progress'], f"Bonding Curve {result['progress']:.1f}% ({result['reason']})"
        
        return True, 100.0, "Graduated (Raydium/Orca/Meteora)"
    
    async def check_ath_rebound(self, token_address: str, chain: str, pair_data: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Check if token is a rebound candidate (>80% drop from ATH + still active).
        
        Returns:
            (is_candidate, ath_data)
        """
        if not self.rebound_enabled or not self.birdeye:
            return False, None
        
        try:
            # 1. Calculate ATH from Birdeye OHLCV
            ath_data = await self.birdeye.calculate_ath(token_address, chain)
            
            if ath_data.get('error'):
                print(f"[REBOUND] ⚠️ ATH calculation failed: {ath_data['error']}")
                return False, None
            
            drop_pct = ath_data.get('drop_percent', 0)
            
            # 2. Check if drop >= threshold
            if drop_pct < self.rebound_min_ath_drop:
                return False, None
            
            # 3. Check activity (still active, not dead)
            volume_24h = pair_data.get('volume', {}).get('h24', 0)
            if volume_24h < self.rebound_min_volume:
                print(f"[REBOUND] ⏭️ Low volume: ${volume_24h:,.0f} < ${self.rebound_min_volume:,.0f}")
                return False, None
            
            # 4. Check liquidity
            liquidity = pair_data.get('liquidity', pair_data.get('liquidity_usd', 0))
            if liquidity < self.rebound_min_liquidity:
                print(f"[REBOUND] ⏭️ Low liquidity: ${liquidity:,.0f} < ${self.rebound_min_liquidity:,.0f}")
                return False, None
            
            print(f"[REBOUND] 🎯 CANDIDATE FOUND! ATH: ${ath_data['ath']:.8f}, Current: ${ath_data['current_price']:.8f}, Drop: {drop_pct:.1f}%")
            self.stats['rebound_candidates'] += 1
            
            return True, ath_data
            
        except Exception as e:
            print(f"[REBOUND] ❌ Error checking ATH: {e}")
            return False, None
    
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
        bc_passed, bc_progress, bc_reason = await self.check_bonding_curve(token_address, chain)
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
        security_data = await audit_token(token_address, chain)
        
        if security_data.get('risk_level') == 'FAIL':
            self.stats['security_filtered'] += 1
            risks = security_data.get('risks', ['Unknown risk'])
            risk_str = ', '.join(risks[:2]) if risks else 'High risk score'
            print(f"[SIGNAL] 🚫 {symbol} skipped: SECURITY FAIL - {risk_str}")
            return None
        
        print(f"[SIGNAL] ✅ {symbol} security: {security_data.get('risk_level')} (Score: {security_data.get('risk_score', 0)})")
        
        # 5. SCORE THRESHOLD CHECK
        score = score_data.get('score', 0)
        
        if score >= self.score_thresholds['buy']:
            signal_type = 'BUY'
        elif score >= self.score_thresholds['watch']:
            signal_type = 'WATCH'
        else:
            print(f"[SIGNAL] ⏭️ {symbol} skipped: Score {score} < {self.score_thresholds['watch']}")
            self.stats['score_filtered'] += 1
            
            # PHASE 3: Check if it's a REBOUND candidate instead
            if self.rebound_enabled:
                is_rebound, ath_data = await self.check_ath_rebound(token_address, chain, pair_data)
                
                if is_rebound:
                    # Rebound-specific score check
                    if score >= self.rebound_score_threshold:
                        signal_type = 'REBOUND'
                        print(f"[REBOUND] ✅ {symbol} qualified as REBOUND signal (score={score})")
                    else:
                        print(f"[REBOUND] ⏭️ {symbol} score too low for rebound: {score} < {self.rebound_score_threshold}")
                        return None
                else:
                    return None
            else:
                return None
        
        # 6. SEND RECOMMENDATION
        if not self.signal_notifier:
            print(f"[SIGNAL] ⚠️ No notifier configured - cannot send {signal_type} signal")
            return None
        
        # Prepare token data for notifier (include ATH data for REBOUND signals)
        token_data = {
            'symbol': symbol,
            'address': token_address,
            'chain': chain,
            'pair_address': pair_data.get('pair_address', ''),
            'price': pair_data.get('price', 0),
            'liquidity': pair_data.get('liquidity', pair_data.get('liquidity_usd', 0)),
            'volume_24h': pair_data.get('volume', {}).get('h24', 0),
            'score': score
        }
        
        # Add ATH data for rebound signals
        if signal_type == 'REBOUND' and ath_data:
            token_data['ath'] = ath_data.get('ath', 0)
            token_data['ath_drop_percent'] = ath_data.get('drop_percent', 0)
            token_data['ath_time'] = ath_data.get('ath_time', 0)
        
        # Send recommendation
        await self.signal_notifier.send_recommendation(
            signal_type=signal_type,
            token_data=token_data,
            score_data=score_data,
            security_data=security_data
        )
        
        if signal_type == 'REBOUND':
            self.stats['rebound_signals'] += 1
        else:
            self.stats['signals_sent'] += 1
        
        print(f"[SIGNAL] ✅ {signal_type} recommendation sent for {symbol}")
        return signal_type
    
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
