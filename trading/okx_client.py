"""
OKX DEX API Client
Handles quote fetching and swap execution
"""

import aiohttp
import asyncio
from typing import Dict, Optional, List
import json
import logging

logger = logging.getLogger(__name__)

class OKXDexClient:
    """OKX DEX API client for multi-chain swaps."""
    
    BASE_URL = "https://www.okx.com/api/v5/dex/aggregator"
    
    # Chain ID mapping
    CHAIN_IDS = {
        'solana': '501',
        'base': '8453',
        'ethereum': '1',
    }
    
    # Jupiter API for Solana
    JUPITER_URL = "https://quote-api.jup.ag/v6"
    SOL_MINT = "So11111111111111111111111111111111111111112"

    def __init__(self):
        self.session = None
        self.api_key = None
        self.secret_key = None
        self.passphrase = None
        
        # Rate limiting: Max 60 requests per minute
        from collections import deque
        self._request_times = deque(maxlen=60)
        self._rate_limit_lock = asyncio.Lock()
        self._min_request_interval = 2.0  # Increased to 2s to be safe
        
        self._load_credentials()

    def _load_credentials(self):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # Trading API credentials (for CEX trading - not used for DEX)
        self.api_key = (os.getenv('OKX_API_KEY') or '').strip().strip('"').strip("'")
        self.secret_key = (os.getenv('OKX_SECRET_KEY') or '').strip().strip('"').strip("'")
        self.passphrase = (os.getenv('OKX_PASSPHRASE') or '').strip().strip('"').strip("'")
        
        # Web3/DEX API credentials (for DEX Aggregator)
        self.web3_api_key = (os.getenv('OKX_WEB3_API_KEY') or '').strip().strip('"').strip("'")
        self.web3_secret = (os.getenv('OKX_WEB3_SECRET') or '').strip().strip('"').strip("'")
        self.web3_passphrase = (os.getenv('OKX_WEB3_PASSPHRASE') or '').strip().strip('"').strip("'")
        
        # DEBUG: Print credential status
        if self.web3_api_key:
            logger.info(f"Loaded Web3 API Key: {self.web3_api_key[:4]}...{self.web3_api_key[-4:]}")
        else:
            logger.warning("OKX Web3 API Key NOT FOUND - DEX trading will fail")

    async def _rate_limit(self):
        """Enforce rate limiting to prevent 429 errors"""
        async with self._rate_limit_lock:
            from time import time
            
            current_time = time()
            
            # Remove requests older than 60 seconds
            while self._request_times and current_time - self._request_times[0] > 60:
                self._request_times.popleft()
            
            # If we've made 60 requests in the last minute, wait
            if len(self._request_times) >= 60:
                sleep_time = 60 - (current_time - self._request_times[0]) + 1
                if sleep_time > 0:
                    logger.warning(f"Rate limit reached, waiting {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
            
            # Enforce minimum interval between requests
            if self._request_times:
                time_since_last = current_time - self._request_times[-1]
                if time_since_last < self._min_request_interval:
                    await asyncio.sleep(self._min_request_interval - time_since_last)
            
            # Record this request
            self._request_times.append(time())

    def _get_timestamp(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return now.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _sign_request(self, timestamp, method, request_path, body=''):
        """Sign request using Web3 Secret Key"""
        import hmac
        import hashlib
        import base64
        
        message = f"{timestamp}{method}{request_path}{body}"
        logger.info(f"DEBUG SIGN STRING: [{message}]")
        
        mac = hmac.new(
            bytes(self.web3_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        d = mac.digest()
        return base64.b64encode(d).decode('utf-8')

    def _get_dex_headers(self, method, request_path, body=''):
        """Get headers for DEX Aggregator API (Web3 API with HMAC signature)"""
        if not (self.web3_api_key and self.web3_secret and self.web3_passphrase):
            logger.error("Web3 API credentials missing")
            return {}
        
        timestamp = self._get_timestamp()
        sign = self._sign_request(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.web3_api_key,
            'OK-ACCESS-SIGN': sign,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.web3_passphrase,
            'Content-Type': 'application/json'
        }

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_quote(self, chain: str, from_token: str, to_token: str, amount: str, slippage: float = 0.01) -> Optional[Dict]:
        await self._rate_limit()
        # Force OKX for all chains
        return await self._get_okx_quote(chain, from_token, to_token, amount, slippage)

    async def _get_okx_quote(self, chain, from_token, to_token, amount, slippage):
        import requests # Use requests for consistent URL encoding vs Signature
        
        chain_id = self.CHAIN_IDS.get(chain.lower())
        if not chain_id:
            logger.error(f"Unsupported chain: {chain}")
            return None
        
        path_base = "/api/v5/dex/aggregator/quote"
        
        params = {
            'chainId': chain_id,
            'fromTokenAddress': from_token,
            'toTokenAddress': to_token,
            'amount': amount,
            'slippage': str(slippage),
        }
        
        # Sort params alphabetically
        params = dict(sorted(params.items()))
        
        from urllib.parse import urlencode
        query_string = urlencode(params)
        request_path = f"{path_base}?{query_string}"
        
        headers = self._get_dex_headers('GET', request_path)
        # Add User-Agent to avoid blocking
        headers['User-Agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        url = f"https://www.okx.com{request_path}"
        
        try:
            # Blocking call is acceptable here for ensuring Auth works
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                        return data.get('data', [{}])[0]
                else:
                        logger.error(f"[OKX] API Error: {data.get('msg')}")
                        return None
            else:
                logger.error(f"[OKX] HTTP Error: {response.status_code}")
                logger.error(f"[OKX] Response: {response.text}")
                return None
        except Exception as e:
            # Raise exception for network/unexpected errors so main loop skips instead of panicking
            logger.error(f"[OKX] Exception in get_quote: {e}")
            raise e

    async def get_swap_data(self, chain: str, from_token: str, to_token: str, amount: str, slippage: float, user_wallet: str) -> Optional[Dict]:
        await self._rate_limit()
        if chain.lower() == 'solana':
            return await self._get_jupiter_swap(from_token, to_token, amount, slippage, user_wallet)
        return await self._get_okx_swap(chain, from_token, to_token, amount, slippage, user_wallet)

    async def _get_jupiter_swap(self, from_token, to_token, amount, slippage, user_wallet):
        """Get swap instructions from Jupiter API (Solana) - Sync version fallback."""
        
        # List of endpoints to try (Main vs Backup)
        # Note: public.jupiterapi.com typically exposes /quote directly without /v6 prefix, 
        # but to keep logic simple we try standard paths first or adapt.
        endpoints = [
            "https://public.jupiterapi.com", # PRIMARY (QuickNode Public - More reliable DNS)
            # "https://quote-api.jup.ag/v6", # Official (DISABLED: DNS Resolution Issues on VPS)
            # "https://jupiter-api.raydium.io/v6", # Raydium (DISABLED: DNS Resolution Issues)
        ]

        import requests
        slippage_bps = int(slippage * 100)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }

        last_error = None

        for base_url in endpoints:
            try:
                # Adjust path based on endpoint known structure
                # public.jupiterapi.com usually behaves like root is v6
                if "public.jupiterapi.com" in base_url:
                     quote_url = f"{base_url}/quote?inputMint={from_token}&outputMint={to_token}&amount={amount}&slippageBps={slippage_bps}"
                     swap_url = f"{base_url}/swap"
                else:
                     quote_url = f"{base_url}/quote?inputMint={from_token}&outputMint={to_token}&amount={amount}&slippageBps={slippage_bps}"
                     swap_url = f"{base_url}/swap"
                
                logger.info(f"[Jupiter] Trying endpoint: {base_url}...")
                
                # 1. Get Quote
                response = requests.get(quote_url, headers=headers, timeout=5)
                if response.status_code != 200:
                    last_error = f"Quote failed {response.status_code}: {response.text}"
                    continue # Try next
                
                quote_data = response.json()
                
                # 2. Get Swap Transaction
                payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": user_wallet,
                    "wrapAndUnwrapSol": True,
                    "computeUnitPriceMicroLamports": "auto",  # Dynamic priority fee
                    "asLegacyTransaction": False,  # Use versioned transaction
                    "dynamicComputeUnitLimit": True,  # Auto-calculate CU
                    "skipUserAccountsRpcCalls": False  # Ensure account checks
                }
                
                response = requests.post(swap_url, json=payload, headers=headers, timeout=5)
                if response.status_code != 200:
                    last_error = f"Swap failed {response.status_code}: {response.text}"
                    continue # Try next
                    
                swap_resp = response.json()
                        
                # 3. Format
                return {
                    'tx': {
                        'data': swap_resp['swapTransaction'] 
                    },
                    'routerResult': {
                        'toTokenAmount': quote_data.get('outAmount', '0')
                    }
                }
            except Exception as e:
                logger.error(f"[Jupiter] Error with {base_url}: {e}")
                last_error = str(e)
                continue
        
        logger.error(f"[Jupiter] All endpoints failed. Last error: {last_error}")
        return None

    async def _get_okx_swap(self, chain, from_token, to_token, amount, slippage, user_wallet):
        chain_id = self.CHAIN_IDS.get(chain.lower())
        if not chain_id:
            return None
        
        path_base = "/api/v5/dex/aggregator/swap"
        
        params = {
            'chainId': chain_id,
            'fromTokenAddress': from_token,
            'toTokenAddress': to_token,
            'amount': amount,
            'slippage': str(float(slippage) / 100), # Convert % (e.g 15.0) to decimal (0.15)
            'userWalletAddress': user_wallet,
        }
        
        # Sort params alphabetically to match server signature requirement
        params = dict(sorted(params.items()))
        
        from urllib.parse import urlencode
        query_string = urlencode(params)
        request_path = f"{path_base}?{query_string}"
        
        headers = self._get_dex_headers('GET', request_path)
        headers['User-Agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        url = f"https://www.okx.com{request_path}"
        logger.info(f"DEBUG FINAL SWAP URL: {url}")
        
        try:
            import requests
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == '0':
                        return data.get('data', [{}])[0]
                else:
                        logger.error(f"[OKX] API Error in swap: {data.get('msg')}")
                        return None
            else:
                logger.error(f"[OKX] Swap data HTTP error: {response.status_code}")
                logger.error(f"[OKX] Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"[OKX] Exception in get_swap_data: {e}")
            return None

    async def close(self):
        """Close client session."""
        if self.session and not self.session.closed:
            await self.session.close()
