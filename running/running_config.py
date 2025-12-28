"""
Running Token Scanner Configuration

Configuration for post-launch rally detection.

Filter conditions:
- Age >= 30 minutes (already launched)
- Age <= 180 days (not too old)
- Market Cap: $50k - $50M
- Liquidity >= 2x chain minimum
"""
import os
from pathlib import Path

# Base directory for running module
RUNNING_DIR = Path(__file__).parent

# Running Token Scanner Configuration
RUNNING_TOKEN_CONFIG = {
    # Master switch
    "enabled": True,
    
    # Scan interval in minutes
    "scan_interval_minutes": 3,
    
    # Score thresholds for different alert levels
    "score_thresholds": {
        "WATCH": 60,      # 60-69: Worth watching
        "POTENTIAL": 70,  # 70-79: Potential rally
        "TRADE": 80       # 80+: Strong rally signal
    },
    
    # Cooldown between alerts for same token (minutes)
    "cooldown_minutes": 60,
    
    # Token filters
    "filters": {
        # Minimum age in minutes (must be already launched)
        "min_age_minutes": 30,
        
        # Maximum age in days (not too old)
        "max_age_days": 180,
        
        # Market cap range (USD)
        "min_market_cap_usd": 50000,     # $50k minimum
        "max_market_cap_usd": 50000000,  # $50M maximum
        
        # Liquidity must be at least 2x chain minimum
        "min_liquidity_multiplier": 2.0
    },
    
    # Scoring weights
    "scoring": {
        # Base score contribution (50% weight)
        "base_score_weight": 0.50,
        
        # Momentum confirmation bonus
        "momentum_bonus": 15,
        
        # Volume spike bonus (>2x average)
        "volume_spike_bonus": 10,
        
        # Liquidity growth bonus
        "liquidity_growth_bonus": 10,
        
        # Holder risk penalty (per risk)
        "holder_risk_penalty": 5,
        
        # Dev activity penalty
        "dev_activity_penalty": 10,
        
        # Maximum possible score
        "max_score": 90
    },
    
    # Persistence
    "cooldown_file": str(RUNNING_DIR / "running_cooldown.json"),
    
    # Telegram settings
    "use_separate_channel": False,
    "running_chat_id": os.getenv("TELEGRAM_RUNNING_CHAT_ID", "")
}


def get_running_config():
    """Get running token scanner configuration."""
    return RUNNING_TOKEN_CONFIG.copy()


def is_running_enabled():
    """Check if running token scanner is enabled."""
    return RUNNING_TOKEN_CONFIG.get("enabled", False)


def get_score_thresholds():
    """Get score thresholds for alert classification."""
    return RUNNING_TOKEN_CONFIG.get("score_thresholds", {}).copy()


def get_filter_config():
    """Get filter configuration."""
    return RUNNING_TOKEN_CONFIG.get("filters", {}).copy()


def get_scoring_config():
    """Get scoring weights configuration."""
    return RUNNING_TOKEN_CONFIG.get("scoring", {}).copy()


def is_token_eligible(token_data: dict, chain_config: dict = None) -> dict:
    """
    Check if a token is eligible for running token scanner.
    
    Args:
        token_data: Token analysis data
        chain_config: Chain-specific configuration
        
    Returns:
        Dict with:
        - eligible: bool
        - reason: str (if not eligible)
        - token_age_minutes: float
    """
    filters = get_filter_config()
    
    # Get token age
    age_minutes = token_data.get("age_minutes", 0)
    
    # Check minimum age (>= 30 minutes)
    min_age = filters.get("min_age_minutes", 30)
    if age_minutes < min_age:
        return {
            "eligible": False,
            "reason": f"Token too young: {age_minutes:.1f}m < {min_age}m minimum",
            "token_age_minutes": age_minutes
        }
    
    # Check maximum age (<= 180 days)
    max_age_days = filters.get("max_age_days", 180)
    max_age_minutes = max_age_days * 24 * 60
    if age_minutes > max_age_minutes:
        return {
            "eligible": False,
            "reason": f"Token too old: {age_minutes / 60 / 24:.1f}d > {max_age_days}d maximum",
            "token_age_minutes": age_minutes
        }
    
    # Check market cap range
    market_cap = token_data.get("market_cap_usd", 0)
    min_mcap = filters.get("min_market_cap_usd", 50000)
    max_mcap = filters.get("max_market_cap_usd", 50000000)
    
    if market_cap > 0:  # Only check if market cap is available
        if market_cap < min_mcap:
            return {
                "eligible": False,
                "reason": f"Market cap too low: ${market_cap:,.0f} < ${min_mcap:,}",
                "token_age_minutes": age_minutes
            }
        if market_cap > max_mcap:
            return {
                "eligible": False,
                "reason": f"Market cap too high: ${market_cap:,.0f} > ${max_mcap:,}",
                "token_age_minutes": age_minutes
            }
    
    # Check liquidity vs chain minimum
    liquidity = token_data.get("liquidity_usd", 0)
    liq_multiplier = filters.get("min_liquidity_multiplier", 2.0)
    chain_min_liq = 5000  # Default
    if chain_config:
        chain_min_liq = chain_config.get("min_liquidity_usd", 5000)
    
    required_liq = chain_min_liq * liq_multiplier
    if liquidity < required_liq:
        return {
            "eligible": False,
            "reason": f"Liquidity too low: ${liquidity:,.0f} < ${required_liq:,.0f} ({liq_multiplier}x min)",
            "token_age_minutes": age_minutes
        }
    
    return {
        "eligible": True,
        "reason": None,
        "token_age_minutes": age_minutes
    }


def enable_running_mode():
    """Enable running token scanner at runtime."""
    RUNNING_TOKEN_CONFIG["enabled"] = True


def disable_running_mode():
    """Disable running token scanner at runtime."""
    RUNNING_TOKEN_CONFIG["enabled"] = False
