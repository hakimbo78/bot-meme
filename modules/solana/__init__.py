"""
Solana Module - Meme Coin Detection for Solana

This module provides complete Solana meme coin monitoring:
- Pump.fun early detection
- Raydium liquidity confirmation
- Jupiter momentum tracking
- Solana-specific scoring
- Sniper and running detection

CRITICAL: This module must NOT import any EVM adapters.
READ-ONLY: No execution, no wallets, no private keys.


Usage:
    from modules.solana import (
        SolanaScanner,
        SolanaScoreEngine,
        SolanaSniperDetector,
        SolanaRunningDetector,
        SolanaAlert
    )
    
    # Initialize scanner with config from chains.yaml
    scanner = SolanaScanner(config)
    if scanner.connect():
        tokens = scanner.scan_new_pairs()
        
    # Score tokens
    score_engine = SolanaScoreEngine(config)
    for token in tokens:
        score_result = score_engine.calculate_score(token)
"""

# Core scanner components
from .solana_scanner import SolanaScanner
from .pumpfun_scanner import PumpfunScanner
from .raydium_scanner import RaydiumScanner
from .jupiter_scanner import JupiterScanner

# Scoring
from .solana_score_engine import SolanaScoreEngine

# Detection modes
from .solana_sniper import SolanaSniperDetector
from .solana_running_detector import SolanaRunningDetector

# Alerts
from .solana_alert import SolanaAlert

# Utilities
from .solana_utils import (
    # Program IDs
    PUMPFUN_PROGRAM_ID,
    RAYDIUM_AMM_PROGRAM_ID,
    JUPITER_AGGREGATOR_V6,
    
    # Helpers
    create_solana_client,
    get_sol_price_usd,
    sol_to_usd,
    is_valid_solana_address,
    solana_log,
    
    # Thresholds
    SNIPER_MAX_AGE,
    MIN_LIQUIDITY_TRADE,
    BUY_VELOCITY_HIGH
)


__all__ = [
    # Main scanner
    'SolanaScanner',
    
    # Sub-scanners
    'PumpfunScanner',
    'RaydiumScanner', 
    'JupiterScanner',
    
    # Scoring
    'SolanaScoreEngine',
    
    # Detection
    'SolanaSniperDetector',
    'SolanaRunningDetector',
    
    # Alerts
    'SolanaAlert',
    
    # Utilities
    'create_solana_client',
    'get_sol_price_usd',
    'sol_to_usd',
    'is_valid_solana_address',
    'solana_log',
    
    # Constants
    'PUMPFUN_PROGRAM_ID',
    'RAYDIUM_AMM_PROGRAM_ID',
    'JUPITER_AGGREGATOR_V6',
    'SNIPER_MAX_AGE',
    'MIN_LIQUIDITY_TRADE',
    'BUY_VELOCITY_HIGH'
]


# Module version
__version__ = '1.0.0'
