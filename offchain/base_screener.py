"""
BASE SCREENER - Abstract base class for off-chain data sources

Defines the interface all screeners must implement.
Ensures consistent data structure across DexScreener, DEXTools, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime


class BaseScreener(ABC):
    """
    Abstract base class for off-chain screeners.
    
    All screeners (DexScreener, DEXTools) must implement these methods.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize base screener.
        
        Args:
            config: Configuration dict with API keys, rate limits, etc.
        """
        self.config = config or {}
        self.last_request_time = None
        self.request_count = 0
        
    @abstractmethod
    async def fetch_trending_pairs(self, chain: str = "base", limit: int = 50) -> List[Dict]:
        """
        Fetch trending pairs from the data source.
        
        Args:
            chain: Target chain (base, ethereum, blast, etc.)
            limit: Maximum number of pairs to return
            
        Returns:
            List of raw pair data dicts
        """
        pass
    
    @abstractmethod
    async def fetch_top_gainers(self, chain: str = "base", timeframe: str = "1h", limit: int = 50) -> List[Dict]:
        """
        Fetch top gainers by price change.
        
        Args:
            chain: Target chain
            timeframe: Time window (5m, 15m, 1h, 24h)
            limit: Maximum number of pairs to return
            
        Returns:
            List of raw pair data dicts
        """
        pass
    
    @abstractmethod
    async def fetch_pair_details(self, pair_address: str, chain: str = "base") -> Optional[Dict]:
        """
        Fetch detailed information for a specific pair.
        
        Args:
            pair_address: The pair/pool address
            chain: Target chain
            
        Returns:
            Detailed pair data or None if not found
        """
        pass
    
    @abstractmethod
    def get_rate_limit_info(self) -> Dict:
        """
        Get current rate limit status.
        
        Returns:
            Dict with 'remaining', 'reset_time', 'total_requests' keys
        """
        pass
    
    def _update_rate_limit(self):
        """Update internal rate limit tracking."""
        self.last_request_time = datetime.now()
        self.request_count += 1
    
    def _normalize_chain_name(self, chain: str) -> str:
        """
        Normalize chain name to lowercase standard format.
        
        Args:
            chain: Chain name in any case
            
        Returns:
            Normalized chain name
        """
        chain_map = {
            'base': 'base',
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'blast': 'blast',
            'arbitrum': 'arbitrum',
            'arb': 'arbitrum',
            'optimism': 'optimism',
            'op': 'optimism',
            'polygon': 'polygon',
            'matic': 'polygon',
            'solana': 'solana',
            'sol': 'solana',
        }
        return chain_map.get(chain.lower(), chain.lower())
    
    def get_stats(self) -> Dict:
        """
        Get screener statistics.
        
        Returns:
            Dict with stats like request count, last request time, etc.
        """
        return {
            'request_count': self.request_count,
            'last_request': self.last_request_time.isoformat() if self.last_request_time else None,
            'source': self.__class__.__name__,
        }
