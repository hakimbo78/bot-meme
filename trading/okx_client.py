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
        self._load_credentials()

    def _load_credentials(self):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = (os.getenv('OKX_API_KEY') or '').strip().strip('"').strip("'")
        self.secret_key = (os.getenv('OKX_SECRET_KEY') or '').strip().strip('"').strip("'")
        self.passphrase = (os.getenv('OKX_PASSPHRASE') or '').strip().strip('"').strip("'")
        
        # DEBUG: Print credential status (Partial)
        if self.api_key:
            logger.info(f"Loaded API Key: {self.api_key[:4]}...{self.api_key[-4:]}")
        else:
            logger.error("OKX API Key NOT FOUND in env")

    def _get_timestamp(self):
        from datetime import datetime, timezone
        # Use timezone-aware UTC
        now = datetime.now(timezone.utc)
        # Format: 2020-12-08T09:08:57.715Z
        return now.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def _sign_request(self, timestamp, method, request_path, body=''):
        import hmac
        import hashlib
        import base64
        
        message = f"{timestamp}{method}{request_path}{body}"
        logger.info(f"DEBUG SIGN STRING: [{message}]") # ACTIVE DEBUG
        
        mac = hmac.new(
            bytes(self.secret_key, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        d = mac.digest()
        return base64.b64encode(d).decode('utf-8')

    def _get_headers(self, method, request_path, body=''):
        if not (self.api_key and self.secret_key and self.passphrase):
            return {}
            
        timestamp = self._get_timestamp()
        sign = self._sign_request(timestamp, method, request_path, body)
        
        return {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': sign,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
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
        
        headers = self._get_headers('GET', request_path)
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
            logger.error(f"[OKX] Exception in get_quote: {e}")
            return None

    async def get_swap_data(self, chain: str, from_token: str, to_token: str, amount: str, slippage: float, user_wallet: str) -> Optional[Dict]:
        return await self._get_okx_swap(chain, from_token, to_token, amount, slippage, user_wallet)

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
            'slippage': str(slippage),
            'userWalletAddress': user_wallet,
        }
        
        # Sort params alphabetically to match server signature requirement
        params = dict(sorted(params.items()))
        
        from urllib.parse import urlencode
        query_string = urlencode(params)
        request_path = f"{path_base}?{query_string}"
        
        headers = self._get_headers('GET', request_path)
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
