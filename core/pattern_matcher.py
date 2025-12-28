"""
Pattern Matcher - Fuzzy Similarity Scoring

Compares new token metrics against historical patterns to predict outcomes.
"""
from typing import Dict, List, Tuple
from collections import Counter

class PatternMatcher:
    """
    Calculates similarity between a new token and historical patterns.
    """
    
    def __init__(self, memory_interface):
        self.memory = memory_interface
        
    def match_token(self, token_data: Dict, limit: int = 100) -> Dict:
        """
        Compare token against recent history.
        
        Args:
            token_data: Token metrics
            limit: History lookback size
            
        Returns:
            Dict with match stats and confidence
        """
        chain = token_data.get('chain', 'base')
        history = self.memory.get_recent_patterns(chain, limit)
        
        if not history:
            return {
                'pattern_similarity': 0,
                'matched_outcomes': {},
                'confidence_label': 'LOW_DATA'
            }
            
        matches = []
        
        # Normalize token data
        t_score = token_data.get('score', 0)
        t_liq = token_data.get('liquidity_usd', 0)
        t_conc = token_data.get('holder_risk', 50)  # Default mid-risk if missing
        t_mom = 1 if token_data.get('momentum_confirmed', False) else 0
        
        for pattern in history:
            similarity = self._calculate_similarity(
                t_score, t_liq, t_conc, t_mom,
                pattern
            )
            
            if similarity >= 60:  # Minimum similarity threshold
                matches.append({
                    'similarity': similarity,
                    'outcome': pattern['outcome']
                })
        
        # Aggregate outcomes
        if not matches:
            return {
                'pattern_similarity': 0,
                'matched_outcomes': {},
                'confidence_label': 'NO_MATCH'
            }
            
        # Weighted outcome calculation
        outcomes = Counter()
        total_sim = 0
        max_sim = 0
        
        for m in matches:
            # Higher similarity = more weight
            weight = (m['similarity'] / 100.0) ** 2
            outcomes[m['outcome']] += weight
            total_sim += weight
            max_sim = max(max_sim, m['similarity'])
            
        # Convert to percentages
        outcome_pct = {k: int((v / total_sim) * 100) for k, v in outcomes.items()}
        
        # Determine confidence
        confidence_label = 'LOW'
        if max_sim > 85 and len(matches) > 5:
            confidence_label = 'HIGH'
        elif max_sim > 70 and len(matches) > 2:
            confidence_label = 'MEDIUM'
            
        return {
            'pattern_similarity': int(max_sim),
            'matched_outcomes': outcome_pct,
            'confidence_label': confidence_label,
            'match_count': len(matches)
        }
        
    def _calculate_similarity(self, 
                            t_score: float, 
                            t_liq: float, 
                            t_conc: float, 
                            t_mom: int,
                            pattern: Dict) -> float:
        """
        Calculate fuzzy similarity score (0-100).
        """
        # Score difference (30% weight)
        p_score = pattern['initial_score']
        score_diff = abs(t_score - p_score)
        score_sim = max(0, 100 - (score_diff * 2))  # 50 pts diff = 0 sim
        
        # Liquidity log-scale difference (30% weight)
        p_liq = pattern['liquidity']
        # Avoid div by zero
        liq_ratio = min(t_liq, p_liq) / max(t_liq, p_liq, 1.0)
        liq_sim = liq_ratio * 100
        
        # Concentration difference (20% weight)
        p_conc = pattern['holder_concentration']
        conc_diff = abs(t_conc - p_conc)
        conc_sim = max(0, 100 - (conc_diff * 2))
        
        # Momentum exact match (20% weight)
        p_mom = pattern['momentum_confirmed']
        mom_sim = 100 if t_mom == p_mom else 0
        
        weighted_sim = (
            (score_sim * 0.30) +
            (liq_sim * 0.30) +
            (conc_sim * 0.20) +
            (mom_sim * 0.20)
        )
        
        return weighted_sim
