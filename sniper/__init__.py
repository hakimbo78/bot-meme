"""
Sniper Module - Full high-risk early token detection system

This module provides the complete sniper mode functionality:
- sniper_config: Configuration and settings
- sniper_detector: Early token detection and filtering
- sniper_scorer: Legacy basic scoring (kept for backwards compatibility)
- sniper_score_engine: NEW - Advanced scoring engine
- sniper_trigger: NEW - ALL-TRUE trigger evaluation
- sniper_cooldown: NEW - Persistent cooldown (1 alert per token ever)
- sniper_killswitch: NEW - Auto-cancel monitoring
- sniper_alert: Enhanced HIGH RISK Telegram alerts

CRITICAL: Sniper mode is OFF by default.
Enable with --sniper-mode CLI flag.

SAFETY: This is a READ-ONLY informational system.
NO trading execution. NO private keys. NO wallets.
"""
from .sniper_config import (
    SNIPER_CONFIG,
    get_sniper_config,
    is_sniper_enabled,
    is_chain_allowed,
    get_sniper_chat_id,
    enable_sniper_mode,
    disable_sniper_mode
)
from .sniper_detector import SniperDetector
from .sniper_scorer import SniperScorer
from .sniper_score_engine import SniperScoreEngine
from .sniper_trigger import SniperTrigger
from .sniper_cooldown import SniperCooldown
from .sniper_killswitch import SniperKillSwitch
from .sniper_alert import SniperAlert
from .auto_upgrade import AutoUpgradeEngine


__all__ = [
    # Config
    'SNIPER_CONFIG',
    'get_sniper_config',
    'is_sniper_enabled',
    'is_chain_allowed',
    'get_sniper_chat_id',
    'enable_sniper_mode',
    'disable_sniper_mode',
    # Core classes
    'SniperDetector',
    'SniperScorer',  # Legacy
    'SniperScoreEngine',  # NEW
    'SniperTrigger',  # NEW
    'SniperCooldown',  # NEW
    'SniperKillSwitch',  # NEW
    'SniperAlert',
    'AutoUpgradeEngine'  # NEW - TRADE → SNIPER upgrade engine
]

