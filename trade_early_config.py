"""
TRADE-EARLY Configuration
Enhanced configuration for early token detection with auto-upgrade capability.

TRADE-EARLY tokens are promising tokens that score in the 60-69 range,
allowing early visibility while awaiting momentum confirmation for upgrade.

When upgrade conditions are met, tokens auto-upgrade to TRADE with re-alert.
"""
import os
from pathlib import Path
from safe_math import safe_div_percentage

# Base directory for cooldown files
TRADE_EARLY_DIR = Path(__file__).parent

# TRADE-EARLY Configuration
TRADE_EARLY_CONFIG = {
    # Master switch
    "enabled": True,
    
    # Score range for TRADE-EARLY classification (inclusive)
    # Tokens scoring 60-69 become TRADE-EARLY
    "score_range": (60, 69),
    
    # Minimum liquidity multiplier relative to chain minimum
    # e.g., 1.5x means if chain min is $10k, token needs $15k
    "min_liquidity_multiplier": 1.5,
    
    # Maximum token age to qualify for TRADE-EARLY (minutes)
    "max_age_minutes": 5,
    
    # Auto-upgrade to TRADE when conditions are met
    "auto_upgrade": True,
    
    # Upgrade conditions - ALL must be met for upgrade
    "upgrade_conditions": {
        # Momentum must be confirmed
        "momentum_confirmed": True,
        
        # Liquidity must grow by this percentage from initial
        "liquidity_growth_pct": 30,
        
        # Score must increase by at least this amount
        "score_increase": 10
    },
    
    # Tracking settings
    "max_tracking_minutes": 15,  # Stop tracking after 15 minutes
    "check_interval_seconds": 30,  # How often to check upgrade conditions
    
    # Cooldown settings
    "cooldown_file": str(TRADE_EARLY_DIR / "trade_early_cooldown.json"),
    "upgrade_cooldown_minutes": 60,  # One upgrade alert per token per hour
}


def get_trade_early_config():
    """Get TRADE-EARLY configuration."""
    return TRADE_EARLY_CONFIG.copy()


def is_trade_early_enabled():
    """Check if TRADE-EARLY mode is enabled."""
    return TRADE_EARLY_CONFIG.get("enabled", True)


def get_score_range():
    """Get the score range for TRADE-EARLY classification."""
    return TRADE_EARLY_CONFIG.get("score_range", (60, 69))


def is_in_trade_early_range(score: int) -> bool:
    """
    Check if score falls within TRADE-EARLY range.
    
    Args:
        score: Token score value
        
    Returns:
        True if score is in TRADE-EARLY range (60-69 by default)
    """
    low, high = get_score_range()
    return low <= score <= high


def get_upgrade_conditions():
    """Get the upgrade conditions dictionary."""
    return TRADE_EARLY_CONFIG.get("upgrade_conditions", {}).copy()


def check_upgrade_eligibility(
    initial_liquidity: float,
    current_liquidity: float,
    initial_score: int,
    current_score: int,
    momentum_confirmed: bool,
    fake_pump: bool = False,
    mev_detected: bool = False,
    dev_flag: str = "SAFE"
) -> dict:
    """
    Check if TRADE-EARLY token is eligible for upgrade to TRADE.
    
    Args:
        initial_liquidity: Liquidity at TRADE-EARLY detection
        current_liquidity: Current liquidity
        initial_score: Score at TRADE-EARLY detection
        current_score: Current score
        momentum_confirmed: Whether momentum is confirmed
        fake_pump: Whether fake pump is detected
        mev_detected: Whether MEV is detected
        dev_flag: Developer activity flag
        
    Returns:
        Dict with:
        - can_upgrade: bool
        - upgrade_reason: str (if can_upgrade)
        - blocked_reasons: list[str] (if cannot upgrade)
        - metrics: dict with computed values
    """
    conditions = get_upgrade_conditions()
    blocked_reasons = []
    metrics = {}
    
    # Calculate metrics
    liq_growth_pct = 0
    if initial_liquidity > 0:
        # SAFE: Prevent division by zero in liquidity growth calculation
        liq_growth_pct = safe_div_percentage(current_liquidity, initial_liquidity, default=0)
    metrics["liquidity_growth_pct"] = liq_growth_pct
    
    score_increase = current_score - initial_score
    metrics["score_increase"] = score_increase
    metrics["momentum_confirmed"] = momentum_confirmed
    
    # Check conditions
    
    # 1. Momentum confirmation
    if conditions.get("momentum_confirmed", True):
        if not momentum_confirmed:
            blocked_reasons.append("Momentum not confirmed")
    
    # 2. Liquidity growth
    required_growth = conditions.get("liquidity_growth_pct", 30)
    if liq_growth_pct < required_growth:
        blocked_reasons.append(f"Liquidity growth {liq_growth_pct:.1f}% < {required_growth}%")
    
    # 3. Score increase
    required_score_inc = conditions.get("score_increase", 10)
    if score_increase < required_score_inc:
        blocked_reasons.append(f"Score increase {score_increase} < {required_score_inc}")
    
    # 4. Safety checks (blocking conditions)
    if fake_pump:
        blocked_reasons.append("Fake pump detected")
    
    if mev_detected:
        blocked_reasons.append("MEV pattern detected")
    
    if dev_flag == "DUMP":
        blocked_reasons.append("Dev DUMP detected")
    
    # Determine result
    can_upgrade = len(blocked_reasons) == 0
    
    result = {
        "can_upgrade": can_upgrade,
        "upgrade_reason": None,
        "blocked_reasons": blocked_reasons,
        "metrics": metrics
    }
    
    if can_upgrade:
        result["upgrade_reason"] = (
            f"Momentum confirmed, liquidity +{liq_growth_pct:.1f}%, "
            f"score +{score_increase}"
        )
    
    return result
