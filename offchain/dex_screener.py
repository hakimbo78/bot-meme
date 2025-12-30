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
    
    def _get_search_queries(self, chain: str) -> list:
        """
        Get MULTIPLE search queries for a chain to find trending/new pairs.
        
        ROOT CAUSE FIX:
        - Old strategy: Query by WETH/SOL address → Only returns established pairs
        - New strategy: Query by popular keywords + DEX names → Returns new coins
        
        This returns a LIST of queries to scan comprehensively.
        """
        chain = chain.lower()
        
        # Base queries: Popular meme/trending keywords
        base_queries = ['pepe', 'doge', 'meme', 'ai', 'trump', 'cat', 'dog']
        
        if chain == 'base':
            # Base-specific: DEX names + keywords
            dex_queries = ['uniswap', 'aerodrome', 'baseswap']
            return base_queries + dex_queries
            
        elif chain == 'solana':
            # Solana-specific: DEX names + keywords
            dex_queries = ['raydium', 'orca', 'pump']  # pump.fun is popular
            return base_queries + dex_queries
            
        elif chain == 'ethereum':
            # Ethereum-specific
            dex_queries = ['uniswap', 'sushiswap']
            return base_queries + dex_queries
            
        else:
            # Fallback: just use base queries
            return base_queries
            
    async def fetch_trending_pairs(self, chain: str = "base", limit: int = 50) -> List[Dict]:
        """
        Fetch trending pairs by volume - WITH QUALITY FILTERS.
        
        NEW STRATEGY (ROOT CAUSE FIX):
        - Use MULTIPLE queries (keywords + DEX names) instead of single WETH/SOL address
        - This detects NEW coins that appear in DexScreener dashboard
        - Aggregate results from all queries and deduplicate
        
        Improvements:
        - Pre-filter dead pairs ($0 volume)
        - Pre-filter low liquidity pairs (< $100) - RELAXED for Level-0
        - Sort by 24h volume (most active first)
        - Only return quality pairs
        """
        chain = self._normalize_chain_name(chain)
        queries = self._get_search_queries(chain)
        
        print(f"[DEXSCREENER DEBUG] fetch_trending_pairs called for chain: {chain}")
        print(f"[DEXSCREENER DEBUG] Using {len(queries)} queries: {queries}")
        
        # Strategy: Use MULTIPLE searches and aggregate results
        url = f"{self.BASE_URL}/search"
        
        all_pairs = []
        seen_addresses = set()
        
        # Iterate through all queries
        for query in queries:
            params = {'q': query}
            
            print(f"[DEXSCREENER DEBUG] Query: '{query}'")
            
            data = await self._rate_limited_request(url, params)
            
            if not data or 'pairs' not in data:
                continue
            
            pairs = data['pairs']
            print(f"[DEXSCREENER DEBUG]   - Got {len(pairs)} pairs")
            
            # Filter by chain and deduplicate
            for p in pairs:
                if p.get('chainId', '').lower() == chain:
                    addr = p.get('pairAddress', '')
                    if addr and addr not in seen_addresses:
                        seen_addresses.add(addr)
                        all_pairs.append(p)
        
        print(f"[DEXSCREENER DEBUG] Total unique pairs from all queries: {len(all_pairs)}")
        
        # ============================================================
        # PRE-FILTERING (Improve data quality)
        # ============================================================
        
        quality_pairs = []
        filtered_dead = 0
        filtered_low_liq = 0
        filtered_no_data = 0
        
        for p in all_pairs:
            # Get volume (prefer 24h for stability)
            vol_24h = p.get('volume', {}).get('h24', 0) if isinstance(p.get('volume'), dict) else 0
            vol_24h = float(vol_24h) if vol_24h else 0
            
            # Get liquidity
            liquidity = p.get('liquidity', {}).get('usd', 0) if isinstance(p.get('liquidity'), dict) else 0
            liquidity = float(liquidity) if liquidity else 0
            
            # QUALITY CHECKS
            # Skip if NO volume at all (dead pair)
            if vol_24h <= 0:
                filtered_dead += 1
                continue
            
            # RELAXED PRE-FILTER: $100 min liquidity (was $500)
            # This allows early pairs but stops absolute dust
            if liquidity < 100:
                filtered_low_liq += 1
                continue
            
            # Skip if missing critical data
            if not p.get('pairAddress'):
                filtered_no_data += 1
                continue
            
            # Passed quality checks
            quality_pairs.append(p)
        
        print(f"[DEXSCREENER DEBUG] Quality filter: {len(quality_pairs)} passed")
        print(f"[DEXSCREENER DEBUG]   - Filtered dead pairs ($0 vol): {filtered_dead}")
        print(f"[DEXSCREENER DEBUG]   - Filtered low liq (<$100): {filtered_low_liq}")
        print(f"[DEXSCREENER DEBUG]   - Filtered no data: {filtered_no_data}")
        
        # Step 3: Sort by 24h volume descending (most active first)
        quality_pairs.sort(
            key=lambda x: float(x.get('volume', {}).get('h24', 0) or 0),
            reverse=True
        )
        
        result = quality_pairs[:limit]
        print(f"[DEXSCREENER DEBUG] Returning {len(result)} HIGH QUALITY pairs")
        
        return result
    
    async def fetch_top_gainers(self, chain: str = "base", timeframe: str = "1h", limit: int = 50) -> List[Dict]:
        """Fetch top gainers by price change."""
        chain = self._normalize_chain_name(chain)
        query = self._get_search_query(chain)
        
        # Map timeframe to DexScreener field
        timeframe_map = {
            '5m': 'm5', '15m': 'm5', '1h': 'h1', '6h': 'h6', '24h': 'h24',
        }
        tf_key = timeframe_map.get(timeframe, 'h1')
        
        # Search using optimized query
        search_url = f"{self.BASE_URL}/search"
        params = {'q': query}
        
        data = await self._rate_limited_request(search_url, params)
        
        if not data or 'pairs' not in data:
            return []
        
        pairs = data['pairs']
        
        # Filter by chain
        chain_pairs = [
            p for p in pairs 
            if p.get('chainId', '').lower() == chain
        ]
        
        all_pairs = []
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
        """Fetch detailed pair information."""
        chain = self._normalize_chain_name(chain)
        url = f"{self.BASE_URL}/pairs/{chain}/{pair_address}"
        data = await self._rate_limited_request(url)
        if not data or 'pair' not in data:
            return None
        return data['pair']
    
    async def fetch_new_pairs(self, chain: str = "base", max_age_minutes: int = 60) -> List[Dict]:
        """
        Fetch recently created pairs - WITH QUALITY FILTERS.
        
        NEW STRATEGY (ROOT CAUSE FIX):
        - Use MULTIPLE queries to find new coins
        - Aggregate and deduplicate results
        """
        chain = self._normalize_chain_name(chain)
        queries = self._get_search_queries(chain)
        
        print(f"[DEXSCREENER DEBUG] fetch_new_pairs called for chain: {chain}, max_age: {max_age_minutes}min")
        print(f"[DEXSCREENER DEBUG] Using {len(queries)} queries")
        
        url = f"{self.BASE_URL}/search"
        
        all_pairs = []
        seen_addresses = set()
        
        # Iterate through all queries
        for query in queries:
            params = {'q': query}
            
            data = await self._rate_limited_request(url, params)
            
            if not data or 'pairs' not in data:
                continue
            
            pairs = data['pairs']
            
            # Filter by chain and deduplicate
            for p in pairs:
                if p.get('chainId', '').lower() == chain:
                    addr = p.get('pairAddress', '')
                    if addr and addr not in seen_addresses:
                        seen_addresses.add(addr)
                        all_pairs.append(p)
        
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        new_pairs = []
        filtered_dead = 0
        filtered_low_liq = 0
        
        for pair in all_pairs:
            created_at = pair.get('pairCreatedAt')
            if not created_at:
                continue
            
            try:
                created_time = datetime.fromtimestamp(created_at / 1000)
                if created_time < cutoff_time:
                    continue
                
                # Quality checks
                vol_24h = float(pair.get('volume', {}).get('h24', 0) or 0)
                liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                
                if vol_24h <= 0:
                    filtered_dead += 1
                    continue
                
                if liquidity < 100: # RELAXED: was 500
                    filtered_low_liq += 1
                    continue
                
                new_pairs.append(pair)
                
            except Exception as e:
                pass
        
        print(f"[DEXSCREENER DEBUG] New pairs found: {len(new_pairs)} (liq>100, vol>0)")
        return new_pairs
    
    def get_rate_limit_info(self) -> Dict:
        """Get current rate limit status."""
        remaining = self.rate_limit_per_minute - self.request_count
        return {
            'remaining': max(0, remaining),
            'reset_time': None,
            'total_requests': self.request_count,
            'rate_limit': self.rate_limit_per_minute,
        }
