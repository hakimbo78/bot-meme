"""
DEDUPLICATOR

Prevents duplicate pair events from being processed multiple times.
Tracks seen pairs with cooldown period.

RPC SAVINGS: Avoids redundant on-chain verification for same pair.
"""

from typing import Dict, Set
from datetime import datetime, timedelta
import threading


class Deduplicator:
    """
    Tracks seen pairs to prevent duplicate processing.
    
    Features:
    - Cooldown-based deduplication
    - Separate tracking per chain
    - Thread-safe operations
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize deduplicator.
        
        Args:
            config: Deduplication configuration dict
        """
        self.config = config or {}
        
        self.cooldown_seconds = self.config.get('cooldown_seconds', 600)  # 10 minutes default
        
        # Track seen pairs: {chain: {pair_address: last_seen_time}}
        self._seen: Dict[str, Dict[str, datetime]] = {}
        self._lock = threading.Lock()
        
        # Stats
        self.total_checked = 0
        self.duplicates_blocked = 0
        self.unique_passed = 0
    
    def is_duplicate(self, pair_address: str, chain: str = "base") -> bool:
        """
        Check if pair was recently seen.
        
        Args:
            pair_address: Pair contract address
            chain: Chain identifier
            
        Returns:
            True if duplicate (seen within cooldown), False if unique
        """
        with self._lock:
            self.total_checked += 1
            
            # Initialize chain dict if needed
            if chain not in self._seen:
                self._seen[chain] = {}
            
            chain_seen = self._seen[chain]
            
            # Check if seen
            if pair_address in chain_seen:
                last_seen = chain_seen[pair_address]
                elapsed = (datetime.now() - last_seen).total_seconds()
                
                # Still in cooldown period
                if elapsed < self.cooldown_seconds:
                    self.duplicates_blocked += 1
                    return True
            
            # Not a duplicate - mark as seen
            chain_seen[pair_address] = datetime.now()
            self.unique_passed += 1
            return False
    
    def mark_seen(self, pair_address: str, chain: str = "base"):
        """
        Manually mark pair as seen.
        
        Args:
            pair_address: Pair contract address
            chain: Chain identifier
        """
        with self._lock:
            if chain not in self._seen:
                self._seen[chain] = {}
            
            self._seen[chain][pair_address] = datetime.now()
    
    def cleanup_expired(self):
        """Remove expired entries beyond cooldown period."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(seconds=self.cooldown_seconds)
            removed_count = 0
            
            for chain in self._seen:
                expired_pairs = [
                    addr for addr, last_seen in self._seen[chain].items()
                    if last_seen < cutoff_time
                ]
                
                for addr in expired_pairs:
                    del self._seen[chain][addr]
                    removed_count += 1
            
            return removed_count
    
    def clear(self):
        """Clear all tracked pairs."""
        with self._lock:
            self._seen.clear()
            self.total_checked = 0
            self.duplicates_blocked = 0
            self.unique_passed = 0
    
    def get_stats(self) -> Dict:
        """
        Get deduplication statistics.
        
        Returns:
            Dict with dedup stats
        """
        with self._lock:
            total_seen = sum(len(chain_dict) for chain_dict in self._seen.values())
            
            dedup_rate = 0
            if self.total_checked > 0:
                dedup_rate = (self.duplicates_blocked / self.total_checked) * 100
            
            return {
                'total_checked': self.total_checked,
                'duplicates_blocked': self.duplicates_blocked,
                'unique_passed': self.unique_passed,
                'dedup_rate_pct': dedup_rate,
                'currently_tracked': total_seen,
                'cooldown_seconds': self.cooldown_seconds,
                'chains': list(self._seen.keys()),
            }
