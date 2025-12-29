"""
OFF-CHAIN SCREENER MODULE

Production-grade off-chain gatekeeper for crypto scanner.
Filters ~95% noise before triggering on-chain verification.

GOAL:
- 0 on-chain calls while idle
- Detect viral/top-gainer tokens fast
- Target RPC usage < 5k/day ($5/month budget)

Architecture:
  DEXTools / DexScreener
          ↓
  OFF-CHAIN SCREENER (This Module)
          ↓
  NORMALIZED PAIR EVENT
          ↓
  EXISTING SCORE ENGINE
          ↓
  ON-CHAIN VERIFY (ON DEMAND ONLY)
"""

from .base_screener import BaseScreener
from .dex_screener import DexScreenerAPI
from .dextools_screener import DexToolsAPI
from .normalizer import PairNormalizer
from .filters import OffChainFilter
from .cache import OffChainCache
from .deduplicator import Deduplicator
from .scheduler import OffChainScheduler

__all__ = [
    'BaseScreener',
    'DexScreenerAPI',
    'DexToolsAPI',
    'PairNormalizer',
    'OffChainFilter',
    'OffChainCache',
    'Deduplicator',
    'OffChainScheduler',
]
