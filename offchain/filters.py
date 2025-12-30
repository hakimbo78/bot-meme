"""
MODE C V3: DEGEN SNIPER FILTERS

Hybrid off-chain–first filtering system.
Score-based gating: 
- Low (30-44): Rate limited.
- Mid (45-64): Normal alert.
- High (>=65): On-chain verify.

Normalized Data Input:
{
  "chain": "...",
  "pair_address": "...",
  "token_address": "...",
  "liquidity": 0,
  "volume_24h": 0,
  "price_change_5m": 0,
  "price_change_1h": 0,
  "tx_5m": 0,
  "tx_24h": 0,
  "age_days": 0,
  "offchain_score": 0,
  "event_type": "SECONDARY_MARKET",
  "source": "dexscreener"
}
"""

from typing import Dict, Optional, Tuple, List
from datetime import datetime

class OffChainFilter:
    """
    MODE C V3: DEGEN SNIPER Filter & Scorer
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Extract configuration sections
        self.global_guardrails = self.config.get('global_guardrails', {})
        self.scoring_config = self.config.get('scoring_v3', {})
        self.tiers = self.config.get('telegram_tiers', {})
        
        # Stats
        self.stats = {
            'total_evaluated': 0,
            'level0_rejected': 0,
            'level1_rejected': 0,
            'low_score_rejected': 0,
            'passed': 0,
            'scores': []
        }
    
    def apply_filters(self, pair: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Apply V3 filters and calculate score.
        
        Returns:
            (passed: bool, reason: str or None, metadata: dict or None)
        """
        self.stats['total_evaluated'] += 1
        
        pair_addr = pair.get('pair_address', 'UNKNOWN')[:10]
        
        # 1. Level-0 Filter (Ultra Loose)
        passed_l0, l0_reason = self._check_level0_filter(pair)
        if not passed_l0:
            self.stats['level0_rejected'] += 1
            self._log_drop(pair, f"LEVEL-0: {l0_reason}")
            return False, f"LEVEL-0: {l0_reason}", None
            
        # 2. Level-1 Filter (Momentum) & Revival Rule
        passed_l1, l1_reason = self._check_level1_and_revival(pair)
        if not passed_l1:
            self.stats['level1_rejected'] += 1
            self._log_drop(pair, f"LEVEL-1: {l1_reason}")
            return False, f"LEVEL-1: {l1_reason}", None
            
        # 3. Calculate Score (DOES NOT BLOCK PROCESSING)
        score = self._calculate_score_v3(pair)
        pair['offchain_score'] = score
        
        # Score is used ONLY for tier assignment, NOT for filtering
        self.stats['passed'] += 1
        self.stats['scores'].append(score)
        
        # Determine Verdict
        verdict = "ALERT_ONLY"
        thresholds = self.scoring_config.get('thresholds', {})
        verify_threshold = thresholds.get('verify', 65)
        
        if score >= verify_threshold:
            verdict = "VERIFY"
             
        metadata = {
            'score': score,
            'verdict': verdict,
            'verify_threshold': verify_threshold
        }
        
        return True, None, metadata

    def _check_level0_filter(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        LEVEL-0 FILTER (ULTRA LOOSE):
        - liquidity >= 500
        - tx_5m >= 1 (RELAXED with conditional logic)
        
        PATCHES APPLIED:
        - PATCH 1: Conditional inactivity (not absolute)
        - PATCH 2: Age-based bypass for new pairs
        - PATCH 3: Solana-specific exception
        """
        # Liquidity
        liq = pair.get('liquidity', 0)
        min_liq = self.global_guardrails.get('min_liquidity_usd', 500)
        if liq < min_liq:
            return False, f"Liquidity too low (${liq} < ${min_liq})"
            
        # Tx 5m - RELAXED LOGIC
        tx_5m = pair.get('tx_5m', 0)
        min_tx = self.global_guardrails.get('min_tx_5m', 1)
        
        if tx_5m < min_tx:
            age_days = pair.get('age_days', 0)
            if age_days is None:
                age_days = 0.0
            price_change_1h = pair.get('price_change_1h', 0) or 0
            chain = pair.get('chain', '').lower()
            volume_24h = pair.get('volume_24h', 0)
            
            # PATCH 2: Age-based bypass - new pairs frequently have no tx_5m yet
            if age_days <= 0.5:
                # Allow new pairs to pass without tx_5m requirement
                return True, None
                
            # PATCH 3: Solana-specific exception - delayed tx_5m reporting
            if chain == "solana" and liq >= 50000 and volume_24h >= 50000:
                # Solana pairs with strong liquidity/volume can pass despite missing tx_5m
                return True, None
            
            # PATCH 1: Conditional inactivity - only reject if old + flat + no activity
            if age_days > 1 and price_change_1h <= 0:
                return False, f"Fully inactive (old={age_days:.1f}d, flat, tx_5m={tx_5m})"
            
            # Otherwise allow: dormant/early/revival pairs can pass
            # (they have either: young age OR positive price movement)
            return True, None
            
        return True, None
        
    def _check_level1_and_revival(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        LEVEL-1 FILTER + REVIVAL RULE
        
        CRITICAL: Uses OR logic for momentum (NOT AND)
        """
        age_days = pair.get('age_days', 0)
        if age_days is None: 
            age_days = 0.0
            
        price_change_5m = pair.get('price_change_5m', 0) or 0
        price_change_1h = pair.get('price_change_1h', 0) or 0
        tx_5m = pair.get('tx_5m', 0)
        
        # REVIVAL RULE: If age > 30 days
        if age_days > 30:
            # Require fresh activity: (price_change_5m >= 5 OR tx_5m >= 5)
            is_revival = (abs(price_change_5m) >= 5) or (tx_5m >= 5)
            if not is_revival:
                return False, f"Old pair ({age_days:.1f}d) no revival momentum"
            return True, None
            
        # MOMENTUM FILTER (OR LOGIC - CRITICAL)
        # Pass if ANY condition is true:
        momentum = (
            abs(price_change_5m) >= 5
            or abs(price_change_1h) >= 15
            or tx_5m >= 5
        )
        
        if not momentum:
            return False, "No momentum (p5m<5, p1h<15, tx5m<5)"
            
        return True, None

    def _calculate_score_v3(self, pair: Dict) -> float:
        """
        Calculate 0-100 score based on V3 components.
        """
        points_config = self.scoring_config.get('points', {})
        
        score = 0.0
        
        # 1. Price Change 5m (0-30)
        p5m_cap = points_config.get('price_change_5m', 30)
        p5m = abs(pair.get('price_change_5m', 0) or 0)
        
        # Linear scaling up to cap? Or buckets?
        # User didn't specify buckets, so I'll create reasonable ones or linear.
        # Let's use buckets similar to V2 but adapted.
        if p5m >= 50: score += p5m_cap
        elif p5m >= 20: score += p5m_cap * 0.8
        elif p5m >= 10: score += p5m_cap * 0.6
        elif p5m >= 5: score += p5m_cap * 0.4
        else: score += p5m_cap * 0.1 * (p5m/5.0) # Small partial credit
        
        # 2. Price Change 1h (0-20)
        p1h_cap = points_config.get('price_change_1h', 20)
        p1h = abs(pair.get('price_change_1h', 0) or 0)
        if p1h >= 100: score += p1h_cap
        elif p1h >= 50: score += p1h_cap * 0.8
        elif p1h >= 20: score += p1h_cap * 0.6
        elif p1h >= 15: score += p1h_cap * 0.4
        else: score += p1h_cap * 0.1
        
        # 3. Tx 5m (0-20)
        tx_cap = points_config.get('tx_5m', 20)
        tx = pair.get('tx_5m', 0)
        if tx >= 50: score += tx_cap
        elif tx >= 20: score += tx_cap * 0.8
        elif tx >= 10: score += tx_cap * 0.6
        elif tx >= 5: score += tx_cap * 0.4
        elif tx >= 1: score += tx_cap * 0.2
        
        # 4. Liquidity (0-10)
        liq_cap = points_config.get('liquidity', 10)
        liq = pair.get('liquidity', 0)
        if liq >= 50000: score += liq_cap
        elif liq >= 10000: score += liq_cap * 0.8
        elif liq >= 5000: score += liq_cap * 0.6
        elif liq >= 2000: score += liq_cap * 0.4
        elif liq >= 500: score += liq_cap * 0.2
        
        # 5. Volume 24h (0-10)
        vol_cap = points_config.get('volume_24h', 10)
        vol = pair.get('volume_24h', 0)
        if vol >= 100000: score += vol_cap
        elif vol >= 50000: score += vol_cap * 0.8
        elif vol >= 10000: score += vol_cap * 0.6
        elif vol >= 5000: score += vol_cap * 0.4
        elif vol >= 1000: score += vol_cap * 0.2
        
        # 6. Revival Bonus (+10)
        # If age > 30d AND momentum true (momentum already checked if we passed filters)
        revival_bonus = points_config.get('revival_bonus', 10)
        age = pair.get('age_days', 0)
        if age and age > 30:
            score += revival_bonus
            
        return min(100.0, score)

    def _log_drop(self, pair: Dict, reason: str):
        """Log pair drop with full context (MANDATORYDebugLogging)."""
        print(
            f"[MODE C DROP]\n"
            f"  pair={pair.get('pair_address', 'UNKNOWN')[:10]}...\n"
            f"  pc5m={pair.get('price_change_5m', 0):.2f}\n"
            f"  pc1h={pair.get('price_change_1h', 0):.2f}\n"
            f"  tx5m={pair.get('tx_5m', 0)}\n"
            f"  liquidity=${pair.get('liquidity', 0):,.0f}\n"
            f"  age_days={pair.get('age_days', 0):.2f}\n"
            f"  reason={reason}"
        )
    
    def get_stats(self) -> Dict:
        return self.stats
