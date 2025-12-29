"""
OFF-CHAIN SCREENER CONFIGURATION

Configuration template for off-chain screener integration.
"""

# Off-chain screener configuration
OFFCHAIN_SCREENER_CONFIG = {
    # Feature flag
    'enabled': True,
    
    # Enabled chains (BASE, ETHEREUM, SOLANA as requested)
    'enabled_chains': ['base', 'ethereum', 'solana'],
    
    # DEXTools (optional - requires API key) - DISABLED for now
    'dextools_enabled': False,  # Using DexScreener only
    'dextools': {
        'api_key': '',  # Add your DEXTools API key here
        'rate_limit_per_minute': 30,
        'min_request_interval_seconds': 2.0,
    },
    
    # DexScreener (free, always enabled)
    'dexscreener': {
        'rate_limit_per_minute': 300,
        'min_request_interval_seconds': 0.2,
    },
    
    # Filters (AGGRESSIVE MODE - REALISTIC)
    # DexScreener PUBLIC API provides ONLY h1 and h24 metrics
    'filters': {
        # ================================================================
        # LEVEL-0: BASIC VIABILITY (LONGGAR TAPI MASUK AKAL)
        # ================================================================
        # Purpose: Hindari dead/honeypot, bukan cari pump
        'min_liquidity': 10000,  # $10k minimum liquidity (viability check)
        
        # REMOVED hard gates for volume_1h and tx_1h
        # Pairs can pass Level-0 even with volume_1h = 0 or tx_1h = 0
        # as long as they show ANY activity in 24h
        
        'max_age_hours': None,  # DISABLED - Allow old pair revivals
        
        # ================================================================
        # LEVEL-1: AGGRESSIVE MOMENTUM SCORING
        # ================================================================
        # Momentum score thresholds (NOT hard gates)
        'momentum_score_threshold': 3,  # Need >= 3 points to pass
        
        # Scoring weights:
        # volume.h1 >= 50: +2, >= 20: +1
        # txns.h1 >= 3: +2, >= 1: +1
        # priceChange.h1 > 0: +1
        # priceChange.h24 > 5%: +1
        
        # ================================================================
        # LEVEL-2: FAKE LIQUIDITY CHECK
        # ================================================================
        'fake_liq_threshold': 500000,  # $500k liquidity threshold
        'fake_liq_min_volume_24h': 200,  # Require >= $200 vol if liq > 500k
        'fake_liq_min_tx_24h': 10,  # Require >= 10 tx if liq > 500k
        
        # DEXTools guarantee (unchanged)
        'dextools_top_rank': 50,  # Top 50 ranks bypass filters
    },
    
    # Cache
    'cache': {
        'ttl_seconds': 300,  # 5 minutes TTL
        'max_size': 1000,  # Max 1000 cached pairs
    },
    
    # Deduplicator (PRODUCTION - Restored)
    'deduplicator': {
        'cooldown_seconds': 600,  # 10 minutes cooldown (prevents spam)
    },
    
    # Scheduler
    'scheduler': {
        # DexScreener intervals
        'dexscreener_interval_min': 30,  # Minimum 30s between scans
        'dexscreener_interval_max': 60,  # Maximum 60s between scans
        
        # DEXTools intervals (more conservative)
        'dextools_interval_min': 90,  # Minimum 90s between scans
        'dextools_interval_max': 180,  # Maximum 180s between scans
        
        # Adaptive scaling
        'adaptive_scaling': True,
        'activity_threshold': 5,  # Pairs/scan to consider "active"
    },
    
    # Scoring weights for FINAL_SCORE calculation (H1-based)
    'scoring': {
        'offchain_weight': 0.6,  # 60% off-chain score
        'onchain_weight': 0.4,  # 40% on-chain score
        'verify_threshold': 60,  # Trigger on-chain verify if FINAL_SCORE >= 60
        
        # Off-chain score component weights (total = 100%)
        'liquidity_weight': 0.30,  # 30% - liquidity.usd
        'volume_1h_weight': 0.30,  # 30% - volume.h1
        'price_change_1h_weight': 0.25,  # 25% - priceChange.h1
        'tx_1h_weight': 0.15,  # 15% - txns.h1
    },
}


def get_offchain_config():
    """Get off-chain screener configuration."""
    return OFFCHAIN_SCREENER_CONFIG


def is_offchain_enabled():
    """Check if off-chain screener is enabled."""
    return OFFCHAIN_SCREENER_CONFIG.get('enabled', False)
