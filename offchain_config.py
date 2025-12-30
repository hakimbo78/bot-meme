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
# MODE C V2: DEGEN SNIPER CONFIGURATION (OFF-CHAIN FIRST)
DEGEN_SNIPER_CONFIG = {
    'enabled': True,
    'mode_name': 'DEGEN_SNIPER_V2',
    
    'enabled_chains': ['base', 'ethereum', 'solana'],
    
    'dexscreener': {
        'rate_limit_per_minute': 300,
        'min_request_interval_seconds': 0.2,
    },
    
    # ================================================================
    # GLOBAL GUARDRAILS (MANDATORY)
    # ================================================================
    'global_guardrails': {
        'min_liquidity_usd': 5000,          # Increased from 3k
        'require_h24_volume': True,
        'max_age_hours': 24,                # Hard cutoff
    },
    
    # ================================================================
    # SCORING V2 (0-100 Scale)
    # ================================================================
    'scoring_v2': {
        'weights': {
            'liquidity': 0.30,
            'volume': 0.30,
            'price_change': 0.20,
            'tx_count': 0.20
        },
        'thresholds': {
            'low': 25,
            'mid': 40,
            'high': 60,
            'verify': 55  # Trigger on-chain verification
        }
    },
    
    # ================================================================
    # DEDUPLICATION
    # ================================================================
    'deduplication': {
        'pair_cooldown_minutes': 15,    # 15 min pair dedup
        'token_cooldown_minutes': 30,   # 30 min token dedup
    },
    
    # ================================================================
    # TELEGRAM TIERING
    # ================================================================
    'telegram_tiers': {
        'low': {
            'min_score': 25,
            'max_score': 39,
            'rate_limit': 600  # 1 per 10 mins
        },
        'mid': {
            'min_score': 40,
            'max_score': 59,
            'rate_limit': 60   # 1 per 1 min
        },
        'high': {
            'min_score': 60,
            'max_score': 100,
            'rate_limit': 0    # No limit
        }
    },
    
    # ================================================================
    # OUTPUT FORMAT
    # ================================================================
    'output': {
        'include_chain': True,
        'include_pair_address': True,
        'include_metrics': True,
        'include_score': True,
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
