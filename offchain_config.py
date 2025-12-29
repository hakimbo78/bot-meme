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
    
    # Filters (DIAGNOSTIC MODE - Lowered to see what's being filtered)
    # Note: API now pre-filters $0 volume and <$500 liquidity
    'filters': {
        # Level-0 thresholds (basic quality gates)
        'min_liquidity': 500,  # $500 (API already filters <$500)
        'min_volume_5m': 10,  # $10 volume (LOWERED for diagnostic)
        'min_tx_5m': 2,  # Minimum 2 transactions
        'max_age_hours': 999999,  # DISABLED - Allow old pair revivals (DexScreener detects activity)
        
        # Level-1 thresholds (LOWERED FOR DIAGNOSTIC)
        'min_price_change_5m': 0.1,  # 0.1% (was 10%) - DIAGNOSTIC
        'min_price_change_1h': 0.5,  # 0.5% (was 20%) - DIAGNOSTIC
        'min_volume_spike_ratio': 0.1,  # 0.1x (was 1.5x) - DIAGNOSTIC
        
        # DEXTools guarantee
        'dextools_top_rank': 50,  # Top 50 ranks bypass filters
    },
    
    # Cache
    'cache': {
        'ttl_seconds': 300,  # 5 minutes TTL
        'max_size': 1000,  # Max 1000 cached pairs
    },
    
    # Deduplicator (DISABLED for testing - was 600s)
    'deduplicator': {
        'cooldown_seconds': 0,  # DISABLED - Allow re-evaluation every scan (testing only!)
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
