"""
DEXSCREENER API CLIENT

Primary off-chain data source (MANDATORY, FREE, FAST).
Never poll aggressively - respect rate limits.

DexScreener provides:
- Real-time pair data
- Price changes (5m, 1h, 6h, 24h)
- Volume and liquidity
- Transaction counts
- NO API KEY REQUIRED
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .base_screener import BaseScreener


class DexScreenerAPI(BaseScreener):
    """
    DexScreener API client (FREE, no API key required).
    
    Rate limits: ~300 requests/minute (self-imposed to be respectful)
    """
    
    BASE_URL = "https://api.dexscreener.com/latest/dex"
    
    def __init__(self, config: Dict = None):
        """
        Initialize DexScreener API client.
        
        Args:
            config: Optional config dict with rate limits, etc.
        """
        super().__init__(config)
        self.rate_limit_per_minute = self.config.get('rate_limit_per_minute', 300)
        self.min_request_interval = self.config.get('min_request_interval_seconds', 0.2)  # 200ms between requests
        self.session = None
        
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _rate_limited_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """
        Make rate-limited HTTP request to DexScreener API.
        
        Args:
            url: Full API URL
            params: Optional query parameters
            
        Returns:
            JSON response or None on error
        """
        await self._ensure_session()
        
        # Enforce minimum interval between requests
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
                    print(f"[DEXSCREENER] Rate limited! Backing off...")
                    await asyncio.sleep(5)
                    return None
                else:
                    print(f"[DEXSCREENER] HTTP {response.status}: {url}")
                    return None
                    
        except asyncio.TimeoutError:
            print(f"[DEXSCREENER] Timeout: {url}")
            return None
        except Exception as e:
            print(f"[DEXSCREENER] Request error: {e}")
            return None
    
    async def fetch_trending_pairs(self, chain: str = "base", limit: int = 50) -> List[Dict]:
        """
        Fetch trending pairs by volume.
        
        DexScreener doesn't have a direct "trending" endpoint,
        so we search for recently created pairs with high volume.
        
        Args:
            chain: Target chain
            limit: Max pairs to return
            
        Returns:
            List of pair data dicts
        """
        chain = self._normalize_chain_name(chain)
        
        print(f"[DEXSCREENER DEBUG] fetch_trending_pairs called for chain: {chain}")
        
        # Use search endpoint with chain filter
        url = f"{self.BASE_URL}/search"
        params = {
            'q': chain,  # Search by chain
        }
        
        print(f"[DEXSCREENER DEBUG] Making request to: {url} with params: {params}")
        
        data = await self._rate_limited_request(url, params)
        
        if not data:
            print(f"[DEXSCREENER DEBUG] No data returned from API")
            return []
        
        if 'pairs' not in data:
            print(f"[DEXSCREENER DEBUG] Response has no 'pairs' key. Keys: {list(data.keys())}")
            return []
        
        pairs = data['pairs']
        print(f"[DEXSCREENER DEBUG] API returned {len(pairs)} total pairs")
        
        # Log first pair for debugging
        if pairs:
            sample_pair = pairs[0]
            print(f"[DEXSCREENER DEBUG] Sample pair chainId: {sample_pair.get('chainId')}, pairAddress: {sample_pair.get('pairAddress', 'N/A')[:10]}...")
        
        # Filter by chain and sort by volume
        chain_pairs = [
            p for p in pairs 
            if p.get('chainId', '').lower() == chain
        ]
        
        print(f"[DEXSCREENER DEBUG] After chain filter ({chain}): {len(chain_pairs)} pairs")
        
        # Sort by 24h volume descending
        chain_pairs.sort(
            key=lambda x: float(x.get('volume', {}).get('h24', 0) or 0),
            reverse=True
        )
        
        result = chain_pairs[:limit]
        print(f"[DEXSCREENER DEBUG] Returning {len(result)} pairs")
        
        return result
    
    async def fetch_top_gainers(self, chain: str = "base", timeframe: str = "1h", limit: int = 50) -> List[Dict]:
        """
        Fetch top gainers by price change.
        
        Args:
            chain: Target chain
            timeframe: 5m, 1h, 6h, or 24h
            limit: Max pairs to return
            
        Returns:
            List of pair data dicts sorted by price change
        """
        chain = self._normalize_chain_name(chain)
        
        # Map timeframe to DexScreener field
        timeframe_map = {
            '5m': 'm5',
            '15m': 'm5',  # DexScreener doesn't have 15m, use 5m
            '1h': 'h1',
            '6h': 'h6',
            '24h': 'h24',
        }
        
        tf_key = timeframe_map.get(timeframe, 'h1')
        
        # Fetch pairs for chain using tokens endpoint
        url = f"{self.BASE_URL}/tokens/{chain}"
        
        # Get multiple pages if needed
        all_pairs = []
        
        # DexScreener doesn't support pagination in the same way
        # We'll use the search endpoint and filter
        search_url = f"{self.BASE_URL}/search"
        params = {'q': chain}
        
        data = await self._rate_limited_request(search_url, params)
        
        if not data or 'pairs' not in data:
            return []
        
        pairs = data['pairs']
        
        # Filter by chain
        chain_pairs = [
            p for p in pairs 
            if p.get('chainId', '').lower() == chain
        ]
        
        # Extract price changes and filter positive gainers
        for pair in chain_pairs:
            price_change = pair.get('priceChange', {}).get(tf_key, 0)
            if price_change and float(price_change) > 0:
                all_pairs.append(pair)
        
        # Sort by price change descending
        all_pairs.sort(
            key=lambda x: float(x.get('priceChange', {}).get(tf_key, 0) or 0),
            reverse=True
        )
        
        return all_pairs[:limit]
    
    async def fetch_pair_details(self, pair_address: str, chain: str = "base") -> Optional[Dict]:
        """
        Fetch detailed pair information.
        
        Args:
            pair_address: Pair contract address
            chain: Target chain
            
        Returns:
            Pair data dict or None
        """
        chain = self._normalize_chain_name(chain)
        
        url = f"{self.BASE_URL}/pairs/{chain}/{pair_address}"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'pair' not in data:
            return None
        
        return data['pair']
    
    async def fetch_new_pairs(self, chain: str = "base", max_age_minutes: int = 60) -> List[Dict]:
        """
        Fetch recently created pairs.
        
        This is the MAIN METHOD for detecting new tokens.
        
        Args:
            chain: Target chain
            max_age_minutes: Maximum age of pair in minutes
            
        Returns:
            List of new pair data dicts
        """
        chain = self._normalize_chain_name(chain)
        
        print(f"[DEXSCREENER DEBUG] fetch_new_pairs called for chain: {chain}, max_age: {max_age_minutes}min")
        
        # Use search to find recent pairs
        url = f"{self.BASE_URL}/search"
        params = {'q': chain}
        
        data = await self._rate_limited_request(url, params)
        
        if not data:
            print(f"[DEXSCREENER DEBUG] No data returned from API")
            return []
        
        if 'pairs' not in data:
            print(f"[DEXSCREENER DEBUG] Response has no 'pairs' key")
            return []
        
        pairs = data['pairs']
        print(f"[DEXSCREENER DEBUG] API returned {len(pairs)} total pairs")
        
        # Filter by chain and age
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        print(f"[DEXSCREENER DEBUG] Cutoff time: {cutoff_time}")
        
        new_pairs = []
        chain_matched = 0
        has_creation_time = 0
        
        for pair in pairs:
            if pair.get('chainId', '').lower() != chain:
                continue
            
            chain_matched += 1
            
            # Parse creation time
            created_at = pair.get('pairCreatedAt')
            if created_at:
                has_creation_time += 1
                try:
                    created_time = datetime.fromtimestamp(created_at / 1000)  # milliseconds to seconds
                    if created_time >= cutoff_time:
                        new_pairs.append(pair)
                except Exception as e:
                    print(f"[DEXSCREENER DEBUG] Error parsing creation time: {e}")
                    pass
        
        print(f"[DEXSCREENER DEBUG] Chain matched: {chain_matched}, Has creation time: {has_creation_time}, New pairs: {len(new_pairs)}")
        
        return new_pairs
    
    def get_rate_limit_info(self) -> Dict:
        """Get current rate limit status."""
        remaining = self.rate_limit_per_minute - self.request_count
        
        return {
            'remaining': max(0, remaining),
            'reset_time': None,  # DexScreener doesn't expose this
            'total_requests': self.request_count,
            'rate_limit': self.rate_limit_per_minute,
        }
