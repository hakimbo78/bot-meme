"""
AUTO-TRADING CONFIGURATION
"""

TRADING_CONFIG = {
    'enabled': True,  # Master switch
    
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
    
    # TRADING SETTINGS
    'trading': {
        'budget_per_trade_usd': 1.0,  # $1 for safe testing
        'max_open_positions': 1,
        'max_position_per_token': 1,  # Only 1 position per token
        'min_signal_score': 60,  # Only trade MID/HIGH tier
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
    
    # EXIT STRATEGY (Auto Stop-Loss & Take-Profit)
    'exit_strategy': {
        'enabled': True,
        'stop_loss_percent': -50.0,      # Auto-sell at -30% loss
        'take_profit_percent': 150.0,    # Auto-sell at +150% profit
        'trailing_stop': False,           # Trailing stop-loss (future feature)
        'emergency_exit_liq_drop': 0.50, # Exit if liquidity drops >50%
        'monitor_interval_seconds': 30,   # Check every 30 seconds
    },
    
    # AUTO-SELL LIMITS
    'limits': {
        'auto_take_profit': True,
        'take_profit_percent': 150,  # Sell at 150% profit (2x)
        'auto_stop_loss': True,
        'stop_loss_percent': -50,  # Stop loss at -50% (aggressive)
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
