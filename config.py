import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
GOPLUS_API_URL = os.getenv("GOPLUS_API_URL", "https://api.gopluslabs.io/api/v1/token_security/8453")

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Uniswap V2 Factory on Base (and compatible forks like BaseSwap/AlienBase often use similar structures, 
# but for this demo we'll just check Uniswap V2 style events)
UNISWAP_V2_FACTORY = "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6" 

# Basic scoring weights
SCORE_RULES = {
    "LIQUIDITY_GT_20K": 30,
    "RENOUNCED": 20,
    "NO_MINT_BLACKLIST": 20,
    "HOLDERS_TOP10_LT_40": 20,
    "AGE_LT_15_MIN": 10
}

# 3-Level Alert System Thresholds
ALERT_THRESHOLDS = {
    "INFO": 40,   # 40-59: Lower quality signals
    "WATCH": 60,  # 60-74: Medium quality signals
    "TRADE": 75   # 75+: High quality signals
}

# Base-specific filters
MIN_LIQUIDITY_USD = 15000  # Skip tokens below $15k liquidity
EXTREME_HOLDER_CONCENTRATION_THRESHOLD = 95  # Flag if top10 > 95%

# Momentum tracking configuration
MOMENTUM_SNAPSHOTS = 3  # Number of snapshots to collect
MOMENTUM_INTERVAL_BLOCKS = 2  # Block interval between snapshots
MOMENTUM_LIQUIDITY_TOLERANCE = 0.15  # ±15% stability
MOMENTUM_SCORE_MAX = 20  # Maximum bonus points for confirmed momentum
MOMENTUM_CAP_SCORE = 65  # Cap score at this value if momentum not confirmed

# Re-alert settings
REALERT_COOLDOWN_MINUTES = 15
REALERT_SCORE_IMPROVEMENT = 15
REALERT_LIQUIDITY_IMPROVEMENT = 0.30  # 30%
REALERT_MAX_PER_HOUR = 3

# Auto-upgrade settings (TRADE-EARLY → TRADE)
AUTO_UPGRADE_ENABLED = True
AUTO_UPGRADE_COOLDOWN_SECONDS = 30  # Minimum time between upgrades for same token
AUTO_UPGRADE_MAX_WAIT_MINUTES = 10  # Max time to wait for momentum confirmation

# Transaction analysis
TX_ANALYSIS_BLOCKS_BACK = 5  # Analyze last 5 blocks
SWAP_LIQUIDITY_RATIO_THRESHOLD = 0.20  # 20% of liquidity
SWAP_LIQUIDITY_RATIO_THRESHOLD = 0.20  # 20% of liquidity
GAS_SPIKE_MULTIPLIER = 2.0  # 2x average gas is suspicious

# Rotation Engine Config (Market Intelligence)
ROTATION_CONFIG = {
    "window_minutes": 30,
    "min_confidence": 0.65,
    "apply_scoring_bias": True,
    "max_bias_bonus": 5
}

# Pattern Learning Config
PATTERN_CONFIG = {
    "max_patterns": 5000,
    "match_sample": 100,
    "min_similarity": 60,
    "db_path": "data/patterns.db"
}

# Intelligence Layer Config (Phase 5)
NARRATIVE_CONFIG = {
    "min_confidence": 0.7,
    "max_active_narratives": 10,
    "window_hours": 24
}

SMART_MONEY_CONFIG = {
    "tier1_threshold": 3,  # Wins + Early Entries
    "early_window_minutes": 2
}

CONVICTION_CONFIG = {
    "min_display_score": 60,
    "weights": {
        'narrative': 25.0,
        'smart_money': 35.0,
        'rotation': 20.0,
        'pattern': 20.0
    }
}

# Wallet tracking
DEV_WALLET_CHECK_ENABLED = True
SMART_MONEY_CHECK_ENABLED = True
WALLET_AGE_THRESHOLD_DAYS = 30  # Wallets older than this are "not fresh"

# ================================================
# SOLANA PRIORITY DETECTOR CONFIG
# ================================================
PRIORITY_DETECTOR_CONFIG = {
    # Thresholds for priority detection
    "compute_threshold": 200000,  # 200k compute units = high priority
    "priority_fee_threshold": 10000,  # 0.00001 SOL in lamports
    "min_jito_tip": 10000,  # Minimum Jito tip to detect (lamports)
    
    # Scoring weights (max 50 points total)
    "score_compute": 15,  # High compute usage
    "score_priority_fee": 20,  # Priority fee present
    "score_jito_tip": 15,  # Jito tip detected
}

# ================================================
# SOLANA ALCHEMY SAFE MODE (RPC OPTIMIZATION)
# ================================================
SOLANA_ALCHEMY_SAFE_CONFIG = {
    "max_meta_fetch": 10,          # Max transactions to fetch detailed meta for per scan
    "meta_timeout_seconds": 6,    # Timeout per transaction fetch
    "scan_limit_signatures": 50,  # Reduce getSignatures limit to avoid heavy load
    "skip_on_no_meta": True,      # If detailed meta fails, skip fully parsing
    "downgrade_on_timeout": True, # If timeout, log warning and skip instead of crashing
    "retry_attempts": 1,          # Max retries for meta fetch
    "score_penalty_no_meta": -10  # Score penalty if meta is unavailable
}

# ================================================
# SMART WALLET DETECTOR CONFIG
# ================================================
SMART_WALLET_CONFIG = {
    # Database path
    "db_path": "data/smart_wallets.json",
    
    # Tier thresholds
    "tier1_min_success": 0.70,  # 70% win rate for elite tier
    "tier1_min_trades": 10,  # Minimum 10 trades for elite
    "tier2_min_success": 0.50,  # 50% win rate for good tier
    "tier2_min_trades": 5,  # Minimum 5 trades for good tier
    
    # Scoring weights (max 40 points total)
    "score_tier1": 40,  # Elite wallet detected
    "score_tier2": 25,  # Good wallet detected
    "score_tier3": 15,  # Average wallet detected
}

# ================================================
# AUTO-UPGRADE ENGINE (TRADE → SNIPER)
# ================================================
AUTO_UPGRADE_ENGINE_CONFIG = {
    # Enable/disable feature
    "enabled": True,
    
    # Upgrade threshold (final score must meet this)
    "upgrade_threshold": 85,  # 85+ = SNIPER
    
    # Monitoring settings
    "max_monitoring_minutes": 30,  # Stop monitoring after 30 min
    "cooldown_seconds": 300,  # 5 min cooldown between upgrades
    
    # Scoring weights
    "base_weight": 1.0,  # Base score weight
    "priority_weight": 1.0,  # Priority score weight
    "smart_wallet_weight": 1.0,  # Smart wallet score weight
}

# Final score calculation:
# final_score = min(95, base_score + priority_score + smart_wallet_score)
# Upgrade if: final_score >= 85 AND (priority OR smart_wallet detected)

# Multi-chain configuration
CHAINS_CONFIG_PATH = Path(__file__).parent / "chains.yaml"

def load_chain_configs():
    """Load chain configurations from chains.yaml"""
    if CHAINS_CONFIG_PATH.exists():
        with open(CHAINS_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {"chains": {}}

def get_enabled_chains():
    """Return list of enabled chain names"""
    configs = load_chain_configs()
    return [name for name, config in configs.get('chains', {}).items() 
            if config.get('enabled', False)]

# Load chain configs on import
CHAIN_CONFIGS = load_chain_configs()
