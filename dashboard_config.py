"""
Dashboard Configuration
Settings for the unified operator dashboard.
"""
import os
from pathlib import Path

# Base directory
DASHBOARD_DIR = Path(__file__).parent

# Dashboard Configuration
DASHBOARD_CONFIG = {
    # Auto-refresh interval (seconds)
    "auto_refresh_seconds": 30,
    
    # Color scheme for modes
    "colors": {
        "sniper": "#FF4B4B",       # Bright red
        "trade": "#28A745",         # Green
        "trade_early": "#FFC107",   # Yellow/Amber
        "running": "#007BFF",       # Blue
        "info": "#6C757D",          # Gray
        "watch": "#17A2B8",         # Cyan
    },
    
    # Mode icons
    "icons": {
        "sniper": "🔥",
        "trade": "🟢",
        "trade_early": "🟡",
        "running": "🔵",
        "info": "ℹ️",
        "watch": "👀",
    },
    
    # Mode descriptions
    "mode_descriptions": {
        "sniper": "High-risk early token detection (< 3 min age)",
        "trade": "Strong signals meeting all criteria",
        "trade_early": "Promising tokens awaiting momentum confirmation",
        "running": "Post-launch rally detection (> 30 min age)",
    },
    
    # Card display limits
    "max_cards_per_page": 20,
    "default_min_score": 0,
    "default_min_liquidity": 0,
    
    # Cooldown file paths
    "cooldown_files": {
        "sniper": DASHBOARD_DIR / "sniper" / "sniper_cooldown.json",
        "running": DASHBOARD_DIR / "running" / "running_cooldown.json",
        "trade_early": DASHBOARD_DIR / "trade_early_cooldown.json",
    },
    
    # Chart settings
    "chart_height": 300,
    "chart_colors": {
        "liquidity": "#00D4FF",
        "momentum": "#FF6B6B",
        "volume": "#4CAF50",
    },
}


def get_dashboard_config():
    """Get dashboard configuration."""
    return DASHBOARD_CONFIG.copy()


def get_color(mode: str) -> str:
    """Get color for a mode."""
    return DASHBOARD_CONFIG["colors"].get(mode.lower(), "#6C757D")


def get_icon(mode: str) -> str:
    """Get icon for a mode."""
    return DASHBOARD_CONFIG["icons"].get(mode.lower(), "📊")


def get_cooldown_path(mode: str) -> Path:
    """Get cooldown file path for a mode."""
    return DASHBOARD_CONFIG["cooldown_files"].get(mode.lower())
