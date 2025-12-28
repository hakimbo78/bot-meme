"""
Intelligence Module

Includes:
- Narrative Engine: Detects rising thematic narratives
- Smart Money Engine: Tracks wallet behaviors and clusters
- Conviction Engine: Fuses intelligence for final scoring
- Market Heat Engine: Adaptive scan speed based on market conditions
"""
from .narrative_engine import NarrativeEngine
from .smart_money_engine import SmartMoneyEngine
from .wallet_cluster import WalletCluster
from .conviction_engine import ConvictionEngine
from .market_heat_engine import MarketHeatEngine

__all__ = ['NarrativeEngine', 'SmartMoneyEngine', 'WalletCluster', 'ConvictionEngine', 'MarketHeatEngine']
