"""
Uniswap V3 DEX Module for ETH and BASE chains.

Provides V3-specific pool scanning, liquidity calculation, and risk assessment.
Integrates seamlessly with existing scanner loop and risk engine.
"""

from .pool_scanner import UniswapV3PoolScanner
from .liquidity_math import V3LiquidityCalculator
from .v3_risk import V3RiskEngine

__all__ = [
    'UniswapV3PoolScanner',
    'V3LiquidityCalculator',
    'V3RiskEngine'
]