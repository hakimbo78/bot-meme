"""
Birdeye API Client for Historical Price Data (OHLCV)
Provides accurate ATH tracking for Rebound Scanner feature.
"""

import aiohttp
import asyncio
import time
from typing import Dict, List, Optional
import os

# Cache for OHLCV data (24h TTL)
_ohlcv_cache = {}
OHLCV_CACHE_TTL = 86400  # 24 hours

# Rate limiting
_last_birdeye_request = 0
_birdeye_request_interval = 0.5  # 500ms between requests


async def _rate_limit():
    """Enforce Birdeye API rate limiting."""
    global _last_birdeye_request
    elapsed = time.time() - _last_birdeye_request
    if elapsed < _birdeye_request_interval:
        await asyncio.sleep(_birdeye_request_interval - elapsed)
    _last_birdeye_request = time.time()


def _get_cache(key: str) -> Optional[Dict]:
    """Get cached OHLCV data if valid."""
    if key in _ohlcv_cache:
        timestamp, data = _ohlcv_cache[key]
        if time.time() - timestamp < OHLCV_CACHE_TTL:
            return data
        else:
            del _ohlcv_cache[key]
    return None


def _set_cache(key: str, data: Dict):
    """Cache OHLCV data with timestamp."""
    _ohlcv_cache[key] = (time.time(), data)


class BirdeyeClient:
    """
    Birdeye API client for OHLCV historical data.
    Used to calculate accurate ATH for rebound detection.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('BIRDEYE_API_KEY')
        self.base_url = "https://public-api.birdeye.so"
        
        if not self.api_key:
            print("[BIRDEYE] ⚠️ Warning: No API key found. Set BIRDEYE_API_KEY in .env")
    
    async def get_ohlcv(
        self, 
        token_address: str, 
        chain: str = 'solana',
        timeframe: str = '1H',
        limit: int = 1000
    ) -> List[Dict]:
        """
        Get OHLCV candlestick data for a token.
        
        Args:
            token_address: Token contract address
            chain: blockchain (solana, ethereum, base, etc.)
            timeframe: 1m, 5m, 15m, 1H, 4H, 1D, 1W
            limit: Number of candles (max 1000)
        
        Returns:
            List of candles: [{'time': epoch, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': float}]
        """
        cache_key = f"{chain}_{token_address}_{timeframe}"
        cached = _get_cache(cache_key)
        if cached:
            return cached
        
        if not self.api_key:
            print("[BIRDEYE] ❌ Cannot fetch OHLCV: No API key")
            return []
        
        await _rate_limit()
        
        # Map chain names to Birdeye format
        chain_map = {
            'solana': 'solana',
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'base': 'base',
            'bsc': 'bsc',
            'arbitrum': 'arbitrum',
            'polygon': 'polygon'
        }
        birdeye_chain = chain_map.get(chain.lower(), 'solana')
        
        url = f"{self.base_url}/defi/ohlcv"
        params = {
            'address': token_address,
            'type': timeframe,
            'time_from': int(time.time()) - (730 * 86400),  # 730 days ago (max history)
            'time_to': int(time.time())
        }
        
        headers = {
            'X-API-KEY': self.api_key,
            'x-chain': birdeye_chain
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=15) as resp:
                    if resp.status != 200:
                        print(f"[BIRDEYE] ⚠️ API Error {resp.status}")
                        return []
                    
                    data = await resp.json()
                    
                    if not data.get('success'):
                        print(f"[BIRDEYE] ⚠️ API returned error: {data.get('message')}")
                        return []
                    
                    candles = data.get('data', {}).get('items', [])
                    
                    # Transform to standard format
                    result = []
                    for c in candles:
                        result.append({
                            'time': c.get('unixTime', 0),
                            'open': c.get('o', 0),
                            'high': c.get('h', 0),
                            'low': c.get('l', 0),
                            'close': c.get('c', 0),
                            'volume': c.get('v', 0)
                        })
                    
                    _set_cache(cache_key, result)
                    print(f"[BIRDEYE] ✅ Fetched {len(result)} candles for {token_address[:10]}...")
                    return result
                    
        except asyncio.TimeoutError:
            print(f"[BIRDEYE] ⚠️ Timeout fetching OHLCV")
            return []
        except Exception as e:
            print(f"[BIRDEYE] ❌ Error: {e}")
            return []
    
    async def calculate_ath(self, token_address: str, chain: str = 'solana') -> Dict:
        """
        Calculate All-Time High from historical OHLCV data.
        
        Returns:
            {
                'ath': float,
                'current_price': float,
                'drop_percent': float,
                'ath_time': int (epoch),
                'candles_count': int
            }
        """
        candles = await self.get_ohlcv(token_address, chain, timeframe='1H', limit=1000)
        
        if not candles:
            return {
                'ath': 0,
                'current_price': 0,
                'drop_percent': 0,
                'ath_time': 0,
                'candles_count': 0,
                'error': 'No candle data available'
            }
        
        # Find ATH from all candles
        ath = 0
        ath_time = 0
        for candle in candles:
            high = candle.get('high', 0)
            if high > ath:
                ath = high
                ath_time = candle.get('time', 0)
        
        # Current price = last candle close
        current_price = candles[-1].get('close', 0) if candles else 0
        
        # Calculate drop %
        drop_percent = 0
        if ath > 0 and current_price > 0:
            drop_percent = ((ath - current_price) / ath) * 100
        
        return {
            'ath': ath,
            'current_price': current_price,
            'drop_percent': drop_percent,
            'ath_time': ath_time,
            'candles_count': len(candles)
        }


# Global instance
_birdeye_client = None

def get_birdeye_client() -> BirdeyeClient:
    """Get or create global Birdeye client instance."""
    global _birdeye_client
    if _birdeye_client is None:
        _birdeye_client = BirdeyeClient()
    return _birdeye_client
