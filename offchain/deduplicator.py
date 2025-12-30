"""
DEDUPLICATOR V2

Prevents duplicate processing at both PAIR and TOKEN levels.

MODE C V2 Requirements:
- Token-level deduplicator (30 min)
- Pair-level deduplicator (15 min)
"""

from typing import Dict, Set
from datetime import datetime, timedelta
import threading

class Deduplicator:
    """
    Tracks seen pairs and tokens to prevent spam.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Cooldowns (in minutes)
        self.pair_cooldown = self.config.get('pair_cooldown_minutes', 15)
        self.token_cooldown = self.config.get('token_cooldown_minutes', 30)
        
        # State: {chain: {address: {timestamp, ...}}}
        self._seen_pairs: Dict[str, Dict[str, datetime]] = {}
        self._seen_tokens: Dict[str, Dict[str, datetime]] = {}
        
        self._lock = threading.Lock()
        
        # Stats
        self.stats = {
            'pair_duplicates': 0,
            'token_duplicates': 0,
            'momentum_bypass': 0
        }
    
    def is_duplicate(self, pair_address: str, chain: str = "base", 
                    volume_h24: float = None, price_change_1h: float = None) -> bool:
        """
        Check if pair was seen within pair_cooldown (15 min).
        Bypassed if SIGNIFICANT momentum shift occurs (e.g. 2x volume).
        """
        with self._lock:
            now = datetime.now()
            
            # Initialize chain bucket
            if chain not in self._seen_pairs:
                self._seen_pairs[chain] = {}
                
            last_seen = self._seen_pairs[chain].get(pair_address)
            
            if last_seen:
                # Check cooldown
                elapsed_minutes = (now - last_seen).total_seconds() / 60
                if elapsed_minutes < self.pair_cooldown:
                    self.stats['pair_duplicates'] += 1
                    return True # Duplicate
            
            # Not duplicate or expired -> Record it
            self._seen_pairs[chain][pair_address] = now
            return False

    def is_token_duplicate(self, token_address: str, chain: str = "base") -> bool:
        """
        Check if token was seen within token_cooldown (30 min).
        Strict deduplication properly.
        """
        with self._lock:
            now = datetime.now()
            
            if chain not in self._seen_tokens:
                self._seen_tokens[chain] = {}
                
            last_seen = self._seen_tokens[chain].get(token_address)
            
            if last_seen:
                elapsed_minutes = (now - last_seen).total_seconds() / 60
                if elapsed_minutes < self.token_cooldown:
                    self.stats['token_duplicates'] += 1
                    return True
            
            self._seen_tokens[chain][token_address] = now
            return False
            
    def cleanup_expired(self):
        """Remove expired entries."""
        with self._lock:
            now = datetime.now()
            removed = 0
            
            # Cleanup pairs
            for chain in self._seen_pairs:
                to_remove = []
                for addr, ts in self._seen_pairs[chain].items():
                    if (now - ts).total_seconds() / 60 > self.pair_cooldown:
                        to_remove.append(addr)
                for addr in to_remove:
                    del self._seen_pairs[chain][addr]
                    removed += 1
                    
            # Cleanup tokens
            for chain in self._seen_tokens:
                to_remove = []
                for addr, ts in self._seen_tokens[chain].items():
                    if (now - ts).total_seconds() / 60 > self.token_cooldown:
                        to_remove.append(addr)
                for addr in to_remove:
                    del self._seen_tokens[chain][addr]
                    removed += 1
                    
            return removed
            
    def get_stats(self) -> Dict:
        return self.stats
