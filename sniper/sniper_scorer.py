"""
Sniper Scorer - Independent scoring for early-stage tokens

COMPLETELY SEPARATE from main scorer.py
Does NOT use momentum confirmation or phase detection.

Scoring components (0-100 total):
+25  Buy frequency (>= min_buys_30s)
+20  Liquidity growth speed
+15  Unique wallet count
+20  Price velocity (short-term)
-10  Gas spike detected (WARNING ONLY)
-5   High holder concentration (NON-FATAL)

No score cap applied.
"""
from typing import Dict
from .sniper_config import get_sniper_config


class SniperScorer:
    """
    Independent scorer for sniper mode.
    
    This scorer is completely separate from the main TokenScorer.
    It does NOT require momentum confirmation.
    """
    
    def __init__(self):
        self.config = get_sniper_config()
    
    def score_token(self, token_data: Dict, activity_data: Dict) -> Dict:
        """
        Score token for sniper alert eligibility.
        
        Args:
            token_data: Token analysis data
            activity_data: Activity analysis from sniper_detector
            
        Returns:
            Dict with:
            - sniper_score: int (0-100+)
            - score_breakdown: dict of component scores
            - risk_warnings: list of warnings
            - meets_threshold: bool
        """
        score = 0
        breakdown = {}
        warnings = []
        
        min_buys = self.config.get('min_buys_30s', 5)
        min_wallets = self.config.get('min_unique_wallets', 3)
        threshold = self.config.get('sniper_score_threshold', 60)
        
        # 1. Buy Frequency Score (+25 max)
        buys_30s = activity_data.get('buys_30s', 0)
        if buys_30s >= min_buys:
            buy_score = 25
        elif buys_30s >= min_buys // 2:
            buy_score = 15
        elif buys_30s > 0:
            buy_score = 10
        else:
            buy_score = 0
        
        breakdown['buy_frequency'] = buy_score
        score += buy_score
        
        # 2. Liquidity Score (+20 max)
        liquidity = token_data.get('liquidity_usd', 0)
        min_liq = self.config.get('min_liquidity_usd', 2000)
        
        if liquidity >= min_liq * 5:  # 5x minimum = strong liquidity
            liq_score = 20
        elif liquidity >= min_liq * 2:  # 2x minimum
            liq_score = 15
        elif liquidity >= min_liq:
            liq_score = 10
        else:
            liq_score = 5
        
        breakdown['liquidity'] = liq_score
        score += liq_score
        
        # 3. Unique Wallets Score (+15 max)
        unique_wallets = activity_data.get('unique_wallets', 0)
        if unique_wallets >= min_wallets * 2:  # 2x minimum
            wallet_score = 15
        elif unique_wallets >= min_wallets:
            wallet_score = 10
        elif unique_wallets > 0:
            wallet_score = 5
        else:
            wallet_score = 0
        
        breakdown['unique_wallets'] = wallet_score
        score += wallet_score
        
        # 4. Price Velocity Score (+20 max)
        # Estimate based on buy pressure and activity
        if buys_30s >= min_buys and unique_wallets >= min_wallets:
            velocity_score = 20
        elif buys_30s >= min_buys or unique_wallets >= min_wallets:
            velocity_score = 10
        else:
            velocity_score = 5
        
        breakdown['price_velocity'] = velocity_score
        score += velocity_score
        
        # 5. Token Age Bonus (+10 max)
        age = token_data.get('age_minutes', 999)
        max_age = self.config.get('max_age_minutes', 3)
        if age <= 1:
            age_score = 10  # Very fresh
        elif age <= 2:
            age_score = 5
        else:
            age_score = 0
        
        breakdown['token_age'] = age_score
        score += age_score
        
        # PENALTIES
        
        # 6. Gas Spike Penalty (-10, WARNING ONLY)
        if activity_data.get('gas_spike_detected', False):
            score -= 10
            breakdown['gas_spike_penalty'] = -10
            warnings.append('Gas spike detected - possible MEV')
        
        # 7. Holder Concentration Penalty (-5, NON-FATAL)
        top10 = token_data.get('top10_holders_percent', 0)
        if top10 > 80:
            score -= 5
            breakdown['holder_concentration_penalty'] = -5
            warnings.append(f'High holder concentration ({top10:.0f}%)')
        
        # Ensure score doesn't go below 0
        score = max(0, score)
        
        # Add mandatory warnings (always present for sniper alerts)
        warnings.extend([
            'Momentum NOT confirmed',
            'Dev wallet NOT verified',
            'MEV / fake pump possible'
        ])
        
        return {
            'sniper_score': score,
            'score_breakdown': breakdown,
            'risk_warnings': warnings,
            'meets_threshold': score >= threshold,
            'threshold': threshold
        }
    
    def get_action_guidance(self) -> list:
        """
        Get action guidance text for sniper alerts.
        
        Returns:
            List of guidance strings
        """
        return [
            'Manual scalp only',
            'Small position',
            'Fast exit',
            'High risk'
        ]
