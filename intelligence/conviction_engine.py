"""
Conviction Engine

Fuses intelligence signals into a final Conviction Score.
Inputs:
- Narrative Strength (0-1.0) -> Scaled to 25 pts
- Smart Money Count -> Scaled to 35 pts
- Rotation Bias -> Scaled to 20 pts
- Pattern Similarity -> Scaled to 20 pts

Total: 100 points
"""
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class ConvictionConfig:
    min_display_score: int = 60
    weights: Dict[str, float] = field(default_factory=lambda: {
        'narrative': 25.0,
        'smart_money': 35.0,
        'rotation': 20.0,
        'pattern': 20.0
    })

class ConvictionEngine:
    def __init__(self, config: Dict = None):
        config_dict = config or {}
        self.config = ConvictionConfig(
            min_display_score=config_dict.get('min_display_score', 60)
        )
        
    def calculate_conviction(self, 
                           narrative_data: Dict,
                           smart_money_data: Dict,
                           rotation_data: Dict,
                           pattern_data: Dict) -> Dict:
        """
        Calculate final conviction score.
        """
        score = 0
        details = []
        
        # 1. Narrative Score (0-25)
        n_conf = narrative_data.get('confidence', 0)
        n_trend = narrative_data.get('trend', 'NONE')
        n_score = n_conf * self.config.weights['narrative']
        if n_trend == 'RISING':
            n_score = min(self.config.weights['narrative'], n_score * 1.2) # Boost rising
        score += n_score
        if n_score > 5:
            details.append(f"Narrative {narrative_data.get('narrative')} ({n_trend})")
            
        # 2. Smart Money Score (0-35)
        # Heuristic: 1 Tier-1 = 15pts, Tier-2 = 5pts
        t1 = smart_money_data.get('tier1_wallets', 0)
        t2 = smart_money_data.get('tier2_wallets', 0)
        sm_raw = (t1 * 15) + (t2 * 5)
        sm_score = min(self.config.weights['smart_money'], sm_raw)
        score += sm_score
        if sm_score > 0:
            details.append(f"Smart Money: {t1} T1 / {t2} T2")
            
        # 3. Rotation Score (0-20)
        r_conf = rotation_data.get('confidence', 0)
        r_bias = rotation_data.get('rotation_bias')
        # We only score if the token's chain matches the rotation bias
        # This requires the caller to check chain alignment before passing rotation_data
        # Assuming rotation_data passed here means "aligned" or has a flag
        if rotation_data.get('is_aligned', False):
            r_score = r_conf * self.config.weights['rotation']
            score += r_score
            details.append(f"Rotation Aligned ({int(r_conf*100)}%)")
        else:
            r_score = 0
            
        # 4. Pattern Score (0-20)
        p_sim = pattern_data.get('pattern_similarity', 0) / 100.0
        p_score = p_sim * self.config.weights['pattern']
        score += p_score
        if p_score > 5:
            details.append(f"Pattern Match {int(p_sim*100)}%")
            
        final_score = int(min(100, score))
        
        # Interpret verdict
        verdict = "NOISE"
        if final_score >= 90: verdict = "RARE ASYMMETRIC"
        elif final_score >= 75: verdict = "STRONG CONVICTION"
        elif final_score >= 60: verdict = "WATCH CLOSELY"
        
        return {
            'conviction_score': final_score,
            'verdict': verdict,
            'reasoning': details,
            'breakdown': {
                'narrative': n_score,
                'smart_money': sm_score,
                'rotation': r_score,
                'pattern': p_score
            }
        }
