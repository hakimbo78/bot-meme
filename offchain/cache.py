"""
OFF-CHAIN CACHE

In-memory cache for off-chain data to avoid redundant API calls.
Implements TTL-based expiration and size limits.

RPC SAVINGS: Caching prevents re-fetching same pair data multiple times.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import threading


class OffChainCache:
    """
    Thread-safe in-memory cache for off-chain pair data.
    
    Features:
    - TTL-based expiration
    - Size limit with LRU eviction
    - Thread-safe operations
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize cache.
        
        Args:
            config: Cache configuration dict
        """
        self.config = config or {}
        
        self.ttl_seconds = self.config.get('ttl_seconds', 300)  # 5 minutes default
        self.max_size = self.config.get('max_size', 1000)  # Max 1000 entries
        
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # Stats
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[Dict]:
        """
        Get cached value if exists and not expired.
        
        Args:
            key: Cache key (usually pair_address)
            
        Returns:
            Cached value or None
        """
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check if expired
            if self._is_expired(entry):
                del self._cache[key]
                self.misses += 1
                return None
            
            # Update access time for LRU
            entry['last_accessed'] = datetime.now()
            self.hits += 1
            
            return entry['value']
    
    def set(self, key: str, value: Dict):
        """
        Set cache value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Check size limit
            if key not in self._cache and len(self._cache) >= self.max_size:
                self._evict_lru()
            
            now = datetime.now()
            self._cache[key] = {
                'value': value,
                'created_at': now,
                'last_accessed': now,
                'expires_at': now + timedelta(seconds=self.ttl_seconds)
            }
    
    def delete(self, key: str):
        """
        Delete cache entry.
        
        Args:
            key: Cache key
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    def _is_expired(self, entry: Dict) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > entry['expires_at']
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        # Find LRU entry
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]['last_accessed']
        )
        
        del self._cache[lru_key]
        self.evictions += 1
    
    def cleanup_expired(self):
        """Remove all expired entries."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate_pct': hit_rate,
                'evictions': self.evictions,
                'ttl_seconds': self.ttl_seconds,
            }
