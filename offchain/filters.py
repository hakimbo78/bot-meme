"""
MODE C V2: DEGEN SNIPER FILTERS

Hybrid off-chain–first filtering system.
Score-based gating: 
- Low (25-39), Mid (40-59), High (>=60).
- On-chain verify ONLY if >= 55.

Normalized Data Input:
{
  "chain": "...",
  "pair_address": "...",
  "token_address": "...",
  "liquidity": 0,
  "volume_24h": 0,
  "price_change_5m": 0,
  "price_change_1h": 0,
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
    MODE C V2: DEGEN SNIPER Filter & Scorer
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Extract configuration sections
        self.global_guardrails = self.config.get('global_guardrails', {})
        self.scoring_config = self.config.get('scoring_v2', {})
        self.tiers = self.config.get('telegram_tiers', {})
        
        # Stats
        self.stats = {
            'total_evaluated': 0,
            'guardrail_rejected': 0,
            'low_score_rejected': 0,
            'passed': 0,
            'scores': []
        }
    
    def apply_filters(self, pair: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Apply V2 filters and calculate score.
        
        Returns:
            (passed: bool, reason: str or None, metadata: dict or None)
        """
        self.stats['total_evaluated'] += 1
        
        # 1. Global Guardrails (Mandatory)
        passed_rails, rail_reason = self._check_global_guardrails(pair)
        if not passed_rails:
            self.stats['guardrail_rejected'] += 1
            return False, f"GUARDRAIL: {rail_reason}", None
            
        # 2. Calculate Score
        score = self._calculate_score_v2(pair)
        pair['offchain_score'] = score
        
        # 3. Check Minimum Score (Low Tier starts at 25)
        min_score = self.tiers.get('low', {}).get('min_score', 25)
        if score < min_score:
            self.stats['low_score_rejected'] += 1
            return False, f"Score too low ({score:.1f} < {min_score})", {'score': score}
            
        self.stats['passed'] += 1
        self.stats['scores'].append(score)
        
        # Determine Verdict
        verdict = "SKIP"
        # Default verify threshold if not in config
        verify_threshold = self.scoring_config.get('thresholds', {}).get('verify', 55)
        
        if score >= verify_threshold:
            verdict = "VERIFY"
        elif score >= 25:
             verdict = "ALERT_ONLY"
             
        metadata = {
            'score': score,
            'verdict': verdict,
            'verify_threshold': verify_threshold
        }
        
        return True, None, metadata

    def _check_global_guardrails(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """Check mandatory global guardrails."""
        # liquidity
        liq = pair.get('liquidity', 0)
        min_liq = self.global_guardrails.get('min_liquidity_usd', 5000)
        if liq < min_liq:
            return False, f"Liquidity too low (${liq} < ${min_liq})"
            
        # volume 24h
        vol24 = pair.get('volume_24h', 0)
        if self.global_guardrails.get('require_h24_volume', True) and vol24 <= 0:
            return False, "Zero 24h volume"
            
        # Age
        age_days = pair.get('age_days', 0)
        max_age = self.global_guardrails.get('max_age_hours', 24) / 24.0 # Convert hours to days
        # If age is None (unknown), we might pass or fail. Let's pass but be cautious.
        if age_days is not None and age_days > max_age:
             # Check if it has very high volume to justify
             if vol24 < 50000: # Arbitrary old-pair threshold
                 return False, f"Old pair ({age_days:.1f}d) with low volume"
                 
        return True, None

    def _calculate_score_v2(self, pair: Dict) -> float:
        """
        Calculate 0-100 score based on normalized V2 metrics.
        """
        weights = self.scoring_config.get('weights', {})
        
        liq = pair.get('liquidity', 0)
        vol = pair.get('volume_24h', 0)
        tx = pair.get('tx_24h', 0)
        price_1h = pair.get('price_change_1h', 0)
        
        score = 0.0
        
        # Liquidity (30%)
        # Target: 5k = 5pts, 100k = 30pts
        w_liq = weights.get('liquidity', 0.30) * 100
        if liq >= 100000: score += w_liq
        elif liq >= 50000: score += w_liq * 0.8
        elif liq >= 20000: score += w_liq * 0.6
        elif liq >= 10000: score += w_liq * 0.4
        elif liq >= 5000:  score += w_liq * 0.2
        
        # Volume (30%)
        # Target: 2k = 5pts, 100k = 30pts
        w_vol = weights.get('volume', 0.30) * 100
        if vol >= 100000: score += w_vol
        elif vol >= 50000: score += w_vol * 0.8
        elif vol >= 20000: score += w_vol * 0.6
        elif vol >= 10000: score += w_vol * 0.4
        elif vol >= 2000:  score += w_vol * 0.2
        
        # Price Change 1h (20%)
        # Target: 5% = 5pts, 100% = 20pts
        w_price = weights.get('price_change', 0.20) * 100
        abs_p = abs(price_1h)
        if abs_p >= 100: score += w_price
        elif abs_p >= 50: score += w_price * 0.8
        elif abs_p >= 20: score += w_price * 0.6
        elif abs_p >= 10: score += w_price * 0.4
        elif abs_p >= 5:  score += w_price * 0.2
        
        # Tx Count 24h (20%)
        # Target: 50 = 5pts, 500 = 20pts
        w_tx = weights.get('tx_count', 0.20) * 100
        if tx >= 500: score += w_tx
        elif tx >= 200: score += w_tx * 0.8
        elif tx >= 100: score += w_tx * 0.6
        elif tx >= 50:  score += w_tx * 0.4
        elif tx >= 20:  score += w_tx * 0.2
        
        # Cap at 100
        return min(100.0, score)

    def get_stats(self) -> Dict:
        return self.stats
