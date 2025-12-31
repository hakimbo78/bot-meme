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
        LEVEL-0 FILTER (HARD KILL) - TIGHTENED FOR HYBRID OPTION C
        
        DROP if:
        1. ZOMBIE: age > 30d AND no activity
        2. LOW LIQUIDITY: < $2,000 (HYBRID)
        3. LOW VOLUME: < $1,000 in 24h (HYBRID)
        
        This ensures only quality pairs pass.
        """
        # Check liquidity (HYBRID requirement)
        liquidity = pair.get('liquidity', 0)
        min_liq = self.global_guardrails.get('min_liquidity_usd', 2000)
        if liquidity < min_liq:
            return False, f"LOW_LIQUIDITY (${liquidity:,.0f} < ${min_liq:,.0f})"
        
        # Check volume (HYBRID requirement)
        volume_24h = pair.get('volume_24h', 0)
        min_vol = self.global_guardrails.get('min_volume_24h', 1000)
        require_volume = self.global_guardrails.get('require_h24_volume', True)
        
        if require_volume and volume_24h < min_vol:
            return False, f"LOW_VOLUME (${volume_24h:,.0f} < ${min_vol:,.0f})"
        
        # Check for zombies (old logic)
        age_days = pair.get('age_days', 0)
        if age_days is None:
            age_days = 0.0
            
        price_change_5m = pair.get('price_change_5m', 0) or 0
        price_change_1h = pair.get('price_change_1h', 0) or 0
        tx_5m = pair.get('tx_5m', 0)
        
        # Only drop total zombies: old + completely inactive
        is_zombie = (
            age_days > 30
            and price_change_5m == 0
            and price_change_1h == 0
            and tx_5m == 0
        )
        
        if is_zombie:
            return False, f"ZOMBIE (age={age_days:.1f}d, no activity)"
            
        # Check Quality Guardrails (Enhanced Filters)
        quality_check = self.global_guardrails.get('quality_check', {})
        
        # 1. Socials Check
        if quality_check.get('socials_check', False):
            # Only drop if we are SURE there are no socials (has_socials is explicitly False)
            if pair.get('has_socials') is False:
                return False, "NO_SOCIALS (Requirement: Telegram/X/Web)"
        
        # 2. Minimum Unique Buyers Proxy (Tx Buys 5m)
        min_buyers = quality_check.get('min_unique_buyers_5m', 0)
        buys_5m = pair.get('buys_5m', 0)
        if min_buyers > 0 and buys_5m < min_buyers:
            return False, f"LOW_BUYERS (buys={buys_5m} < {min_buyers})"
            
        return True, None
        
    def _check_level1_and_revival(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        LEVEL-1 FILTER (IGNITION CHECK)
        
        PASS if ANY activity signal is present:
        - price_change_5m > 0
        - OR price_change_1h > 0
        - OR tx_5m >= 1
        
        DROP ONLY if all metrics are zero/inactive.
        No percentage thresholds. No revival rules.
        MODE C allows extremely early signals.
        """
        price_change_5m = pair.get('price_change_5m', 0) or 0
        price_change_1h = pair.get('price_change_1h', 0) or 0
        tx_5m = pair.get('tx_5m', 0)
        
        # Pass if ANY ignition signal detected
        has_ignition = (
            price_change_5m > 0
            or price_change_1h > 0
            or tx_5m >= 1
        )
        
        if not has_ignition:
            return False, "No ignition (pc5m=0, pc1h=0, tx5m=0)"
            
        return True, None

    def _calculate_score_v3(self, pair: Dict) -> float:
        """
        Calculate 0-100 score based on V3 components.
        TIGHTENED BUCKETS (HYBRID OPTION C) - Only quality coins get points!
        """
        points_config = self.scoring_config.get('points', {})
        
        score = 0.0
        
        # 1. Price Change 5m (0-30) - TIGHTENED
        p5m_cap = points_config.get('price_change_5m', 30)
        p5m = abs(pair.get('price_change_5m', 0) or 0)
        
        if p5m >= 50: score += p5m_cap           # 50%+ → 30 pts
        elif p5m >= 20: score += p5m_cap * 0.8   # 20%+ → 24 pts
        elif p5m >= 10: score += p5m_cap * 0.6   # 10%+ → 18 pts
        elif p5m >= 5: score += p5m_cap * 0.3    # 5%+ → 9 pts (was 0.4)
        else: score += 0                         # < 5% → 0 pts (was partial)
        
        # 2. Price Change 1h (0-20) - TIGHTENED
        p1h_cap = points_config.get('price_change_1h', 20)
        p1h = abs(pair.get('price_change_1h', 0) or 0)
        if p1h >= 100: score += p1h_cap          # 100%+ → 20 pts
        elif p1h >= 50: score += p1h_cap * 0.8   # 50%+ → 16 pts
        elif p1h >= 20: score += p1h_cap * 0.6   # 20%+ → 12 pts
        elif p1h >= 10: score += p1h_cap * 0.3   # 10%+ → 6 pts (was 0.4)
        else: score += 0                         # < 10% → 0 pts (was 0.1)
        
        # 3. Tx 5m (0-20) - TIGHTENED
        tx_cap = points_config.get('tx_5m', 20)
        tx = pair.get('tx_5m', 0)
        if tx >= 50: score += tx_cap             # 50+ tx → 20 pts
        elif tx >= 20: score += tx_cap * 0.8     # 20+ tx → 16 pts
        elif tx >= 10: score += tx_cap * 0.6     # 10+ tx → 12 pts
        elif tx >= 5: score += tx_cap * 0.4      # 5+ tx → 8 pts
        else: score += 0                         # < 5 tx → 0 pts (was 0.2)
        
        # 4. Liquidity (0-10) - TIGHTENED
        liq_cap = points_config.get('liquidity', 10)
        liq = pair.get('liquidity', 0)
        if liq >= 100000: score += liq_cap       # $100K+ → 10 pts
        elif liq >= 50000: score += liq_cap * 0.8  # $50K+ → 8 pts
        elif liq >= 20000: score += liq_cap * 0.6  # $20K+ → 6 pts
        elif liq >= 10000: score += liq_cap * 0.4  # $10K+ → 4 pts
        elif liq >= 5000: score += liq_cap * 0.2   # $5K+ → 2 pts
        else: score += 0                         # < $5K → 0 pts (was 0.2)
        
        # 5. Volume 24h (0-10) - TIGHTENED
        vol_cap = points_config.get('volume_24h', 10)
        vol = pair.get('volume_24h', 0)
        if vol >= 100000: score += vol_cap       # $100K+ → 10 pts
        elif vol >= 50000: score += vol_cap * 0.8  # $50K+ → 8 pts
        elif vol >= 20000: score += vol_cap * 0.6  # $20K+ → 6 pts
        elif vol >= 10000: score += vol_cap * 0.4  # $10K+ → 4 pts
        elif vol >= 5000: score += vol_cap * 0.2   # $5K+ → 2 pts
        else: score += 0                         # < $5K → 0 pts (was 0.2)
        
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
