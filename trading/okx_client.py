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
    
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_quote(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount: str,
        slippage: float = 0.01 
    ) -> Optional[Dict]:
        """
        Get swap quote from OKX DEX.
        
        Args:
            chain: Chain name (solana, base, ethereum)
            from_token: Token to sell (address or 'native')
            to_token: Token to buy (address)
            amount: Amount in smallest unit (wei, lamports)
            slippage: Slippage tolerance (0.01 = 1%)
        
        Returns:
            Quote dict with route, price, gas estimate
        """
        chain_id = self.CHAIN_IDS.get(chain.lower())
        if not chain_id:
            logger.error(f"Unsupported chain: {chain}")
            return None
        
        url = f"{self.BASE_URL}/quote"
        params = {
            'chainId': chain_id,
            'fromTokenAddress': from_token,
            'toTokenAddress': to_token,
            'amount': amount,
            'slippage': str(slippage),
        }
        
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == '0':
                         return data.get('data', [{}])[0]
                    else:
                         logger.error(f"[OKX] API Error: {data.get('msg')}")
                         return None
                else:
                    logger.error(f"[OKX] HTTP Error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"[OKX] Exception in get_quote: {e}")
            return None

    async def get_swap_data(
        self,
        chain: str,
        from_token: str,
        to_token: str,
        amount: str,
        slippage: float,
        user_wallet: str
    ) -> Optional[Dict]:
        """
        Get swap transaction data.
        
        Returns:
            Transaction data ready to sign and send
        """
        chain_id = self.CHAIN_IDS.get(chain.lower())
        if not chain_id:
            return None

        url = f"{self.BASE_URL}/swap"
        params = {
            'chainId': chain_id,
            'fromTokenAddress': from_token,
            'toTokenAddress': to_token,
            'amount': amount,
            'slippage': str(slippage),
            'userWalletAddress': user_wallet,
        }
        
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == '0':
                         return data.get('data', [{}])[0]
                    else:
                         logger.error(f"[OKX] API Error in swap: {data.get('msg')}")
                         return None
                else:
                    logger.error(f"[OKX] Swap data HTTP error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"[OKX] Exception in get_swap_data: {e}")
            return None
