"""
DEXTOOLS API CLIENT

Secondary off-chain source (OPTIONAL, for top-gainer validation).
NEVER poll aggressively - DEXTools has strict rate limits.

DEXTools provides:
- Trending tokens with ranking
- Hot pairs detection
- Top gainers with verified data
- Requires API key for higher limits
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from .base_screener import BaseScreener


class DexToolsAPI(BaseScreener):
    """
    DEXTools API client (OPTIONAL, requires API key).
    
    Rate limits: Varies by plan (Free: ~30 req/min, Pro: more)
    Use sparingly - only for validation of high-confidence signals.
    """
    
    BASE_URL = "https://api.dextools.io/v1"
    
    def __init__(self, config: Dict = None):
        """
        Initialize DEXTools API client.
        
        Args:
            config: Config dict with 'api_key', 'rate_limit_per_minute', etc.
        """
        super().__init__(config)
        self.api_key = self.config.get('api_key', '')
        self.rate_limit_per_minute = self.config.get('rate_limit_per_minute', 30)  # Conservative default
        self.min_request_interval = self.config.get('min_request_interval_seconds', 2.0)  # 2s between requests
        self.session = None
        self.enabled = bool(self.api_key)
        
        if not self.enabled:
            print("[DEXTOOLS] WARNING: No API key provided, DEXTools screener disabled")
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None:
            headers = {
                'X-API-Key': self.api_key
            }
            self.session = aiohttp.ClientSession(headers=headers)
    
    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _rate_limited_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """
        Make rate-limited HTTP request to DEXTools API.
        
        Args:
            url: Full API URL
            params: Optional query parameters
            
        Returns:
            JSON response or None on error
        """
        if not self.enabled:
            return None
        
        await self._ensure_session()
        
        # Enforce minimum interval between requests (CRITICAL for DEXTools)
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                await asyncio.sleep(self.min_request_interval - elapsed)
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                self._update_rate_limit()
                
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    print(f"[DEXTOOLS] Rate limited! Backing off...")
                    await asyncio.sleep(10)
                    return None
                elif response.status == 401:
                    print(f"[DEXTOOLS] Unauthorized - check API key")
                    self.enabled = False
                    return None
                else:
                    print(f"[DEXTOOLS] HTTP {response.status}: {url}")
                    return None
                    
        except asyncio.TimeoutError:
            print(f"[DEXTOOLS] Timeout: {url}")
            return None
        except Exception as e:
            print(f"[DEXTOOLS] Request error: {e}")
            return None
   
    async def fetch_trending_pairs(self, chain: str = "base", limit: int = 50) -> List[Dict]:
        """
        Fetch trending pairs from DEXTools hot pairs.
        
        Args:
            chain: Target chain
            limit: Max pairs to return (DEXTools usually returns top 50)
            
        Returns:
            List of pair data dicts with ranking
        """
        if not self.enabled:
            return []
        
        chain = self._normalize_chain_name(chain)
        
        # DEXTools uses different chain identifiers
        chain_map = {
            'ethereum': 'ether',
            'base': 'base',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'polygon': 'polygon',
        }
        
        dextools_chain = chain_map.get(chain, chain)
        
        # Hot pairs endpoint
        url = f"{self.BASE_URL}/chain/{dextools_chain}/hot"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'data' not in data:
            return []
        
        pairs = data['data'][:limit]
        
        # Add source and ranking
        for idx, pair in enumerate(pairs):
            pair['dextools_rank'] = idx + 1
            pair['source'] = 'dextools'
        
        return pairs
    
    async def fetch_top_gainers(self, chain: str = "base", timeframe: str = "1h", limit: int = 50) -> List[Dict]:
        """
        Fetch top gainers from DEXTools.
        
        Args:
            chain: Target chain
            timeframe: 24h (DEXTools primarily shows 24h gainers)
            limit: Max pairs to return
            
        Returns:
            List of pair data dicts sorted by price change
        """
        if not self.enabled:
            return []
        
        chain = self._normalize_chain_name(chain)
        
        chain_map = {
            'ethereum': 'ether',
            'base': 'base',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'polygon': 'polygon',
        }
        
        dextools_chain = chain_map.get(chain, chain)
        
        # Gainers endpoint (usually shows 24h gainers)
        url = f"{self.BASE_URL}/chain/{dextools_chain}/gainers"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'data' not in data:
            return []
        
        pairs = data['data'][:limit]
        
        # Add source and ranking
        for idx, pair in enumerate(pairs):
            pair['dextools_rank'] = idx + 1
            pair['source'] = 'dextools'
        
        return pairs
    
    async def fetch_pair_details(self, pair_address: str, chain: str = "base") -> Optional[Dict]:
        """
        Fetch detailed pair information from DEXTools.
        
        Args:
            pair_address: Pair contract address
            chain: Target chain
            
        Returns:
            Pair data dict or None
        """
        if not self.enabled:
            return None
        
        chain = self._normalize_chain_name(chain)
        
        chain_map = {
            'ethereum': 'ether',
            'base': 'base',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'polygon': 'polygon',
        }
        
        dextools_chain = chain_map.get(chain, chain)
        
        url = f"{self.BASE_URL}/chain/{dextools_chain}/pair/{pair_address}"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'data' not in data:
            return None
        
        return data['data']
    
    def get_rate_limit_info(self) -> Dict:
        """Get current rate limit status."""
        remaining = self.rate_limit_per_minute - self.request_count
        
        return {
            'remaining': max(0, remaining),
            'reset_time': None,
            'total_requests': self.request_count,
            'rate_limit': self.rate_limit_per_minute,
            'enabled': self.enabled,
        }
