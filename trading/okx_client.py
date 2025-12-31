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
        if chain.lower() == 'solana':
            return await self._get_jupiter_swap(from_token, to_token, amount, slippage, user_wallet)
        return await self._get_okx_swap(chain, from_token, to_token, amount, slippage, user_wallet)

    async def _get_jupiter_swap(self, from_token, to_token, amount, slippage, user_wallet):
        """Get swap instructions from Jupiter API (Solana) - Sync version fallback."""
        try:
            import requests
            # 1. Get Quote
            slippage_bps = int(slippage * 100)
            quote_url = f"{self.JUPITER_URL}/quote?inputMint={from_token}&outputMint={to_token}&amount={amount}&slippageBps={slippage_bps}"
            
            # Use requests with User-Agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/json"
            }
            
            response = requests.get(quote_url, headers=headers)
            if response.status_code != 200:
                logger.error(f"[Jupiter] Quote failed ({response.status_code}): {response.text}")
                return None
            quote_data = response.json()
            
            # 2. Get Swap Transaction
            swap_url = f"{self.JUPITER_URL}/swap"
            payload = {
                "quoteResponse": quote_data,
                "userPublicKey": user_wallet,
                "wrapAndUnwrapSol": True
            }
            
            response = requests.post(swap_url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"[Jupiter] Swap failed ({response.status_code}): {response.text}")
                return None
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
            logger.error(f"[Jupiter] Exception: {e}")
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
            'slippage': str(slippage),
            'userWalletAddress': user_wallet,
        }
        
        # Sort params alphabetically to match server signature requirement
        params = dict(sorted(params.items()))
        
        from urllib.parse import urlencode
        query_string = urlencode(params)
        request_path = f"{path_base}?{query_string}"
        
        headers = self._get_dex_headers('GET', request_path)
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
