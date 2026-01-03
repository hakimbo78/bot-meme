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
    
    # NEW: Chain Type Helper
    @staticmethod
    def get_chain_type(chain: str) -> str:
        """Determine if chain is EVM or Solana."""
        evm_chains = ['base', 'ethereum', 'eth']
        return 'evm' if chain.lower() in evm_chains else 'solana'
    
    # UPDATED: Budget (chain-aware)
    @staticmethod
    def set_budget(amount: float, chain: str = None):
        """Set budget for specific chain type or globally."""
        if amount > 0:
            if chain:
                chain_type = ConfigManager.get_chain_type(chain)
                TRADING_CONFIG['trading'][chain_type]['budget_per_trade_usd'] = amount
                logger.info(f"Budget for {chain_type.upper()} set to ${amount}")
            else:
                # Fallback: set both
                TRADING_CONFIG['trading']['evm']['budget_per_trade_usd'] = amount
                TRADING_CONFIG['trading']['solana']['budget_per_trade_usd'] = amount
                logger.info(f"Budget set to ${amount} for all chains")
            return True
        return False
    
    @staticmethod
    def get_budget(chain: str = None) -> float:
        """Get budget for specific chain type."""
        if chain:
            chain_type = ConfigManager.get_chain_type(chain)
            return TRADING_CONFIG['trading'].get(chain_type, {}).get('budget_per_trade_usd', 1.0)
        # Fallback: return EVM budget
        return TRADING_CONFIG['trading'].get('evm', {}).get('budget_per_trade_usd', 1.0)
    
    # NEW: Max Positions (chain-aware)
    @staticmethod
    def get_max_positions(chain: str = None) -> int:
        """Get max open positions for chain type."""
        if chain:
            chain_type = ConfigManager.get_chain_type(chain)
            return TRADING_CONFIG['trading'].get(chain_type, {}).get('max_open_positions', 10)
        return TRADING_CONFIG['trading'].get('evm', {}).get('max_open_positions', 10)
    
    # NEW: Exit Strategy (chain-aware)
    @staticmethod
    def get_exit_strategy(chain: str = None) -> dict:
        """Get exit strategy config for chain type."""
        if chain:
            chain_type = ConfigManager.get_chain_type(chain)
            return TRADING_CONFIG['trading'].get(chain_type, {}).get('exit_strategy', {})
        # Fallback: return global deprecated config
        return TRADING_CONFIG.get('exit_strategy', {})
    
    # NEW: Trading Config (chain-aware)
    @staticmethod
    def get_trading_config(chain: str) -> dict:
        """Get full trading config for specific chain type."""
        chain_type = ConfigManager.get_chain_type(chain)
        return TRADING_CONFIG['trading'].get(chain_type, {})

    @staticmethod
    def get_chain_config(chain: str):
        return TRADING_CONFIG['chains'].get(chain.lower(), {})

