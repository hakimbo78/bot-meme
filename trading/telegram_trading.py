"""
Telegram Trading Interface
Handles trading-related Telegram commands.
"""

from typing import List, Dict
from .config_manager import ConfigManager
from .db_handler import TradingDB

class TelegramTrading:
    def __init__(self, db: TradingDB):
        self.db = db

    def get_status_message(self) -> str:
        """Get formatted status message."""
        config = ConfigManager.get_config()
        enabled = "✅ ENABLED" if config['enabled'] else "❌ DISABLED"
        
        chains_status = []
        for chain, data in config['chains'].items():
            status = "✅" if data['enabled'] else "❌"
            chains_status.append(f"- {chain.title()}: {status}")
            
        budget = config['trading']['budget_per_trade_usd']
        
        msg = [
            "🤖 **AUTO-TRADING STATUS**",
            f"Status: {enabled}",
            f"Budget: ${budget} per trade",
            "",
            "🔗 **CHAINS**",
            "\n".join(chains_status),
            "",
            "📊 **RISK SETTINGS**",
            f"Max Buy Tax: {config['risk']['max_buy_tax']}%",
            f"Max Slippage: {config['risk']['max_slippage']}%",
            f"Stop Loss: {config['limits']['stop_loss_percent']}%",
            f"Take Profit: {config['limits']['take_profit_percent']}%"
        ]
        return "\n".join(msg)

    def get_positions_message(self) -> str:
        """Get open positions message."""
        positions = self.db.get_open_positions()
        
        if not positions:
            return "📉 No open positions."
            
        msg = ["📊 **OPEN POSITIONS**\n"]
        for p in positions:
            pnl_emoji = "🟢" if (p['pnl_percent'] or 0) >= 0 else "🔴"
            msg.append(
                f"{pnl_emoji} **{p.get('token_symbol', 'UNKNOWN')}** ({p['chain'].upper()})\n"
                f"Entry: ${p['entry_price']:.6f} | Alloc: ${p['entry_value_usd']:.2f}\n"
                f"PnL: {p.get('pnl_percent', 0):.2f}% (${p.get('pnl_usd', 0):.2f})\n"
                f"`{p['token_address']}`\n"
            )
            
        return "\n".join(msg)

    def handle_enable_chain(self, chain: str) -> str:
        if ConfigManager.set_chain_status(chain, True):
            return f"✅ Chain **{chain.upper()}** enabled for trading."
        return f"❌ Unknown chain: {chain}"

    def handle_disable_chain(self, chain: str) -> str:
        if ConfigManager.set_chain_status(chain, False):
            return f"⚠️ Chain **{chain.upper()}** disabled."
        return f"❌ Unknown chain: {chain}"

    def handle_set_budget(self, amount_str: str) -> str:
        try:
            amount = float(amount_str)
            if ConfigManager.set_budget(amount):
                return f"💰 Budget set to **${amount}** per trade."
            return "❌ Invalid budget amount."
        except ValueError:
            return "❌ Please provide a valid number."
