"""
Narrative Detection Engine

Detects market narratives based on token metadata keywords.
Tracks keyword frequency over time to determine trend direction.
"""
import re
import time
from collections import Counter, deque
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class NarrativeConfig:
    min_confidence: float = 0.7
    max_active_narratives: int = 10
    window_hours: int = 24
    
class NarrativeEngine:
    def __init__(self, config: Dict = None):
        config_dict = config or {}
        self.config = NarrativeConfig(
            min_confidence=config_dict.get('min_confidence', 0.7),
            max_active_narratives=config_dict.get('max_active_narratives', 10)
        )
        
        # Keyword mapping to narratives
        self.keywords = {
            'AI_AGENT': ['AI', 'GPT', 'LLM', 'AGENT', 'NEURAL', 'BRAIN', 'BOT', 'MACHINE'],
            'INFRA_SOL': ['SOL', 'SPEED', 'PIPELINE', 'VALIDATOR', 'NODE', 'RPC'],
            'TELEGRAM_BOT': ['TELEGRAM', 'BOT', 'SNIPER', 'TRACKER', 'ALERT'],
            'RWA': ['REAL', 'ESTATE', 'ASSET', 'GOLD', 'TOKENIZED'],
            'DOGE_META': ['DOGE', 'SHIB', 'FLOKI', 'ELON', 'DOG'],
            'PEPE_META': ['PEPE', 'FROG', 'MEME', 'KEK'],
            'CATS_META': ['CAT', 'KITTY', 'MEOW', 'FELINE']
        }
        
        # History tracks: {narrative: deque([(timestamp, 1)])}
        self.history = {k: deque() for k in self.keywords}
        self.active_narratives = {}

    def analyze_token(self, token_data: Dict) -> Dict:
        """
        Analyze token metadata to detect narratives.
        """
        text = (
            token_data.get('name', '') + " " + 
            token_data.get('symbol', '')
        ).upper()
        
        detected = []
        
        for narrative, keywords in self.keywords.items():
            matches = [k for k in keywords if k in text]
            if matches:
                self._record_hit(narrative)
                detected.append(narrative)
                
        # Get active narrative status
        primary_narrative = None
        highest_conf = 0
        
        for narr in detected:
            stats = self.get_narrative_stats(narr)
            if stats['confidence'] > highest_conf:
                highest_conf = stats['confidence']
                primary_narrative = narr
                
        return {
            'narrative': primary_narrative,
            'confidence': highest_conf,
            'trend': self.get_narrative_stats(primary_narrative)['trend'] if primary_narrative else 'NONE',
            'all_detected': detected
        }
    
    def _record_hit(self, narrative: str):
        """Record a narrative hit."""
        now = time.time()
        self.history[narrative].append((now, 1))
        self._cleanup(narrative)
        
    def _cleanup(self, narrative: str):
        """Remove old hits."""
        now = time.time()
        cutoff = now - (self.config.window_hours * 3600)
        while self.history[narrative] and self.history[narrative][0][0] < cutoff:
            self.history[narrative].popleft()
            
    def get_narrative_stats(self, narrative: str) -> Dict:
        """Get stats for a specific narrative."""
        if not narrative or narrative not in self.history:
            return {'confidence': 0, 'trend': 'NONE', 'count': 0}
            
        hits = len(self.history[narrative])
        
        # Simple heuristic: >5 hits in 24h = rising
        # Logic can be improved with time-decay weights
        
        confidence = min(1.0, hits / 5.0)  # 5 hits = 100% confidence
        
        trend = 'STABLE'
        if hits >= 5: 
            trend = 'RISING'
        elif hits >= 2:
            trend = 'STABLE'
        else:
            trend = 'FADING'
            
        return {
            'confidence': confidence,
            'trend': trend,
            'count': hits
        }
        
    def get_active_narratives(self) -> List[Dict]:
        """Get all currently active narratives."""
        active = []
        for narr in self.keywords:
            stats = self.get_narrative_stats(narr)
            if stats['confidence'] >= 0.4:  # Show loosely active ones too
                active.append({
                    'name': narr,
                    'stats': stats
                })
        
        return sorted(active, key=lambda x: x['stats']['confidence'], reverse=True)
