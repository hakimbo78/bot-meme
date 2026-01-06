"""
AUTO-TRADING CONFIGURATION
NOTE: Trading is DISABLED. Bot operates in SIGNAL-ONLY mode.
"""

TRADING_CONFIG = {
    'enabled': False,  # DISABLED - Signal Only Mode
    
    # SIGNAL MODE SETTINGS (NEW)
    'signal_mode': {
        'enabled': True,
        'max_age_hours': 24.0,          # Max age 24 hours (Stable)
        'min_age_hours': 1.0,           # Min age 1 hour (Avoid fresh launch chaos)
        'scan_interval_seconds': 30,    # Scan every 30 seconds
        'min_liquidity': 20000,         # Minimum $20K liquidity for recommendations
        
        # Score Thresholds for Recommendations
        'score_thresholds': {
            'buy': 70,    # Score >= 70: BUY recommendation
            'watch': 50,  # Score 50-69: WATCH recommendation
            # Score < 50: No recommendation (skip)
        },
        
        # Chains to scan
    },
    
    # REBOUND MODE SETTINGS (ATH Recovery Scanner)
    'rebound_mode': {
        'enabled': True,
        'max_age_hours': 720.0,         # Max 30 days old (30 * 24)
        'min_age_hours': 1.0,           # Min 1 hour (same as signal mode)
        'min_ath_drop_percent': 80.0,  # Minimum 80% drop from ATH
        'min_liquidity': 10000,         # Lower threshold for older tokens
        'min_volume_24h': 10000,        # Must have >$10K daily volume (still active)
        
        # Score Thresholds
        'score_thresholds': {
            'rebound': 60,   # Score >= 60: REBOUND recommendation
            # Lower threshold since these are recovery plays
        },
        
        # Activity Filters (ensures token not dead/rugpulled)
        'activity_filters': {
            'min_txn_24h': 50,           # Minimum 50 transactions/day
            'max_holder_drop_percent': 30,  # Max 30% holder decrease (not mass exodus)
        },
        
        # Chains to scan
        'chains': ['solana', 'base', 'ethereum'],
    },
    
    # CHAIN SETTINGS (Dynamic enable/disable)
    'chains': {
        'solana': {
            'enabled': True,
            'rpc_url': 'https://api.mainnet-beta.solana.com',
            'native_token': 'SOL',
            'min_native_balance': 0.01,  # Min SOL for gas
        },
        'base': {
            'enabled': True,
            'rpc_url': 'https://base-mainnet.g.alchemy.com/v2/V1JFM6ky14zmXtFdWdGgm',
            'native_token': 'ETH',
            'min_native_balance': 0.001,  # Min ETH for gas
        },
        'ethereum': {
            'enabled': False,  # Disabled by default (high gas)
            'rpc_url': 'https://eth-mainnet.g.alchemy.com/v2/V1JFM6ky14zmXtFdWdGgm',
            'native_token': 'ETH',
            'min_native_balance': 0.01,
        },
    },
    
    # TRADING SETTINGS - CHAIN TYPE GROUPS
    'trading': {
        # EVM Chains (Base, Ethereum)
        'evm': {
            'budget_per_trade_usd': 5.0,
            'max_open_positions': 1,
            'max_position_per_token': 1,
            'min_signal_score': 55,
            
            # Exit Strategy for EVM
            'exit_strategy': {
                'enabled': True,
                'stop_loss_percent': -999.0,      # DISABLED
                'take_profit_percent': 300.0,     # 3x
                'moonbag_enabled': True,
                'take_profit_sell_percent': 100.0, # Sell 100% at TP
                'moonbag_trailing_stop': True,
                'trailing_stop': False,
                'emergency_exit_liq_drop': 0.50,
            }
        },
        
        # Solana Chain
        'solana': {
            'budget_per_trade_usd': 1.0,
            'max_open_positions': 1,
            'max_position_per_token': 1,
            'min_signal_score': 50,
            
            # Exit Strategy for Solana
            'exit_strategy': {
                'enabled': False,
                'stop_loss_percent': -999.0,      # DISABLED
                'take_profit_percent': 200.0,     # 3x (more aggressive)
                'moonbag_enabled': False,
                'take_profit_sell_percent': 100.0, # Sell 100% at TP (hold more)
                'moonbag_trailing_stop': False,
                'trailing_stop': False,
                'emergency_exit_liq_drop': 0.50,
            }
        },
        
        # Global Settings (backward compatibility)
        'monitor_interval_seconds': 30,
        
        # Re-Buy Prevention (Avoid chasing or dead coins)
        'rebuy_prevention': {
            'enabled': True,
            'min_drop_percent': 85,  # Allow re-buy only if price dropped 85% from exit
        },
    },
    
    # RISK MANAGEMENT (Aggressive)
    'risk': {
        'check_honeypot': True,
        'max_risk_score': 30,  # [DYNAMIC] 0-30=SAFE (Buy), 31-60=WARN, 61+=FAIL
        'max_buy_tax': 15,  # 15% max buy tax (aggressive)
        'max_sell_tax': 15,  # 15% max sell tax (aggressive)
        'min_liquidity_usd': 20000,  # $20K min liquidity
        'max_slippage': 0.05,  # 0.05% max slippage (aggressive)
        'min_liquidity_check': True,
    },
    
    # DEPRECATED - Kept for backward compatibility, will be removed
    'exit_strategy': {
        'enabled': True,
        'stop_loss_percent': -999.0,
        'take_profit_percent': 150.0,
        'moonbag_enabled': True,
        'take_profit_sell_percent': 50.0,
        'moonbag_trailing_stop': True,
        'trailing_stop': False,
        'emergency_exit_liq_drop': 0.50,
        'monitor_interval_seconds': 30,
    },
    
    # DEPRECATED - Kept for backward compatibility, will be removed
    'limits': {
        'auto_take_profit': True,
        'take_profit_percent': 150,
        'auto_stop_loss': True,
        'stop_loss_percent': -50,
    },
    
    # OKX DEX API
    'okx_dex': {
        'base_url': 'https://www.okx.com/api/v5/dex/aggregator',
        'timeout': 10,
    },
    
    # TELEGRAM NOTIFICATIONS
    'telegram': {
        'notify_on_buy': True,
        'notify_on_sell': True,
        'notify_on_limit_trigger': True,
    },
    
    # ----------------------------------------
    # PHASE 3: TRADING STATE MACHINE
    # ----------------------------------------
    'state_machine': {
        'enabled': True,
        
        # 1. PROBE STATE (Initial Entry)
        'probe_size_pct': 50.0,       # Initial buy = 50% of budget (Conservative entry)
        
        # 2. WATCH STATE (Monitoring)
        'trailing_stop_enabled': True,
        'trailing_activation': 20.0,  # Activate trailing stop after +20% profit
        'trailing_distance': 10.0,    # Follow price by -10% distance
        
        # 3. SCALE STATE (Doubling Down)
        'scale_enabled': True,
        'scale_profit_threshold': 20.0, # Must be +20% profit to scale (Winners only)
        'scale_risk_max': 25,         # Risk score must be very low (<25) to scale
        'scale_size_pct': 100.0,      # Buy remaining 50% (Total 100%)
        
        # 4. EXIT RULES
        'emergency_risk_exit': 80,    # Force exit if Risk Score spikes > 80
    },
}


def get_trading_config():
    """Get trading configuration."""
    return TRADING_CONFIG


def is_trading_enabled():
    """Check if trading is enabled."""
    return TRADING_CONFIG.get('enabled', False)


def is_chain_enabled(chain: str):
    """Check if specific chain is enabled for trading."""
    chain_config = TRADING_CONFIG['chains'].get(chain.lower(), {})
    return chain_config.get('enabled', False)
