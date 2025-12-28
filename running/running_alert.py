"""
Running Alert - Telegram alerting for running token scanner

COMPLETELY SEPARATE from main telegram_notifier.py and sniper_alert.py
- Uses its own alert history
- Does NOT affect operator alert cooldowns
- Does NOT trigger re-alert logic

Features:
- Distinct format with 🚀 icon
- Score breakdown section
- Risk/opportunity summary
- Safety warning footer
"""
import asyncio
import time
from typing import Dict, Optional
from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .running_config import get_running_config


class RunningAlert:
    """
    Enhanced Telegram alerting for running token scanner.
    
    Features:
    - Cooldown enforcement from RunningCooldown
    - Max alerts per hour limit
    - Separate alert history (isolated from operator)
    - Distinct format with 🚀 icon
    - Opportunity summary section
    """
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.main_chat_id = TELEGRAM_CHAT_ID
        self.config = get_running_config()
        
        # Determine which chat to use
        running_chat = self.config.get("running_chat_id", "")
        use_separate = self.config.get("use_separate_channel", False)
        
        if use_separate and running_chat:
            self.chat_id = running_chat
            self.using_separate_channel = True
        else:
            self.chat_id = self.main_chat_id
            self.using_separate_channel = False
        
        self.enabled = bool(self.bot_token and self.chat_id)
        
        # Rate limiting
        self._alerts_this_hour = 0
        self._hour_start = time.time()
        self._max_per_hour = 20  # Higher limit for running scanner
        
        if self.enabled:
            self.bot = Bot(token=self.bot_token)
        else:
            self.bot = None
    
    def _reset_hourly_counter(self):
        """Reset hourly counter if hour has passed."""
        current_time = time.time()
        if current_time - self._hour_start >= 3600:
            self._alerts_this_hour = 0
            self._hour_start = current_time
    
    def can_send_alert(self) -> Dict:
        """
        Check if we can send an alert (rate limit check).
        
        Note: Token-level cooldown is handled by RunningCooldown.
        
        Returns:
            Dict with:
            - can_send: bool
            - reason: str if cannot send
        """
        self._reset_hourly_counter()
        
        if self._alerts_this_hour >= self._max_per_hour:
            return {
                "can_send": False,
                "reason": f"Hourly limit reached ({self._max_per_hour}/hour)"
            }
        
        return {"can_send": True, "reason": None}
    
    def _format_running_message(self, token_data: Dict, score_data: Dict) -> str:
        """
        Format running alert message with distinct styling.
        
        Args:
            token_data: Token analysis data
            score_data: Running score data from RunningScoreEngine
        """
        chain_prefix = token_data.get("chain_prefix", "[UNKNOWN]")
        name = token_data.get("name", "UNKNOWN")
        symbol = token_data.get("symbol", "???")
        address = token_data.get("address", token_data.get("token_address", "N/A"))
        age = token_data.get("age_minutes", 0)
        liquidity = token_data.get("liquidity_usd", 0)
        
        running_score = score_data.get("running_score", 0)
        max_score = score_data.get("max_possible", 90)
        alert_level = score_data.get("alert_level", "WATCH")
        
        # Format age appropriately
        if age >= 60 * 24:  # More than 1 day
            age_str = f"{age / 60 / 24:.1f} days"
        elif age >= 60:  # More than 1 hour
            age_str = f"{age / 60:.1f} hours"
        else:
            age_str = f"{age:.1f} min"
        
        # Build indicators
        momentum = "✅ CONFIRMED" if score_data.get("momentum_confirmed") else "⏳ Pending"
        volume = "✅ YES" if score_data.get("volume_spike") else "❌ No"
        liq_trend = "📈 Growing" if score_data.get("liquidity_growing") else "➡️ Stable"
        
        # Build score breakdown
        breakdown = score_data.get("score_breakdown", {})
        breakdown_text = ""
        if breakdown:
            breakdown_text = "📊 *Score Breakdown:*\n"
            for k, v in breakdown.items():
                sign = "+" if v >= 0 else ""
                breakdown_text += f"• {k.replace('_', ' ').title()}: {sign}{v}\n"
            breakdown_text += "\n"
        
        # Build warnings section
        risk_flags = score_data.get("risk_flags", [])
        warnings_text = ""
        if risk_flags:
            warnings_text = "⚠️ *Warnings:*\n"
            for flag in risk_flags[:3]:  # Limit to 3
                warnings_text += f"• {flag}\n"
            warnings_text += "\n"
        
        # Alert level emoji
        level_emoji = {
            "TRADE": "🔥",
            "POTENTIAL": "📈",
            "WATCH": "👀"
        }.get(alert_level, "ℹ️")
        
        message = f"""🚀 {chain_prefix} RUNNING {alert_level} {level_emoji}

*Token:* `{name}` ({symbol})
*Address:* `{address}`
*Age:* {age_str}
*Liquidity:* ${liquidity:,.0f}

📊 *RUNNING SCORE:* *{running_score}/{max_score}*

*Momentum:* {momentum}
*Volume Spike:* {volume}
*Liquidity:* {liq_trend}

{breakdown_text}{warnings_text}⚠️ *Informational only*
_NOT investment advice. No execution._
"""
        return message
    
    async def send_running_alert_async(self, token_data: Dict, score_data: Dict) -> bool:
        """
        Send running alert to Telegram.
        
        Args:
            token_data: Token analysis data
            score_data: Running score data from RunningScoreEngine
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            print("[RUNNING] Alert: Telegram not enabled")
            return False
        
        # Rate limit check
        check = self.can_send_alert()
        if not check["can_send"]:
            print(f"[RUNNING] Alert: Rate limited - {check['reason']}")
            return False
        
        message = self._format_running_message(token_data, score_data)
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
            
            self._alerts_this_hour += 1
            
            channel_type = "separate running channel" if self.using_separate_channel else "main channel"
            print(f"[RUNNING] Alert: Sent to {channel_type}")
            
            return True
            
        except TelegramError as e:
            print(f"[RUNNING] Alert: Telegram error - {e}")
            return False
    
    def send_running_alert(self, token_data: Dict, score_data: Dict) -> bool:
        """Synchronous wrapper for send_running_alert_async."""
        if not self.enabled:
            return False
        
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.send_running_alert_async(token_data, score_data)
            )
            return result
        except Exception as e:
            print(f"[RUNNING] Alert: Error - {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get alerting stats."""
        return {
            "alerts_this_hour": self._alerts_this_hour,
            "max_per_hour": self._max_per_hour,
            "using_separate_channel": self.using_separate_channel,
            "enabled": self.enabled
        }
