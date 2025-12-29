"""
DEDUPLICATOR

Prevents duplicate pair events from being processed multiple times.
Tracks seen pairs with cooldown period.

IMPROVED: Now supports momentum-based re-evaluation.
- Re-evaluates if volume_1h increased by >= threshold (default 5)
- Re-evaluates if price_change_1h increased by >= threshold (default 0.1%)
- Re-evaluates if tx_1h increased (any increase)

RPC SAVINGS: Avoids redundant on-chain verification for same pair unless momentum changed.
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
    - Configurable momentum re-evaluation
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize deduplicator.
        
        Args:
            config: Deduplication configuration dict
        """
        self.config = config or {}
        
        self.cooldown_seconds = self.config.get('base_cooldown_seconds', 
                                              self.config.get('cooldown_seconds', 600))
        
        # Bypass conditions
        self.bypass_config = self.config.get('bypass_conditions', {})
        
        # Track seen pairs with metrics: {chain: {pair_address: {timestamp, volume_1h, price_change_1h}}}
        self._seen: Dict[str, Dict[str, Dict]] = {}
        self._lock = threading.Lock()
        
        # Stats
        self.total_checked = 0
        self.duplicates_blocked = 0
        self.unique_passed = 0
        self.momentum_reeval = 0  # Count of momentum-triggered re-evaluations
    
    def is_duplicate(self, pair_address: str, chain: str = "base", 
                    volume_1h: float = None, price_change_1h: float = None, 
                    tx_1h: int = None) -> bool:
        """
        Check if pair was recently seen (with sensitive momentum-based re-evaluation).
        
        Re-evaluation triggers (Configurable):
        - volume_1h increased >= threshold (default 5)
        - tx_1h increased (any increase)
        - priceChange.h1 changed >= threshold (default 0.1%)
        
        Args:
            pair_address: Pair contract address
            chain: Chain identifier
            volume_1h: Current h1 volume (for momentum check)
            price_change_1h: Current h1 price change (for momentum check)
            tx_1h: Current h1 transaction count (for momentum check)
            
        Returns:
            True if duplicate (seen within cooldown AND no momentum increase), False if unique or momentum increased
        """
        with self._lock:
            self.total_checked += 1
            
            # Initialize chain dict if needed
            if chain not in self._seen:
                self._seen[chain] = {}
            
            chain_seen = self._seen[chain]
            
            # Check if seen
            if pair_address in chain_seen:
                pair_data = chain_seen[pair_address]
                last_seen = pair_data.get('timestamp')
                elapsed = (datetime.now() - last_seen).total_seconds()
                
                # Still in cooldown period
                if elapsed < self.cooldown_seconds:
                    # Check for momentum increase (allows re-evaluation)
                    prev_volume = pair_data.get('volume_1h', 0)
                    prev_price_change = pair_data.get('price_change_1h', 0)
                    prev_tx = pair_data.get('tx_1h', 0)
                    
                    # Calculate momentum changes
                    volume_increase = False
                    price_increase = False
                    tx_increase = False
                    
                    # Volume check (Absolute increase)
                    vol_threshold = self.bypass_config.get('volume_h1_increased', 5)
                    if volume_1h is not None and prev_volume is not None:
                        if volume_1h >= prev_volume + vol_threshold:
                            volume_increase = True
                    
                    # Price change delta check (Absolute delta)
                    price_threshold = self.bypass_config.get('abs_price_change_h1_delta', 0.1)
                    if price_change_1h is not None and prev_price_change is not None:
                        price_delta = abs(price_change_1h - prev_price_change)
                        if price_delta >= price_threshold:
                            price_increase = True
                    
                    # Transaction count check (Any increase)
                    if self.bypass_config.get('txns_h1_increased', True):
                        if tx_1h is not None and prev_tx is not None:
                            if tx_1h > prev_tx:
                                tx_increase = True
                    
                    # If momentum increased significantly, allow re-evaluation
                    if volume_increase or price_increase or tx_increase:
                        self.momentum_reeval += 1
                        # Update metrics but don't block
                        chain_seen[pair_address] = {
                            'timestamp': datetime.now(),
                            'volume_1h': volume_1h,
                            'price_change_1h': price_change_1h,
                            'tx_1h': tx_1h
                        }
                        self.unique_passed += 1
                        return False  # Allow re-evaluation
                    
                    # No momentum increase → block
                    self.duplicates_blocked += 1
                    return True
            
            # Not a duplicate (or cooldown expired) - mark as seen
            chain_seen[pair_address] = {
                'timestamp': datetime.now(),
                'volume_1h': volume_1h,
                'price_change_1h': price_change_1h,
                'tx_1h': tx_1h
            }
            self.unique_passed += 1
            return False
    
    def mark_seen(self, pair_address: str, chain: str = "base", 
                 volume_1h: float = None, price_change_1h: float = None,
                 tx_1h: int = None):
        """
        Manually mark pair as seen (with metrics).
        
        Args:
            pair_address: Pair contract address
            chain: Chain identifier
            volume_1h: Current h1 volume
            price_change_1h: Current h1 price change
            tx_1h: Current h1 transaction count
        """
        with self._lock:
            if chain not in self._seen:
                self._seen[chain] = {}
            
            self._seen[chain][pair_address] = {
                'timestamp': datetime.now(),
                'volume_1h': volume_1h,
                'price_change_1h': price_change_1h,
                'tx_1h': tx_1h
            }
    
    def cleanup_expired(self):
        """Remove expired entries beyond cooldown period."""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(seconds=self.cooldown_seconds)
            removed_count = 0
            
            for chain in self._seen:
                expired_pairs = [
                    addr for addr, data in self._seen[chain].items()
                    if data.get('timestamp', datetime.min) < cutoff_time
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
                'momentum_reeval': self.momentum_reeval,
                'dedup_rate_pct': dedup_rate,
                'currently_tracked': total_seen,
                'cooldown_seconds': self.cooldown_seconds,
                'chains': list(self._seen.keys()),
            }
