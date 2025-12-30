"""
GECKOTERMINAL API CLIENT

FREE API for getting new pools/pairs without keyword search.
Perfect replacement for DexScreener's limited search API.

API Documentation: https://www.geckoterminal.com/dex-api
Rate Limits: 
- 30 requests per minute (FREE tier)
- Respectful usage recommended

Endpoints:
- /networks/{network}/new_pools - Get recently created pools
- /networks/{network}/trending_pools - Get trending pools
"""

import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class GeckoTerminalAPI:
    """
    GeckoTerminal API client for fetching new and trending pools.
    
    Rate Limits (FREE tier):
    - 30 requests per minute
    - We use 0.5 requests per second (30/min) to be safe
    """
    
    BASE_URL = "https://api.geckoterminal.com/api/v2"
    
    def __init__(self, config: Dict = None):
        """
        Initialize GeckoTerminal API client.
        
        Args:
            config: Optional config dict with rate limits
        """
        self.config = config or {}
        
        # Rate limiting (conservative to avoid hitting limits)
        self.rate_limit_per_minute = self.config.get('rate_limit_per_minute', 30)
        self.min_request_interval = self.config.get('min_request_interval_seconds', 2.0)  # 2s between requests
        
        self.session = None
        self.last_request_time = None
        self.request_count = 0
        
        # Network name mapping
        self.network_map = {
            'solana': 'solana',
            'base': 'base',
            'ethereum': 'eth',
            'eth': 'eth',
        }
    
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
        Make rate-limited HTTP request to GeckoTerminal API.
        
        Args:
            url: Full API URL
            params: Optional query parameters
            
        Returns:
            JSON response or None on error
        """
        await self._ensure_session()
        
        # Enforce minimum interval between requests (2 seconds)
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                wait_time = self.min_request_interval - elapsed
                print(f"[GECKOTERMINAL] Rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        try:
            headers = {
                'Accept': 'application/json',
            }
            
            async with self.session.get(url, params=params, headers=headers, timeout=10) as response:
                self.last_request_time = datetime.now()
                self.request_count += 1
                
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    print(f"[GECKOTERMINAL] Rate limited! Backing off for 60s...")
                    await asyncio.sleep(60)
                    return None
                else:
                    print(f"[GECKOTERMINAL] HTTP {response.status}: {url}")
                    return None
                    
        except asyncio.TimeoutError:
            print(f"[GECKOTERMINAL] Timeout: {url}")
            return None
        except Exception as e:
            print(f"[GECKOTERMINAL] Request error: {e}")
            return None
    
    def _normalize_network_name(self, chain: str) -> str:
        """Normalize chain name to GeckoTerminal network name."""
        chain = chain.lower()
        return self.network_map.get(chain, chain)
    
    async def fetch_new_pools(self, chain: str = "solana", limit: int = 20) -> List[Dict]:
        """
        Fetch recently created pools (NEW PAIRS).
        
        This is the MAIN endpoint - returns pools sorted by creation time.
        NO keyword search needed!
        
        Args:
            chain: Chain name (solana, base, ethereum)
            limit: Max number of pools to return (API returns 20 per page)
            
        Returns:
            List of pool dicts with normalized format
        """
        network = self._normalize_network_name(chain)
        
        print(f"[GECKOTERMINAL] Fetching new pools for {network}...")
        
        url = f"{self.BASE_URL}/networks/{network}/new_pools"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'data' not in data:
            print(f"[GECKOTERMINAL] No data returned for {network}")
            return []
        
        pools = data['data']
        print(f"[GECKOTERMINAL] Got {len(pools)} new pools for {network}")
        
        # Normalize to our format
        normalized_pools = []
        for pool in pools[:limit]:
            normalized = self._normalize_pool(pool, chain)
            if normalized:
                normalized_pools.append(normalized)
        
        print(f"[GECKOTERMINAL] Normalized {len(normalized_pools)} pools")
        return normalized_pools
    
    async def fetch_trending_pools(self, chain: str = "solana", limit: int = 20) -> List[Dict]:
        """
        Fetch trending pools.
        
        Args:
            chain: Chain name (solana, base, ethereum)
            limit: Max number of pools to return
            
        Returns:
            List of pool dicts with normalized format
        """
        network = self._normalize_network_name(chain)
        
        print(f"[GECKOTERMINAL] Fetching trending pools for {network}...")
        
        url = f"{self.BASE_URL}/networks/{network}/trending_pools"
        
        data = await self._rate_limited_request(url)
        
        if not data or 'data' not in data:
            return []
        
        pools = data['data']
        print(f"[GECKOTERMINAL] Got {len(pools)} trending pools for {network}")
        
        # Normalize to our format
        normalized_pools = []
        for pool in pools[:limit]:
            normalized = self._normalize_pool(pool, chain)
            if normalized:
                normalized_pools.append(normalized)
        
        return normalized_pools
    
    def _normalize_pool(self, pool: Dict, chain: str) -> Optional[Dict]:
        """
        Normalize GeckoTerminal pool data to our standard format.
        
        This makes it compatible with existing bot infrastructure.
        """
        try:
            attrs = pool.get('attributes', {})
            
            # Extract pool address
            pool_address = attrs.get('address', '')
            if not pool_address:
                return None
            
            # Extract token info from relationships
            relationships = pool.get('relationships', {})
            base_token = relationships.get('base_token', {}).get('data', {})
            quote_token = relationships.get('quote_token', {}).get('data', {})
            
            # Get base token address (the actual new token)
            base_token_id = base_token.get('id', '')
            # Format: "network_address"
            base_token_address = base_token_id.split('_')[-1] if '_' in base_token_id else ''
            
            # Parse pool name (e.g., "PEPE / WETH")
            pool_name = attrs.get('name', '')
            token_symbol = pool_name.split(' / ')[0] if ' / ' in pool_name else 'UNKNOWN'
            
            # Get volume and liquidity
            volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0) or 0)
            reserve_usd = float(attrs.get('reserve_in_usd', 0) or 0)
            
            # Get price changes
            price_changes = attrs.get('price_change_percentage', {})
            price_change_5m = float(price_changes.get('m5', 0) or 0)
            price_change_1h = float(price_changes.get('h1', 0) or 0)
            price_change_24h = float(price_changes.get('h24', 0) or 0)
            
            # Get transactions
            txns = attrs.get('transactions', {})
            txns_5m = txns.get('m5', {})
            txns_1h = txns.get('h1', {})
            txns_24h = txns.get('h24', {})
            
            tx_5m = (txns_5m.get('buys', 0) or 0) + (txns_5m.get('sells', 0) or 0)
            tx_1h = (txns_1h.get('buys', 0) or 0) + (txns_1h.get('sells', 0) or 0)
            tx_24h = (txns_24h.get('buys', 0) or 0) + (txns_24h.get('sells', 0) or 0)
            
            # Get creation time
            created_at_str = attrs.get('pool_created_at')
            created_at = None
            age_hours = None
            
            if created_at_str:
                try:
                    created_time = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    # Convert to timestamp (milliseconds)
                    created_at = int(created_time.timestamp() * 1000)
                    # Calculate age in hours
                    age_hours = (datetime.now(created_time.tzinfo) - created_time).total_seconds() / 3600
                except:
                    pass
            
            # Normalize to DexScreener-like format for compatibility
            normalized = {
                'chainId': chain.lower(),
                'dexId': 'geckoterminal',
                'pairAddress': pool_address,
                'baseToken': {
                    'address': base_token_address,
                    'symbol': token_symbol,
                    'name': token_symbol,
                },
                'quoteToken': {
                    'symbol': pool_name.split(' / ')[1] if ' / ' in pool_name else 'UNKNOWN',
                },
                'priceUsd': str(attrs.get('base_token_price_usd', '0')),
                'volume': {
                    'h24': volume_24h,
                },
                'liquidity': {
                    'usd': reserve_usd,
                },
                'priceChange': {
                    'm5': price_change_5m,
                    'h1': price_change_1h,
                    'h24': price_change_24h,
                },
                'txns': {
                    'm5': {'buys': txns_5m.get('buys', 0), 'sells': txns_5m.get('sells', 0)},
                    'h1': {'buys': txns_1h.get('buys', 0), 'sells': txns_1h.get('sells', 0)},
                    'h24': {'buys': txns_24h.get('buys', 0), 'sells': txns_24h.get('sells', 0)},
                },
                'pairCreatedAt': created_at,
                'age_hours': age_hours,
                
                # Additional GeckoTerminal-specific data
                'fdv_usd': attrs.get('fdv_usd'),
                'market_cap_usd': attrs.get('market_cap_usd'),
                
                # Metadata
                'source': 'geckoterminal',
            }
            
            return normalized
            
        except Exception as e:
            print(f"[GECKOTERMINAL] Error normalizing pool: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get API usage statistics."""
        return {
            'total_requests': self.request_count,
            'rate_limit': self.rate_limit_per_minute,
            'min_interval': self.min_request_interval,
        }
