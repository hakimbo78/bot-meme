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
    
    # Filters
    'filters': {
        # Level-0 thresholds
        'min_liquidity': 5000,  # $5k minimum liquidity
        'min_volume_5m': 1000,  # $1k volume in 5 minutes
        'min_tx_5m': 5,  # Minimum 5 transactions
        'max_age_hours': 24,  # Only pairs < 24 hours old
        
        # Level-1 thresholds
        'min_price_change_5m': 20.0,  # 20% price gain in 5m
        'min_price_change_1h': 50.0,  # 50% price gain in 1h
        'min_volume_spike_ratio': 2.0,  # 2x volume spike
        
        # DEXTools guarantee
        'dextools_top_rank': 50,  # Top 50 ranks bypass filters
    },
    
    # Cache
    'cache': {
        'ttl_seconds': 300,  # 5 minutes TTL
        'max_size': 1000,  # Max 1000 cached pairs
    },
    
    # Deduplicator
    'deduplicator': {
        'cooldown_seconds': 600,  # 10 minutes cooldown
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
    
    # Scoring weights for FINAL_SCORE calculation
    'scoring': {
        'offchain_weight': 0.6,  # 60% off-chain score
        'onchain_weight': 0.4,  # 40% on-chain score
        'verify_threshold': 60,  # Trigger on-chain verify if FINAL_SCORE >= 60
    },
}


def get_offchain_config():
    """Get off-chain screener configuration."""
    return OFFCHAIN_SCREENER_CONFIG


def is_offchain_enabled():
    """Check if off-chain screener is enabled."""
    return OFFCHAIN_SCREENER_CONFIG.get('enabled', False)
