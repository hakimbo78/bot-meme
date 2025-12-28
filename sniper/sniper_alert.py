"""
Sniper Alert - Enhanced Telegram alerting for sniper mode

COMPLETELY SEPARATE from main telegram_notifier.py
- Uses its own alert history
- Does NOT affect operator alert cooldowns
- Does NOT trigger re-alert logic

Features:
- Distinct format with 🔥🔫⚡ icons
- Operator protocol section
- Safety warning footer
- Optional separate Telegram channel
- Cancelled alert support for kill switch
"""
import asyncio
import time
from typing import Dict, Optional
from telegram import Bot
from telegram.error import TelegramError
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .sniper_config import get_sniper_config, get_sniper_chat_id


class SniperAlert:
    """
    Enhanced Telegram alerting for sniper mode.
    
    Features:
    - Max 1 alert per token (enforced by SniperCooldown)
    - Max alerts per hour limit
    - Separate alert history (isolated from operator)
    - Distinct format with 🔥🔫⚡ icons
    - Operator protocol section
    - Safety warning footer
    - Optional separate channel
    """
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.main_chat_id = TELEGRAM_CHAT_ID
        self.config = get_sniper_config()
        
        # Determine which chat to use
        self.sniper_chat_id = get_sniper_chat_id() or self.main_chat_id
        self.using_separate_channel = self.sniper_chat_id != self.main_chat_id
        
        self.enabled = bool(self.bot_token and self.sniper_chat_id)
        
        # Rate limiting
        self._alerts_this_hour = 0
        self._hour_start = time.time()
        
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
        
        Note: Token-level cooldown is handled by SniperCooldown.
        
        Returns:
            Dict with:
            - can_send: bool
            - reason: str if cannot send
        """
        self._reset_hourly_counter()
        
        max_per_hour = self.config.get('max_alerts_per_hour', 10)
        
        if self._alerts_this_hour >= max_per_hour:
            return {
                'can_send': False,
                'reason': f'Hourly limit reached ({max_per_hour}/hour)'
            }
        
        return {'can_send': True, 'reason': None}
    
    def _format_sniper_message(self, token_data: Dict, score_data: Dict,
                                trigger_result: Dict = None,
                                operator_protocol: Dict = None) -> str:
        """
        Format sniper alert message with distinct styling.
        
        Args:
            token_data: Token analysis data
            score_data: Sniper score data from SniperScoreEngine
            trigger_result: Result from SniperTrigger (optional)
            operator_protocol: Operator protocol from SniperScoreEngine (optional)
        """
        chain_prefix = token_data.get('chain_prefix', '[UNKNOWN]')
        name = token_data.get('name', 'UNKNOWN')
        symbol = token_data.get('symbol', '???')
        address = token_data.get('address', token_data.get('token_address', 'N/A'))
        age = token_data.get('age_minutes', 0)
        liquidity = token_data.get('liquidity_usd', 0)
        
        sniper_score = score_data.get('sniper_score', 0)
        max_score = score_data.get('max_possible', 90)
        risk_level = score_data.get('risk_level', 'UNKNOWN')
        
        # Build condition status if available
        conditions_text = ""
        if trigger_result and trigger_result.get('passed_conditions'):
            conditions = trigger_result.get('passed_conditions', [])
            conditions_text = "✅ *TRIGGER CONDITIONS:*\n"
            for cond in conditions:
                conditions_text += f"• {cond}\n"
            conditions_text += "\n"
        
        # Build operator protocol section
        protocol_text = ""
        if operator_protocol:
            protocol_text = "🎯 *OPERATOR PROTOCOL:*\n"
            protocol_text += f"• Entry Size: {operator_protocol.get('entry_size', '0.1-0.5% max')}\n"
            protocol_text += f"• TP1: {operator_protocol.get('tp1', '+50% (sell 50%)')}\n"
            protocol_text += f"• TP2: {operator_protocol.get('tp2', '+100% (sell 25%)')}\n"
            protocol_text += f"• Stop: {operator_protocol.get('stop_loss', '-20% or kill switch')}\n\n"
        
        # Build warnings section
        risk_flags = score_data.get('risk_flags', [])
        warnings_text = ""
        if risk_flags:
            warnings_text = "⚠️ *WARNINGS:*\n"
            for flag in risk_flags:
                warnings_text += f"• {flag}\n"
            warnings_text += "\n"
        
        # Build score breakdown
        breakdown = score_data.get('score_breakdown', {})
        breakdown_text = ""
        if breakdown:
            breakdown_text = "📈 *Score Breakdown:*\n"
            for k, v in breakdown.items():
                sign = '+' if v >= 0 else ''
                breakdown_text += f"• {k.replace('_', ' ').title()}: {sign}{v}\n"
            breakdown_text += "\n"
        
        message = f"""🔥🔫⚡ {chain_prefix} SNIPER DETECTED ⚡🔫🔥

*Token:* `{name}` ({symbol})
*Address:* `{address}`
*Age:* {age:.1f} min
*Liquidity:* ${liquidity:,.0f}

📊 *SNIPER SCORE:* *{sniper_score}/{max_score}* ({risk_level})

{conditions_text}{breakdown_text}{protocol_text}{warnings_text}🚨 *HIGH RISK - READ ONLY*
_This is informational ONLY._
_NOT investment advice._
_NO execution - manual action required._
"""
        return message
    
    def _format_cancelled_message(self, token_data: Dict, kill_result: Dict) -> str:
        """Format CANCELLED alert message."""
        chain_prefix = token_data.get('chain_prefix', '[UNKNOWN]')
        name = token_data.get('name', 'UNKNOWN')
        symbol = token_data.get('symbol', '???')
        address = token_data.get('address', token_data.get('token_address', 'N/A'))
        
        kill_type = kill_result.get('kill_type', 'UNKNOWN')
        kill_reason = kill_result.get('kill_reason', 'Unknown reason')
        
        message = f"""❌🔫 {chain_prefix} SNIPER CANCELLED ❌

*Token:* `{name}` ({symbol})
*Address:* `{address[:20]}...`

🚨 *Kill Trigger:* {kill_type}
*Reason:* {kill_reason}

⚠️ *DO NOT ENTER* - Risk detected
_Exit immediately if already in position_

🚨 _Automated safety alert - NOT investment advice_
"""
        return message
    
    async def send_sniper_alert_async(self, token_data: Dict, score_data: Dict,
                                       trigger_result: Dict = None,
                                       operator_protocol: Dict = None) -> bool:
        """
        Send sniper alert to Telegram.
        
        Args:
            token_data: Token analysis data
            score_data: Sniper score data from SniperScoreEngine
            trigger_result: Result from SniperTrigger
            operator_protocol: Operator protocol dict
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            print("[SNIPER] Alert: Telegram not enabled")
            return False
        
        # Rate limit check
        check = self.can_send_alert()
        if not check['can_send']:
            print(f"[SNIPER] Alert: Rate limited - {check['reason']}")
            return False
        
        message = self._format_sniper_message(
            token_data, score_data, trigger_result, operator_protocol
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.sniper_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self._alerts_this_hour += 1
            
            if self.using_separate_channel:
                print(f"[SNIPER] Alert: Sent to separate sniper channel")
            else:
                print(f"[SNIPER] Alert: Sent to main channel")
            
            return True
            
        except TelegramError as e:
            print(f"[SNIPER] Alert: Telegram error - {e}")
            return False
    
    async def send_cancelled_alert_async(self, token_data: Dict, 
                                          kill_result: Dict) -> bool:
        """
        Send CANCELLED alert to Telegram.
        
        Args:
            token_data: Token information
            kill_result: Kill result from SniperKillSwitch
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        message = self._format_cancelled_message(token_data, kill_result)
        
        try:
            await self.bot.send_message(
                chat_id=self.sniper_chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            print(f"[SNIPER] Alert: CANCELLED alert sent for {token_data.get('address', 'unknown')[:10]}...")
            return True
            
        except TelegramError as e:
            print(f"[SNIPER] Alert: Telegram error on cancelled alert - {e}")
            return False
    
    def send_sniper_alert(self, token_data: Dict, score_data: Dict,
                           trigger_result: Dict = None,
                           operator_protocol: Dict = None) -> bool:
        """Synchronous wrapper for send_sniper_alert_async."""
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
                self.send_sniper_alert_async(
                    token_data, score_data, trigger_result, operator_protocol
                )
            )
            return result
        except Exception as e:
            print(f"[SNIPER] Alert: Error - {e}")
            return False
    
    def send_cancelled_alert(self, token_data: Dict, kill_result: Dict) -> bool:
        """Synchronous wrapper for send_cancelled_alert_async."""
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
                self.send_cancelled_alert_async(token_data, kill_result)
            )
            return result
        except Exception as e:
            print(f"[SNIPER] Alert: Cancelled alert error - {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get alerting stats."""
        return {
            'alerts_this_hour': self._alerts_this_hour,
            'max_per_hour': self.config.get('max_alerts_per_hour', 10),
            'using_separate_channel': self.using_separate_channel,
            'enabled': self.enabled
        }
