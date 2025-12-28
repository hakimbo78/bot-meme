"""
Sniper Score Engine - Calculates final sniper_score for early token alerts

COMPLETELY SEPARATE from TokenScorer and original SniperScorer.
This engine takes data from multiple sources and calculates a unified sniper score.

Inputs:
- base_score: int (from main TokenScorer)
- momentum_data: dict (from MomentumTracker)
- liquidity_trend: dict (current vs initial liquidity)
- holder_risk: dict (concentration, dev activity)

Output:
- sniper_score: int (capped at 90, minimum threshold 80)

Scoring formula:
- Base contribution: min(base_score * 0.5, 40)
- Momentum bonus: +15 if confirmed, -10 if not
- Liquidity trend: +10 if growing, +5 if stable, -15 if declining
- Holder risk: -5 per risk flag (max -20)
"""
from typing import Dict
from .sniper_config import get_sniper_config


class SniperScoreEngine:
    """
    Sniper Score Engine - calculates final sniper_score.
    
    This is the SINGLE SOURCE OF TRUTH for sniper scoring,
    separate from the main TokenScorer.
    """
    
    def __init__(self):
        self.config = get_sniper_config()
        self._max_score = self.config.get('sniper_score_max', 90)
        self._min_threshold = self.config.get('sniper_score_min_threshold', 80)
    
    def calculate_sniper_score(self, 
                                base_score: int,
                                momentum_data: Dict,
                                liquidity_trend: Dict,
                                holder_risk: Dict) -> Dict:
        """
        Calculate the final sniper score.
        
        Args:
            base_score: Score from main TokenScorer (0-100)
            momentum_data: Dict with keys:
                - momentum_confirmed: bool
                - momentum_score: int
                - momentum_details: dict
            liquidity_trend: Dict with keys:
                - initial_liquidity: float
                - current_liquidity: float
                - trend: 'growing' | 'stable' | 'declining'
            holder_risk: Dict with keys:
                - top10_percent: float
                - dev_flag: str ('SAFE', 'WARNING', 'DUMP')
                - mev_detected: bool
                - fake_pump: bool
                
        Returns:
            Dict with:
            - sniper_score: int (0-90)
            - score_breakdown: dict of component scores
            - meets_threshold: bool
            - risk_level: str
        """
        breakdown = {}
        total_score = 0
        
        # 1. Base Score Contribution (max 40 points)
        base_contribution = min(int(base_score * 0.5), 40)
        breakdown['base_score_contribution'] = base_contribution
        total_score += base_contribution
        
        # 2. Momentum Bonus (max +15, penalty -10)
        momentum_confirmed = momentum_data.get('momentum_confirmed', False)
        if momentum_confirmed:
            momentum_bonus = 15
        else:
            momentum_bonus = -10
        breakdown['momentum_bonus'] = momentum_bonus
        total_score += momentum_bonus
        
        # 3. Liquidity Trend (max +10, penalty -15)
        trend = liquidity_trend.get('trend', 'unknown')
        initial_liq = liquidity_trend.get('initial_liquidity', 0)
        current_liq = liquidity_trend.get('current_liquidity', 0)
        
        if trend == 'growing' or (initial_liq > 0 and current_liq > initial_liq * 1.1):
            liquidity_bonus = 10
        elif trend == 'stable' or (initial_liq > 0 and current_liq >= initial_liq * 0.9):
            liquidity_bonus = 5
        else:  # declining
            liquidity_bonus = -15
        breakdown['liquidity_trend_bonus'] = liquidity_bonus
        total_score += liquidity_bonus
        
        # 4. Holder Risk Penalties (max -20)
        risk_penalty = 0
        risk_flags = []
        
        # High concentration penalty
        top10 = holder_risk.get('top10_percent', 0)
        if top10 > 50:
            risk_penalty -= 5
            risk_flags.append(f'High concentration ({top10:.0f}%)')
        
        # Dev flag penalty
        dev_flag = holder_risk.get('dev_flag', 'SAFE')
        if dev_flag == 'DUMP':
            risk_penalty -= 10
            risk_flags.append('Dev DUMP flag')
        elif dev_flag == 'WARNING':
            risk_penalty -= 5
            risk_flags.append('Dev WARNING flag')
        
        # MEV penalty
        if holder_risk.get('mev_detected', False):
            risk_penalty -= 5
            risk_flags.append('MEV detected')
        
        # Fake pump penalty
        if holder_risk.get('fake_pump', False):
            risk_penalty -= 5
            risk_flags.append('Fake pump suspected')
        
        # Cap penalty at -20
        risk_penalty = max(risk_penalty, -20)
        breakdown['holder_risk_penalty'] = risk_penalty
        total_score += risk_penalty
        
        # 5. Apply bounds
        # Floor at 0, cap at max_score
        sniper_score = max(0, min(total_score, self._max_score))
        
        # 6. Determine risk level
        if sniper_score >= 85:
            risk_level = 'OPTIMAL'
        elif sniper_score >= self._min_threshold:
            risk_level = 'ACCEPTABLE'
        elif sniper_score >= 70:
            risk_level = 'ELEVATED'
        else:
            risk_level = 'HIGH'
        
        return {
            'sniper_score': sniper_score,
            'score_breakdown': breakdown,
            'meets_threshold': sniper_score >= self._min_threshold,
            'threshold': self._min_threshold,
            'max_possible': self._max_score,
            'risk_level': risk_level,
            'risk_flags': risk_flags
        }
    
    def get_operator_protocol(self) -> Dict:
        """
        Get the standard operator protocol for sniper alerts.
        
        Returns recommended entry size, take-profit levels, and exit rules.
        """
        return {
            'entry_size': '0.1-0.5% portfolio max',
            'tp1': '+50% (sell 50% position)',
            'tp2': '+100% (sell 25% position)',
            'tp3': '+200% (sell remaining or trail stop)',
            'stop_loss': '-20% or kill switch trigger',
            'exit_rules': [
                'Exit immediately if kill switch triggers',
                'Exit if liquidity drops 15%+ from alert time',
                'Exit if momentum reverses',
                'Never hold longer than 30 minutes'
            ]
        }
    
    def get_score_description(self, sniper_score: int) -> str:
        """Get human-readable description of sniper score."""
        if sniper_score >= 85:
            return "🟢 OPTIMAL - Strong sniper opportunity"
        elif sniper_score >= 80:
            return "🟡 ACCEPTABLE - Valid sniper, elevated risk"
        elif sniper_score >= 70:
            return "🟠 MARGINAL - Below threshold, consider TRADE instead"
        else:
            return "🔴 REJECT - Does not meet sniper criteria"
