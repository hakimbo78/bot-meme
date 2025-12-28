"""
Uniswap V3 Liquidity Calculator

Calculates active liquidity for V3 pools using concentrated liquidity math.
Converts to USD using existing ETH price feeds.
"""

import math
from typing import Dict, Optional, Tuple
from web3 import Web3
from web3.contract import Contract


class V3LiquidityCalculator:
    """
    Calculates active liquidity in Uniswap V3 pools.
    Uses slot0 and tick data to compute real liquidity.
    """

    # Uniswap V3 constants
    Q96 = 2**96
    MIN_TICK = -887272
    MAX_TICK = 887272

    def __init__(self, web3_provider: Web3, eth_price_usd: float = 3500):
        self.w3 = web3_provider
        self.eth_price_usd = eth_price_usd

    def calculate_pool_liquidity(self, pool_address: str, token0: str, token1: str, weth_address: str) -> Dict:
        """
        Calculate active liquidity for a V3 pool.

        Returns:
        {
            'liquidity_usd': float,
            'price': float,  # token/WETH price
            'active_liquidity': int,  # raw liquidity value
            'tick': int,  # current tick
            'sqrt_price_x96': int
        }
        """
        try:
            # Create pool contract
            pool_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=[
                    {
                        "inputs": [],
                        "name": "slot0",
                        "outputs": [
                            {"type": "uint160"},  # sqrtPriceX96
                            {"type": "int24"},    # tick
                            {"type": "uint16"},   # observationIndex
                            {"type": "uint16"},   # observationCardinality
                            {"type": "uint16"},   # observationCardinalityNext
                            {"type": "uint8"},    # feeProtocol
                            {"type": "bool"}      # unlocked
                        ],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [],
                        "name": "liquidity",
                        "outputs": [{"type": "uint128"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
            )

            # Get slot0 data
            slot0 = pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]

            # Get raw liquidity
            raw_liquidity = pool_contract.functions.liquidity().call()

            # Calculate price from sqrt_price_x96
            price = self._sqrt_price_x96_to_price(sqrt_price_x96)

            # Determine which token is WETH
            is_token0_weth = token0.lower() == weth_address.lower()
            is_token1_weth = token1.lower() == weth_address.lower()

            if is_token0_weth:
                # token1 per token0 (WETH)
                token_price_usd = self.eth_price_usd / price if price > 0 else 0
            elif is_token1_weth:
                # token0 per token1 (WETH)
                token_price_usd = self.eth_price_usd * price if price > 0 else 0
            else:
                # Neither is WETH - assume token0 is base, token1 is quote
                # This is approximate - would need token prices
                token_price_usd = 0

            # Calculate approximate USD liquidity
            # For concentrated liquidity, this is an approximation
            # Real calculation would need tick range data
            liquidity_usd = self._estimate_liquidity_usd(
                raw_liquidity, sqrt_price_x96, current_tick, token_price_usd, is_token0_weth or is_token1_weth
            )

            return {
                'liquidity_usd': liquidity_usd,
                'price': token_price_usd,
                'active_liquidity': raw_liquidity,
                'tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'success': True
            }

        except Exception as e:
            print(f"⚠️  [V3] Error calculating liquidity for pool {pool_address}: {e}")
            return {
                'liquidity_usd': 0,
                'price': 0,
                'active_liquidity': 0,
                'tick': 0,
                'sqrt_price_x96': 0,
                'success': False,
                'error': str(e)
            }

    def _sqrt_price_x96_to_price(self, sqrt_price_x96: int) -> float:
        """Convert sqrt_price_x96 to human readable price"""
        try:
            return (sqrt_price_x96 / self.Q96) ** 2
        except:
            return 0

    def _estimate_liquidity_usd(self, liquidity: int, sqrt_price_x96: int, tick: int,
                               token_price_usd: float, has_weth: bool) -> float:
        """
        Estimate USD liquidity value.

        This is a simplified approximation for V3 concentrated liquidity.
        Real calculation requires tick range data from positions.
        """
        if not has_weth or token_price_usd == 0:
            return 0

        try:
            # Simplified: assume liquidity is concentrated around current tick
            # Real V3 would sum liquidity across all ticks
            price = self._sqrt_price_x96_to_price(sqrt_price_x96)

            # Estimate token amounts using current price and liquidity
            # This is approximate - V3 math is more complex
            sqrt_price = sqrt_price_x96 / self.Q96
            token0_amount = liquidity * (1 / sqrt_price) / 1e18  # Assume 18 decimals
            token1_amount = liquidity * sqrt_price / 1e18

            # Convert to USD (assuming token1 is WETH if has_weth)
            if has_weth:
                usd_value = token1_amount * self.eth_price_usd
            else:
                usd_value = token0_amount * token_price_usd

            return usd_value

        except Exception:
            return 0