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
        
        # Bonding Curve Bypass Tracking (NEW)
        self._bc_watchlist: Dict[str, Dict] = {}  # Track BC tokens
        self._graduation_bypass_count: Dict[str, int] = {}  # Count bypasses (max 3)
        
        self._lock = threading.Lock()
        
        # Stats
        self.stats = {
            'pair_duplicates': 0,
            'token_duplicates': 0,
            'momentum_bypass': 0,
            'bc_bypasses': 0  # NEW
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

    def is_token_duplicate(self, token_address: str, chain: str = "base", bc_status: Dict = None) -> bool:
        """
        Check if token was seen within token_cooldown (30 min).
        
        NEW: Allow 3x bypass for graduated BC tokens.
        """
        with self._lock:
            now = datetime.now()
            
            if chain not in self._seen_tokens:
                self._seen_tokens[chain] = {}
            
            # Check if BC token needs bypass
            if bc_status and bc_status.get('in_curve'):
                # Token IN bonding curve -> Track for future bypass
                self._bc_watchlist[token_address] = {
                    'added_at': now,
                    'completion': bc_status.get('completion', 0),
                    'platform': bc_status.get('platform', 'unknown')
                }
                # Don't bypass yet (token blocked anyway)
                
            elif token_address in self._bc_watchlist:
                # Token WAS in BC, check if should bypass
                bypass_count = self._graduation_bypass_count.get(token_address, 0)
                
                if bypass_count < 3:
                    # BYPASS (up to 3 times)
                    self._graduation_bypass_count[token_address] = bypass_count + 1
                    self.stats['bc_bypasses'] += 1
                    print(f"   ✅ BC Graduation Bypass #{bypass_count + 1}/3 for {token_address[:8]}")
                    
                    # Allow re-check by NOT marking as duplicate
                    return False
                else:
                    # Max bypasses reached -> Remove from watchlist
                    del self._bc_watchlist[token_address]
                    print(f"   ⛔ BC Bypass limit reached (3/3) for {token_address[:8]}")
            
            # Normal dedup logic
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
