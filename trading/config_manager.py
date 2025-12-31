"""
Configuration Manager
Handles dynamic updates to trading configuration.
"""

from trading_config import TRADING_CONFIG
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    @staticmethod
    def get_config():
        return TRADING_CONFIG

    @staticmethod
    def is_trading_enabled():
        return TRADING_CONFIG.get('enabled', False)

    @staticmethod
    def enable_trading():
        TRADING_CONFIG['enabled'] = True
        logger.info("Trading ENABLED")

    @staticmethod
    def disable_trading():
        TRADING_CONFIG['enabled'] = False
        logger.info("Trading DISABLED")

    @staticmethod
    def is_chain_enabled(chain: str):
        return TRADING_CONFIG['chains'].get(chain.lower(), {}).get('enabled', False)

    @staticmethod
    def set_chain_status(chain: str, enabled: bool):
        chain = chain.lower()
        if chain in TRADING_CONFIG['chains']:
            TRADING_CONFIG['chains'][chain]['enabled'] = enabled
            status = "ENABLED" if enabled else "DISABLED"
            logger.info(f"Chain {chain.upper()} {status}")
            return True
        return False

    @staticmethod
    def set_budget(amount: float):
        if amount > 0:
            TRADING_CONFIG['trading']['budget_per_trade_usd'] = amount
            logger.info(f"Budget set to ${amount}")
            return True
        return False
    
    @staticmethod
    def get_budget():
        return TRADING_CONFIG['trading']['budget_per_trade_usd']

    @staticmethod
    def get_chain_config(chain: str):
        return TRADING_CONFIG['chains'].get(chain.lower(), {})
