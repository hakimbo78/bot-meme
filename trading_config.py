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
        'budget_per_trade_usd': 2.0,  # $2 for safe testing
        'max_open_positions': 10,
        'max_position_per_token': 1,  # Only 1 position per token
        'min_signal_score': 55,  # Only trade MID/HIGH tier
    },
    
    # RISK MANAGEMENT (Aggressive)
    'risk': {
        'check_honeypot': True,
        'max_buy_tax': 15,  # 15% max buy tax (aggressive)
        'max_sell_tax': 15,  # 15% max sell tax (aggressive)
        'min_liquidity_usd': 2000,  # $2K min liquidity
        'max_slippage': 10,  # 10% max slippage (aggressive)
    },
    
    # AUTO-SELL LIMITS
    'limits': {
        'auto_take_profit': True,
        'take_profit_percent': 100,  # Sell at 100% profit (2x)
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
