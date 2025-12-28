"""
Running Score Engine - Calculates running_score for post-launch tokens

COMPLETELY SEPARATE from TokenScorer and SniperScoreEngine.
This engine calculates a unique score for already-launched tokens
showing signs of secondary pump / rally.

Scoring formula:
- Base score contribution: base_score * 0.5 (max 45)
- Momentum confirmed: +15
- Volume spike (>2x avg): +10
- Liquidity growing: +10
- Holder risks: -5 each (max -20)
- Dev activity: -10

Cap score at 90.
"""
from typing import Dict
from .running_config import get_scoring_config, get_score_thresholds


class RunningScoreEngine:
    """
    Running Score Engine - calculates score for post-launch tokens.
    
    This is the SINGLE SOURCE OF TRUTH for running token scoring,
    separate from TokenScorer and SniperScoreEngine.
    """
    
    def __init__(self):
        self.scoring = get_scoring_config()
        self.thresholds = get_score_thresholds()
        self._max_score = self.scoring.get("max_score", 90)
    
    def calculate_running_score(self,
                                  base_score: int,
                                  momentum_data: Dict,
                                  volume_data: Dict,
                                  liquidity_data: Dict,
                                  holder_data: Dict) -> Dict:
        """
        Calculate the final running score.
        
        Args:
            base_score: Score from main TokenScorer (0-100)
            momentum_data: Dict with keys:
                - momentum_confirmed: bool
                - momentum_score: int
            volume_data: Dict with keys:
                - volume_24h: float
                - average_volume: float
                - volume_spike: bool (>2x average)
            liquidity_data: Dict with keys:
                - initial_liquidity: float
                - current_liquidity: float
                - liquidity_growing: bool
            holder_data: Dict with keys:
                - top10_percent: float
                - holder_risks: list[str]
                - dev_flag: str ('SAFE', 'WARNING', 'DUMP')
                
        Returns:
            Dict with:
            - running_score: int (0-90)
            - score_breakdown: dict of component scores
            - alert_level: str ('WATCH', 'POTENTIAL', 'TRADE', None)
            - meets_threshold: bool
        """
        breakdown = {}
        total_score = 0
        risk_flags = []
        
        # 1. Base Score Contribution (50% weight, max 45 points)
        base_weight = self.scoring.get("base_score_weight", 0.50)
        base_contribution = min(int(base_score * base_weight), 45)
        breakdown["base_score_contribution"] = base_contribution
        total_score += base_contribution
        
        # 2. Momentum Bonus (+15 if confirmed)
        momentum_confirmed = momentum_data.get("momentum_confirmed", False)
        momentum_bonus = self.scoring.get("momentum_bonus", 15)
        if momentum_confirmed:
            breakdown["momentum_bonus"] = momentum_bonus
            total_score += momentum_bonus
        else:
            breakdown["momentum_bonus"] = 0
            risk_flags.append("Momentum not confirmed")
        
        # 3. Volume Spike Bonus (+10 if >2x average)
        volume_spike = volume_data.get("volume_spike", False)
        volume_bonus = self.scoring.get("volume_spike_bonus", 10)
        
        # Calculate volume spike if not provided
        if not volume_spike:
            volume_24h = volume_data.get("volume_24h", 0)
            avg_volume = volume_data.get("average_volume", 0)
            if avg_volume > 0 and volume_24h > avg_volume * 2:
                volume_spike = True
        
        if volume_spike:
            breakdown["volume_spike_bonus"] = volume_bonus
            total_score += volume_bonus
        else:
            breakdown["volume_spike_bonus"] = 0
        
        # 4. Liquidity Growth Bonus (+10 if growing)
        liquidity_growing = liquidity_data.get("liquidity_growing", False)
        liq_bonus = self.scoring.get("liquidity_growth_bonus", 10)
        
        # Calculate growth if not provided
        if not liquidity_growing:
            initial_liq = liquidity_data.get("initial_liquidity", 0)
            current_liq = liquidity_data.get("current_liquidity", 0)
            if initial_liq > 0 and current_liq > initial_liq * 1.1:
                liquidity_growing = True
        
        if liquidity_growing:
            breakdown["liquidity_growth_bonus"] = liq_bonus
            total_score += liq_bonus
        else:
            breakdown["liquidity_growth_bonus"] = 0
        
        # 5. Holder Risk Penalties (-5 each, max -20)
        holder_risk_penalty = self.scoring.get("holder_risk_penalty", 5)
        holder_risks = holder_data.get("holder_risks", [])
        
        # Check top10 concentration
        top10 = holder_data.get("top10_percent", 0)
        if top10 > 50:
            holder_risks.append(f"High concentration ({top10:.0f}%)")
        
        total_holder_penalty = min(len(holder_risks) * holder_risk_penalty, 20)
        breakdown["holder_risk_penalty"] = -total_holder_penalty
        total_score -= total_holder_penalty
        risk_flags.extend(holder_risks)
        
        # 6. Dev Activity Penalty (-10 for WARNING/DUMP)
        dev_flag = holder_data.get("dev_flag", "SAFE")
        dev_penalty = self.scoring.get("dev_activity_penalty", 10)
        
        if dev_flag == "DUMP":
            breakdown["dev_activity_penalty"] = -dev_penalty
            total_score -= dev_penalty
            risk_flags.append("Dev DUMP detected")
        elif dev_flag == "WARNING":
            breakdown["dev_activity_penalty"] = -int(dev_penalty / 2)
            total_score -= int(dev_penalty / 2)
            risk_flags.append("Dev activity warning")
        else:
            breakdown["dev_activity_penalty"] = 0
        
        # Apply bounds
        running_score = max(0, min(total_score, self._max_score))
        
        # Determine alert level
        alert_level = self._classify_alert(running_score)
        
        return {
            "running_score": running_score,
            "score_breakdown": breakdown,
            "alert_level": alert_level,
            "meets_threshold": alert_level is not None,
            "max_possible": self._max_score,
            "risk_flags": risk_flags,
            "momentum_confirmed": momentum_confirmed,
            "volume_spike": volume_spike,
            "liquidity_growing": liquidity_growing
        }
    
    def _classify_alert(self, score: int) -> str:
        """Classify alert level based on running score."""
        trade_threshold = self.thresholds.get("TRADE", 80)
        potential_threshold = self.thresholds.get("POTENTIAL", 70)
        watch_threshold = self.thresholds.get("WATCH", 60)
        
        if score >= trade_threshold:
            return "TRADE"
        elif score >= potential_threshold:
            return "POTENTIAL"
        elif score >= watch_threshold:
            return "WATCH"
        return None
    
    def get_score_description(self, running_score: int) -> str:
        """Get human-readable description of running score."""
        if running_score >= 85:
            return "🟢 STRONG RALLY - High confidence signal"
        elif running_score >= 80:
            return "🟡 RALLY SIGNAL - Valid opportunity"
        elif running_score >= 70:
            return "🟠 POTENTIAL - Rally building"
        elif running_score >= 60:
            return "⚪ WATCH - Early signs"
        else:
            return "🔴 NO SIGNAL - Does not meet criteria"
