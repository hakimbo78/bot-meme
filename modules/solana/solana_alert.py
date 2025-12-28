"""
Solana Alert Module - Telegram Alert Formatting

Formats and sends Solana-specific alerts:
- SOLANA_SNIPER: High-risk early token alerts
- SOLANA_RUNNING: Post-launch momentum alerts

All alerts include:
- [SOLANA] prefix
- Explicit risk warnings
- Source badge (🧪 Pump.fun, 💧 Raydium, 🪐 Jupiter)

CRITICAL: READ-ONLY - Alerts are informational only
"""
import asyncio
import time
from typing import Dict, Optional

from .solana_utils import solana_log, shorten_address


# Telegram config (uses same as main bot)
try:
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    TELEGRAM_BOT_TOKEN = None
    TELEGRAM_CHAT_ID = None


class SolanaAlert:
    """
    Handles Solana-specific Telegram alerts.
    
    Formats alerts with proper Solana branding and risk warnings.
    """
    
    def __init__(self):
        """Initialize alert sender."""
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        
        # Stats
        self._stats = {
            'sniper_alerts_sent': 0,
            'running_alerts_sent': 0,
            'errors': 0
        }
    
    def _get_source_badge(self, source: str) -> str:
        """Get emoji badge for data source."""
        badges = {
            'pumpfun': '🧪 Pump.fun',
            'raydium': '💧 Raydium',
            'jupiter': '🪐 Jupiter'
        }
        return badges.get(source, source)
    
    def _format_risk_warning(self) -> str:
        """Format standard risk warning."""
        return (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ EXTREME RISK\n"
            "❌ NO EXECUTION\n"
            "📖 READ ONLY — NOT FINANCIAL ADVICE\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
    
    async def send_sniper_alert_async(self, token_data: Dict, sniper_result: Dict) -> bool:
        """
        Send SOLANA_SNIPER alert to Telegram.
        
        Args:
            token_data: Unified token data
            sniper_result: Result from SolanaSniperDetector
            
        Returns:
            True if sent successfully
        """
        if not self.bot_token or not self.chat_id:
            solana_log("Telegram not configured", "WARN")
            return False
        
        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            
            bot = Bot(token=self.bot_token)
            
            # Extract data
            name = token_data.get('name', 'UNKNOWN')
            symbol = token_data.get('symbol', '???')
            token_address = token_data.get('token_address', '')[:16] + '...'
            age_seconds = token_data.get('age_seconds', 0)
            sol_inflow = token_data.get('sol_inflow', 0)
            buy_velocity = token_data.get('buy_velocity', 0)
            sniper_score = sniper_result.get('sniper_score', 0)
            
            # Velocity indicator
            if buy_velocity >= 30:
                velocity_indicator = "🔥 EXTREME"
            elif buy_velocity >= 20:
                velocity_indicator = "⚡ HIGH"
            else:
                velocity_indicator = "📈 ACTIVE"
            
            # Format message
            message = (
                f"🔥🔫⚡ [SOLANA] SNIPER ⚡🔫🔥\n\n"
                f"Token: {name} ({symbol})\n"
                f"Address: `{token_address}`\n"
                f"Source: {self._get_source_badge('pumpfun')}\n\n"
                f"📊 Sniper Score: {sniper_score}/100\n\n"
                f"⏱ Age: {age_seconds}s\n"
                f"💰 SOL Inflow: {sol_inflow:.1f} SOL\n"
                f"🚀 Buy Velocity: {velocity_indicator} ({buy_velocity:.0f}/min)\n\n"
                f"{self._format_risk_warning()}"
            )
            
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._stats['sniper_alerts_sent'] += 1
            solana_log(f"📤 Sniper alert sent: {symbol}")
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            solana_log(f"Sniper alert error: {e}", "ERROR")
            return False
    
    def send_sniper_alert(self, token_data: Dict, sniper_result: Dict) -> bool:
        """Synchronous wrapper for sniper alert."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context
                future = asyncio.ensure_future(
                    self.send_sniper_alert_async(token_data, sniper_result)
                )
                return True  # Optimistic return
            else:
                return loop.run_until_complete(
                    self.send_sniper_alert_async(token_data, sniper_result)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(
                self.send_sniper_alert_async(token_data, sniper_result)
            )
    
    async def send_running_alert_async(self, token_data: Dict, running_result: Dict) -> bool:
        """
        Send SOLANA_RUNNING alert to Telegram.
        
        Args:
            token_data: Unified token data
            running_result: Result from SolanaRunningDetector
            
        Returns:
            True if sent successfully
        """
        if not self.bot_token or not self.chat_id:
            solana_log("Telegram not configured", "WARN")
            return False
        
        try:
            from telegram import Bot
            from telegram.constants import ParseMode
            
            bot = Bot(token=self.bot_token)
            
            # Extract data
            name = token_data.get('name', 'UNKNOWN')
            symbol = token_data.get('symbol', '???')
            token_address = token_data.get('token_address', '')[:16] + '...'
            liquidity_usd = token_data.get('liquidity_usd', 0)
            jupiter_volume = token_data.get('jupiter_volume_24h', 0)
            phase = running_result.get('phase', 'RUNNING')
            running_score = running_result.get('running_score', 0)
            signals = running_result.get('signals', [])
            
            # Phase emoji
            phase_emoji = {
                'RUNNING': '🏃',
                'MOMENTUM': '📈',
                'BREAKOUT': '🚀'
            }.get(phase, '🏃')
            
            # Format signals
            signals_text = '\n'.join(signals) if signals else 'No signals'
            
            # Volume spike indicator
            volume_spike = "YES ✅" if jupiter_volume >= 50000 else "No"
            
            # Format message
            message = (
                f"{phase_emoji} [SOLANA] {phase}\n\n"
                f"Token: {name} ({symbol})\n"
                f"Address: `{token_address}`\n\n"
                f"📊 Running Score: {running_score}/100\n\n"
                f"💧 Liquidity: ${liquidity_usd:,.0f}\n"
                f"🪐 Jupiter Volume: ${jupiter_volume:,.0f}\n"
                f"📈 Volume Spike: {volume_spike}\n\n"
                f"📋 Signals:\n{signals_text}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ HIGH RISK\n"
                "📖 READ ONLY — DYOR\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            self._stats['running_alerts_sent'] += 1
            solana_log(f"📤 Running alert sent: {symbol} ({phase})")
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            solana_log(f"Running alert error: {e}", "ERROR")
            return False
    
    def send_running_alert(self, token_data: Dict, running_result: Dict) -> bool:
        """Synchronous wrapper for running alert."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(
                    self.send_running_alert_async(token_data, running_result)
                )
                return True
            else:
                return loop.run_until_complete(
                    self.send_running_alert_async(token_data, running_result)
                )
        except RuntimeError:
            return asyncio.run(
                self.send_running_alert_async(token_data, running_result)
            )
    
    def get_stats(self) -> Dict:
        """Get alert statistics."""
        return self._stats.copy()
