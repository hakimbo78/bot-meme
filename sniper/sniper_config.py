"""
Sniper Mode Configuration
Isolated configuration for high-risk early token detection.

CRITICAL: This mode is OFF by default and must be explicitly enabled.
"""
import os
from pathlib import Path

# Base directory for sniper module
SNIPER_DIR = Path(__file__).parent

# Sniper Mode Settings - User Specification Aligned
SNIPER_CONFIG = {
    # ============================================
    # MASTER SWITCH
    # ============================================
    # OFF by default - enable with --sniper-mode CLI flag
    'enabled': False,
    
    # ============================================
    # CORE THRESHOLDS (User Spec)
    # ============================================
    # Minimum base_score from TokenScorer to consider
    'base_score_min': 75,
    
    # Threshold for sniper_score to trigger alert
    'sniper_score_threshold': 80,
    
    # Maximum token age in minutes
    'max_token_age_minutes': 3,
    
    # Liquidity multiplier (relative to chain minimum)
    'liquidity_multiplier': 2.0,
    
    # Allowed market phases for sniper mode
    'allowed_phases': ['launch', 'early_growth'],
    
    # ============================================
    # KILL SWITCH (User Spec)
    # ============================================
    'killswitch': {
        'liquidity_drop_pct': 0.20,  # 20% liquidity drop = cancel
        'score_drop': 15              # 15 point score drop = cancel
    },
    
    # ============================================
    # TELEGRAM
    # ============================================
    'use_separate_channel': True,
    'sniper_chat_id': os.getenv('TELEGRAM_SNIPER_CHAT_ID', ''),
    
    # ============================================
    # PERSISTENCE
    # ============================================
    'cooldown_file': str(SNIPER_DIR / 'sniper_cooldown.json'),
    
    # ============================================
    # LEGACY SETTINGS (for backwards compatibility)
    # ============================================
    'chains_allowed': ['base', 'ethereum', 'blast'],
    'max_alerts_per_hour': 10,
    'min_age_minutes': 0,
    'max_age_minutes': 3,
    'min_liquidity_usd': 2000,
    'min_buys_30s': 5,
    'min_unique_wallets': 3,
    
    # Sniper Score Engine settings (mapped from user spec)
    'sniper_score_min_threshold': 80,
    'sniper_score_max': 90,
    'trigger_base_score_min': 75,
    'trigger_liquidity_multiplier': 2.0,
    'trigger_allowed_phases': ['launch', 'early_growth'],
    'killswitch_liquidity_drop_pct': 0.20,
    'killswitch_score_drop': 15,
}


def get_sniper_config():
    """Get sniper configuration."""
    return SNIPER_CONFIG.copy()


def is_sniper_enabled():
    """Check if sniper mode is enabled."""
    return SNIPER_CONFIG.get('enabled', False)


def is_chain_allowed(chain_name: str) -> bool:
    """Check if chain is allowed for sniper mode."""
    allowed = SNIPER_CONFIG.get('chains_allowed', [])
    return chain_name.lower() in [c.lower() for c in allowed]


def get_sniper_chat_id():
    """
    Get the Telegram chat ID for sniper alerts.
    
    Returns:
        - sniper_chat_id if use_separate_channel is True and sniper_chat_id is set
        - None otherwise (caller should use main chat_id)
    """
    if SNIPER_CONFIG.get('use_separate_channel', False):
        sniper_id = SNIPER_CONFIG.get('sniper_chat_id', '')
        if sniper_id:
            return sniper_id
    return None


def enable_sniper_mode():
    """Enable sniper mode at runtime."""
    SNIPER_CONFIG['enabled'] = True


def disable_sniper_mode():
    """Disable sniper mode at runtime."""
    SNIPER_CONFIG['enabled'] = False
