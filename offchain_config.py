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
    
    # Filters (PRODUCTION - H1-BASED ONLY)
    # DexScreener PUBLIC API provides ONLY h1 and h24 metrics
    'filters': {
        # Level-0 thresholds (Quality Gate)
        'min_liquidity': 1000,  # $1,000 minimum liquidity
        'min_volume_1h': 300,  # $300 minimum hourly volume
        'min_tx_1h': 10,  # 10 minimum hourly transactions
        
        'max_age_hours': None,  # DISABLED - Allow old pair revivals (momentum-based)
        
        # Level-1 thresholds (Momentum Detection)
        # Use h1 metrics ONLY - no 5m data available from DexScreener API
        'min_price_change_1h': 5.0,  # 5% price gain in 1h
        'min_volume_spike_ratio': 2.0,  # 2.0x hourly volume spike (h1 vs h24 avg)
        
        # DEXTools guarantee
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
