"""
MODE C: DEGEN SNIPER CONFIGURATION

EXTREMELY AGGRESSIVE off-chain filtering for ultra-early detection.
NOW USING GECKOTERMINAL API (time-based queries, no keywords needed).

This mode is designed with strict guardrails to avoid spam while catching the earliest movements.

GUARDRAILS:
- No spam alerts
- No dead pairs
- No low-liquidity garbage
- Alerts must be human-actionable

API COMPLIANCE:
- Uses GeckoTerminal FREE API
- Time-based queries (no keyword search)
- Rate limit: 30 requests/minute
"""

# MODE C V3: DEGEN SNIPER CONFIGURATION (OFF-CHAIN FIRST)
DEGEN_SNIPER_CONFIG = {
    'enabled': True,
    'mode_name': 'DEGEN_SNIPER_V3',
    
    'enabled_chains': ['base', 'ethereum', 'solana'],
    
    # REPLACED: DexScreener -> GeckoTerminal
    'geckoterminal': {
        'rate_limit_per_minute': 30,           # FREE tier limit
        'min_request_interval_seconds': 2.0,   # Conservative (30 req/min = 2s interval)
    },
    
    # ================================================================
    # GLOBAL GUARDRAILS (LEVEL-0)
    # ================================================================
    'global_guardrails': {
        'min_liquidity_usd': 500,           # Ultra loose (Level-0)
        'min_tx_5m': 1,                     # Level-0 rule
        'require_h24_volume': False,        # Not strictly required by Level-0
        'max_age_hours': None,              # Removed for Revival Rule
    },
    
    # ================================================================
    # SCORING V3 (0-100 Scale - Point System)
    # ================================================================
    'scoring_v3': {
        'points': {
            'price_change_5m': 30,
            'price_change_1h': 20,
            'tx_5m': 20,
            'liquidity': 10,
            'volume_24h': 10,
            'revival_bonus': 10
        },
        'thresholds': {
            'low': 30,
            'mid': 45,
            'high': 65,
            'verify': 65  # Trigger on-chain verification
        }
    },
    
    # ================================================================
    # DEDUPLICATION
    # ================================================================
    'deduplication': {
        'pair_cooldown_minutes': 15,    # 15 min pair dedup
        'token_cooldown_minutes': 30,   # 30 min token dedup
        'allow_duplicate_score_threshold': 55 # Allow duplicate if score >= 55
    },
    
    # ================================================================
    # TELEGRAM TIERING
    # ================================================================
    'telegram_tiers': {
        'low': {
            'min_score': 30,
            'max_score': 44,
            'rate_limit': 300  # 1 per 5 mins per chain (approx, exact logic in integration)
        },
        'mid': {
            'min_score': 45,
            'max_score': 64,
            'rate_limit': 0    # Normal alert (no specific rate limit mentioned, assume immediate or standard)
        },
        'high': {
            'min_score': 65,
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
