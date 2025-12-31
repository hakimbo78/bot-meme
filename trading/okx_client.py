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

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_quote(self, chain: str, from_token: str, to_token: str, amount: str, slippage: float = 0.01) -> Optional[Dict]:
        if chain.lower() == 'solana':
            return await self._get_jupiter_quote(from_token, to_token, amount, slippage)
        
        # Fallback to OKX for other chains (requires Auth fix later)
        return await self._get_okx_quote(chain, from_token, to_token, amount, slippage)

    async def _get_jupiter_quote(self, from_token: str, to_token: str, amount: str, slippage: float) -> Optional[Dict]:
        """Fetch quote from Jupiter (Solana)."""
        # Handle Native SOL mapping
        input_mint = self.SOL_MINT if from_token.lower() in ['native', 'sol'] else from_token
        output_mint = self.SOL_MINT if to_token.lower() in ['native', 'sol'] else to_token
        
        url = f"{self.JUPITER_URL}/quote"
        params = {
            'inputMint': input_mint,
            'outputMint': output_mint,
            'amount': amount,
            'slippageBps': int(slippage * 10000) # Jupiter uses basis points (1% = 100)
        }
        
        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data # Jupiter returns the route directly
                else:
                    text = await response.text()
                    logger.error(f"[JUPITER] Quote Error {response.status}: {text}")
                    return None
        except Exception as e:
            logger.error(f"[JUPITER] Exception: {e}")
            return None

    async def _get_okx_quote(self, chain, from_token, to_token, amount, slippage):
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

    async def get_swap_data(self, chain: str, from_token: str, to_token: str, amount: str, slippage: float, user_wallet: str) -> Optional[Dict]:
        if chain.lower() == 'solana':
            return await self._get_jupiter_swap(from_token, to_token, amount, slippage, user_wallet)
        
        return await self._get_okx_swap(chain, from_token, to_token, amount, slippage, user_wallet)

    async def _get_jupiter_swap(self, from_token: str, to_token: str, amount: str, slippage: float, user_wallet: str) -> Optional[Dict]:
        """Fetch swap transaction from Jupiter."""
        # 1. Get Quote First (Jupiter requires quoteResponse in swap payload)
        quote = await self._get_jupiter_quote(from_token, to_token, amount, slippage)
        if not quote:
            return None
            
        url = f"{self.JUPITER_URL}/swap"
        payload = {
            'quoteResponse': quote,
            'userPublicKey': user_wallet,
            'wrapAndUnwrapSol': True
        }
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Jupiter returns {'swapTransaction': 'base64str'}
                    return data
                else:
                    text = await response.text()
                    logger.error(f"[JUPITER] Swap Error {response.status}: {text}")
                    return None
        except Exception as e:
            logger.error(f"[JUPITER] Swap Exception: {e}")
            return None

    async def _get_okx_swap(self, chain, from_token, to_token, amount, slippage, user_wallet):
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
