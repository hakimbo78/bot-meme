"""
Moralis API Client
Handles bonding curve status checks for Solana tokens with rate limiting.
"""

import os
import time
import requests
import logging
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class MoralisClient:
    """
    Client for Moralis Solana API with rate limiting for free tier.
    Free tier limits: ~25 requests/second, 40,000 requests/day
    """
    
    def __init__(self):
        self.api_key = os.getenv('MORALIS_API_KEY', '').strip()
        self.base_url = "https://solana-gateway.moralis.io"
        
        # Rate limiting (conservative for free tier)
        self.min_request_interval = 0.1  # 100ms between requests (10 req/s max)
        self._last_request_time = 0
        
        # Cache to avoid repeated API calls for same token
        self._cache: Dict[str, dict] = {}
        self._cache_ttl = 300  # 5 minutes cache
        
        if not self.api_key:
            logger.warning("⚠️ MORALIS_API_KEY not set - Bonding curve checks will be skipped")
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _get_cached(self, token_mint: str) -> Optional[dict]:
        """Get cached result if still valid."""
        if token_mint in self._cache:
            cached = self._cache[token_mint]
            if time.time() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
        return None
    
    def _set_cache(self, token_mint: str, data: dict):
        """Cache the result."""
        self._cache[token_mint] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def check_bonding_status(self, token_mint: str) -> dict:
        """
        Check if Solana token has completed bonding curve.
        
        Returns:
            dict with keys:
            - is_graduated: bool (True if bonding complete)
            - progress: float (0-100)
            - error: Optional[str]
        """
        # No API key - assume graduated (fail-safe)
        if not self.api_key:
            return {'is_graduated': True, 'progress': 100, 'error': 'No API key configured'}
        
        # Check cache first
        cached = self._get_cached(token_mint)
        if cached:
            logger.debug(f"[Moralis] Cache hit for {token_mint[:8]}...")
            return cached
        
        # Rate limit before request
        self._rate_limit()
        
        url = f"{self.base_url}/token/mainnet/{token_mint}/bonding"
        headers = {
            "accept": "application/json",
            "X-API-Key": self.api_key
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            
            # Handle rate limit response
            if resp.status_code == 429:
                logger.warning(f"[Moralis] Rate limited - backing off")
                time.sleep(2)  # Back off for 2 seconds
                return {'is_graduated': True, 'progress': 100, 'error': 'Rate limited'}
            
            if resp.status_code == 404:
                # Token not found in bonding curve system - likely already graduated or not a BC token
                result = {'is_graduated': True, 'progress': 100, 'error': None}
                self._set_cache(token_mint, result)
                return result
            
            if resp.status_code != 200:
                # API error - assume graduated to avoid blocking (fail-safe)
                logger.warning(f"[Moralis] API error {resp.status_code}: {resp.text[:100]}")
                return {'is_graduated': True, 'progress': 100, 'error': f'API {resp.status_code}'}
            
            data = resp.json()
            progress = float(data.get('bondingProgress', 100))
            is_completed = data.get('isCompleted', False)
            
            result = {
                'is_graduated': is_completed or progress >= 100,
                'progress': progress,
                'error': None
            }
            
            # Cache the result
            self._set_cache(token_mint, result)
            
            logger.info(f"[Moralis] {token_mint[:8]}... -> Progress: {progress:.1f}%, Graduated: {result['is_graduated']}")
            return result
            
        except requests.Timeout:
            logger.warning(f"[Moralis] Timeout for {token_mint[:8]}...")
            return {'is_graduated': True, 'progress': 100, 'error': 'Timeout'}
        except Exception as e:
            logger.error(f"[Moralis] Error checking {token_mint[:8]}...: {e}")
            # On error, assume graduated to avoid blocking (fail-safe)
            return {'is_graduated': True, 'progress': 100, 'error': str(e)}
    
    def is_graduated(self, token_mint: str) -> bool:
        """Simple helper - returns True if token has graduated from bonding curve."""
        result = self.check_bonding_status(token_mint)
        return result['is_graduated']


# Singleton instance
_moralis_client = None

def get_moralis_client() -> MoralisClient:
    """Get or create singleton MoralisClient instance."""
    global _moralis_client
    if _moralis_client is None:
        _moralis_client = MoralisClient()
    return _moralis_client
