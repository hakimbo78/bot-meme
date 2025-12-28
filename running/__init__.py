"""
Running Token Scanner Module

Post-launch rally detection system for tokens that have already launched
but are showing signs of secondary pump / rally.

Features:
- running_config: Configuration and thresholds
- running_score_engine: Scoring logic (separate from TokenScorer)
- running_cooldown: Persistent cooldown (60 min per token)
- running_alert: Enhanced Telegram alerts
- running_scanner: Main orchestration

CRITICAL: This is a READ-ONLY informational system.
NO trading execution. NO private keys. NO wallets.
"""
from .running_config import (
    RUNNING_TOKEN_CONFIG,
    get_running_config,
    is_running_enabled,
    get_score_thresholds,
    get_filter_config,
    enable_running_mode,
    disable_running_mode
)
from .running_score_engine import RunningScoreEngine
from .running_cooldown import RunningCooldown
from .running_alert import RunningAlert
from .running_scanner import RunningScanner


__all__ = [
    # Config
    'RUNNING_TOKEN_CONFIG',
    'get_running_config',
    'is_running_enabled',
    'get_score_thresholds',
    'get_filter_config',
    'enable_running_mode',
    'disable_running_mode',
    # Core classes
    'RunningScoreEngine',
    'RunningCooldown',
    'RunningAlert',
    'RunningScanner'
]
