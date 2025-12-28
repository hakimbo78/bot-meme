"""
Rotation Engine - Cross-Chain Market Attention Tracker

Detects which chain is currently dominating market attention based on:
- Alert volume (weighted)
- Average scores
- Momentum confirmation rates
- Sniper hits

Outputs a 'Rotation Bias' that can be used to advise operators
or boost scores for the active chain.
"""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import  deque

@dataclass
class RotationConfig:
    window_minutes: int = 30
    min_confidence: float = 0.65
    apply_scoring_bias: bool = True
    max_bias_bonus: int = 5
    weights: Dict[str, float] = field(default_factory=lambda: {
        'SNIPER': 3.0,
        'TRADE': 2.0,
        'WATCH': 1.0,
        'INFO': 0.1
    })

class RotationEngine:
    """
    Tracks market rotation across chains using a rolling window of events.
    """
    
    def __init__(self, config: Dict = None):
        config_dict = config or {}
        self.config = RotationConfig(
            window_minutes=config_dict.get('window_minutes', 30),
            min_confidence=config_dict.get('min_confidence', 0.65),
            apply_scoring_bias=config_dict.get('apply_scoring_bias', True),
            max_bias_bonus=config_dict.get('max_bias_bonus', 5)
        )
        
        # Events storage: list of (timestamp, chain, type, score)
        self.events = deque()
        
        # Current state
        self.current_bias = None
        self.confidence = 0.0
        self.chain_scores = {}
        
    def add_event(self, chain: str, event_type: str, score: float):
        """
        Register a market event.
        
        Args:
            chain: Chain name (e.g., 'solana', 'base')
            event_type: 'SNIPER', 'TRADE', 'WATCH', 'INFO'
            score: Token score (0-100)
        """
        now = time.time()
        self.events.append((now, chain, event_type, score))
        self._cleanup()
        self._recalculate()
        
    def _cleanup(self):
        """Remove events older than window."""
        now = time.time()
        window_seconds = self.config.window_minutes * 60
        cutoff = now - window_seconds
        
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
            
    def _recalculate(self):
        """Recalculate rotation metrics."""
        if not self.events:
            self.current_bias = None
            self.confidence = 0.0
            self.chain_scores = {}
            return
            
        # Aggregate stats per chain
        stats = {}
        total_weight = 0
        
        for _, chain, event_type, score in self.events:
            if chain not in stats:
                stats[chain] = {'weight': 0, 'weighted_score': 0, 'count': 0}
            
            weight = self.config.weights.get(event_type, 0.1)
            
            # Boost weight for high scores
            score_multiplier = 1.0 + (score / 100.0)
            final_weight = weight * score_multiplier
            
            stats[chain]['weight'] += final_weight
            stats[chain]['weighted_score'] += (score * final_weight)
            stats[chain]['count'] += 1
            total_weight += final_weight
            
        if total_weight == 0:
            return
            
        # Determine dominance
        dominance_map = {}
        max_share = 0
        leader = None
        
        for chain, data in stats.items():
            share = data['weight'] / total_weight
            avg_score = data['weighted_score'] / data['weight'] if data['weight'] > 0 else 0
            
            dominance_map[chain] = {
                'share': share,
                'avg_score': avg_score,
                'events': data['count']
            }
            
            if share > max_share:
                max_share = share
                leader = chain
        
        self.chain_scores = dominance_map
        
        # Set bias if confidence threshold met
        if max_share >= self.config.min_confidence:
            self.current_bias = leader
            self.confidence = max_share
        else:
            self.current_bias = None  # No clear leader
            self.confidence = max_share
            
    def get_rotation_insight(self) -> Dict:
        """Get current rotation status."""
        return {
            'rotation_bias': self.current_bias,
            'confidence': self.confidence,
            'chain_stats': self.chain_scores,
            'is_confident': self.confidence >= self.config.min_confidence
        }
        
    def get_score_bonus(self, chain: str) -> int:
        """Get score bias bonus for a chain."""
        if not self.config.apply_scoring_bias:
            return 0
            
        if chain == self.current_bias and self.confidence >= self.config.min_confidence:
            return self.config.max_bias_bonus
            
        return 0
