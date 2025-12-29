"""
MODE C: DEGEN SNIPER CONFIGURATION

EXTREMELY AGGRESSIVE off-chain DexScreener filtering for ultra-early detection.

This mode is designed with strict guardrails to avoid spam while catching the earliest movements.

GUARDRAILS:
- No spam alerts
- No dead pairs
- No low-liquidity garbage
- Alerts must be human-actionable

API COMPLIANCE:
- Uses ONLY h1 and h24 metrics (no 5m support)
- 100% DexScreener public API compliant
"""

# MODE C: DEGEN SNIPER Configuration
DEGEN_SNIPER_CONFIG = {
    # Feature flag
    'enabled': True,
    'mode_name': 'DEGEN_SNIPER',
    
    # Enabled chains
    'enabled_chains': ['base', 'ethereum', 'solana'],
    
    # DexScreener API settings
    'dexscreener': {
        'rate_limit_per_minute': 300,
        'min_request_interval_seconds': 0.2,
    },
    
    # ================================================================
    # GLOBAL GUARDRAILS (MANDATORY - REJECT IMMEDIATELY)
    # ================================================================
    'global_guardrails': {
        'min_liquidity_usd': 3000,          # Absolute minimum
        'require_h24_volume': True,          # volume.h24 must be > 0
        'max_age_hours_if_not_trending': 24, # Reject if age > 24h AND not trending
        'require_core_fields': True,         # Must have rank and core DexScreener fields
    },
    
    # ================================================================
    # LEVEL-0: VIABILITY CHECK (VERY LOOSE)
    # ================================================================
    # Purpose: Quick pass if pair shows ANY potential
    # Pass if ANY of these conditions are met:
    'level_0_viability': {
        'min_liquidity_usd': 5000,    # OR liquidity >= $5k
        'min_volume_h24': 2000,       # OR volume.h24 >= $2k
    },
    
    # ================================================================
    # LEVEL-1: EARLY MOMENTUM TRIGGERS (ANY)
    # ================================================================
    # Trigger if ANY early movement detected
    'level_1_momentum': {
        'min_txns_h1': 1,           # OR txns.h1 >= 1
        'min_volume_h1': 10,        # OR volume.h1 >= $10
        'detect_any_price_change_h1': True,  # OR priceChange.h1 != 0
    },
    
    # ================================================================
    # LEVEL-2: STRUCTURAL QUALITY (ANTI-SPAM)
    # ================================================================
    # Require at least 2 of the following to pass
    'level_2_quality': {
        'require_count': 2,  # Need at least 2 conditions to be true
        'conditions': {
            'liquidity_usd': 10000,           # liquidity >= $10k
            'volume_h24': 10000,              # volume.h24 >= $10k
            'txns_h24': 20,                   # txns.h24 >= 20
            'abs_price_change_h24': 5,        # abs(priceChange.h24) >= 5%
        },
    },
    
    # ================================================================
    # BONUS EARLY SIGNALS (add +1 score each)
    # ================================================================
    'bonus_signals': {
        'fresh_lp': {
            'enabled': True,
            'condition': 'liquidity > volume_h24',  # Fresh LP indicator
        },
        'h1_h24_txn_ratio': {
            'enabled': True,
            'min_ratio': 0.2,  # txns.h1 / max(txns.h24, 1) >= 0.2
        },
        'solana_active': {
            'enabled': True,
            'chain': 'solana',
            'min_txns_h24': 10,  # Solana AND txns.h24 >= 10
        },
    },
    
    # ================================================================
    # SCORING SYSTEM
    # ================================================================
    'scoring': {
        'level_1_trigger_points': 1,     # +1 if Level-1 triggered
        'level_2_pass_points': 2,        # +2 if Level-2 passed
        'max_bonus_points': 2,           # Max +2 from bonus signals
        'min_score_to_pass': 3,          # Need score >= 3 to pass
    },
    
    # ================================================================
    # DEDUPLICATION (SMART, NON-SPAM)
    # ================================================================
    'deduplication': {
        'base_cooldown_seconds': 120,  # 2 minutes base cooldown
        
        # Bypass cooldown if ANY of these changes detected:
        'bypass_conditions': {
            'txns_h1_increased': True,              # txns.h1 increased (any amount)
            'volume_h1_increased': 5,               # volume.h1 increased >= $5
            'abs_price_change_h1_delta': 0.1,       # abs(priceChange.h1) changed >= 0.1%
        },
    },
    
    # ================================================================
    # CHAIN-SPECIFIC RULES
    # ================================================================
    'chain_rules': {
        'solana': {
            'ignore_zero_volume_h1': True,  # Don't fail on volume.h1 = 0
            'prefer_txns': True,            # Prefer txns.h24 and liquidity over volume
        },
        'base': {
            'prefer_txns_h1_growth': True,  # Prefer txns.h1 growth
        },
        'ethereum': {
            'min_liquidity_usd': 15000,     # Higher minimum for Ethereum
        },
    },
    
    # ================================================================
    # ALERT RATE LIMITING
    # ================================================================
    'rate_limiting': {
        'max_alerts_per_pair_per_10min': 1,   # Max 1 alert per pair per 10 min
        'max_alerts_per_chain_per_hour': 10,  # Max 10 alerts per chain per hour
    },
    
    # ================================================================
    # OUTPUT FORMAT
    # ================================================================
    'output': {
        'include_chain': True,
        'include_pair_address': True,
        'include_metrics': ['liquidity_usd', 'volume_h1', 'volume_h24', 
                           'txns_h1', 'txns_h24', 'price_change_h1', 'price_change_h24'],
        'include_score': True,
        'include_reason_flags': True,  # EARLY_TX, FRESH_LP, WARMUP, etc.
    },
}


# --- COMPATIBILITY LAYER ---
# Expose standard functions expected by main.py and other modules
# These map directly to the DEGEN_SNIPER config above

def get_offchain_config():
    """
    Get off-chain screener configuration.
    (Aliased to DEGEN SNIPER config for Mode C compatibility)
    """
    return DEGEN_SNIPER_CONFIG


def is_offchain_enabled():
    """
    Check if off-chain screener is enabled.
    (Aliased to DEGEN SNIPER config)
    """
    return DEGEN_SNIPER_CONFIG.get('enabled', False)


# --- MODE-SPECIFIC FUNCTIONS ---

def get_degen_sniper_config():
    """Get DEGEN SNIPER mode configuration."""
    return DEGEN_SNIPER_CONFIG


def is_degen_sniper_enabled():
    """Check if DEGEN SNIPER mode is enabled."""
    return is_offchain_enabled()
