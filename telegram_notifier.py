"""
Telegram Notifier - Enhanced with Security Audit features
Dispatch alerts to Telegram with:
- Re-alert system (improvement tracking)
- Operator hints
- Cooldown management
- Max alerts per token limit
"""
import asyncio
import time
from telegram import Bot
from telegram.error import TelegramError
from config import (
    TELEGRAM_BOT_TOKEN, 
    TELEGRAM_CHAT_ID, 
    ALERT_THRESHOLDS,
    REALERT_COOLDOWN_MINUTES,
    REALERT_SCORE_IMPROVEMENT,
    REALERT_LIQUIDITY_IMPROVEMENT,
    REALERT_MAX_PER_HOUR
)


class TelegramNotifier:
    """
    Enhanced Telegram notifier with re-alert and operator hint support.
    
    Features:
    - Smart re-alerting based on improvements
    - Cooldown timer (default 15 min)
    - Max alerts per token per hour
    - Operator decision hints in messages
    """
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)
        
        # Enhanced alert tracking: {token_address: {timestamp, score, liquidity, count, renounced}}
        self.alert_history = {}
        
        if self.enabled:
            self.bot = Bot(token=self.bot_token)
        else:
            self.bot = None
    
    def _check_realert_eligibility(self, token_address: str, score_data: dict, 
                                    token_data: dict) -> dict:
        """
        Check if token is eligible for re-alert.
        
        Returns:
            Dict with: eligible (bool), is_realert (bool), improvement_type (str)
        """
        token_addr = token_address.lower()
        current_time = time.time()
        
        result = {
            'eligible': True,
            'is_realert': False,
            'improvement_type': None,
            'skip_reason': None
        }
        
        # No history = first alert, always eligible
        if token_addr not in self.alert_history:
            return result
        
        history = self.alert_history[token_addr]
        last_alert_time = history.get('timestamp', 0)
        last_score = history.get('score', 0)
        last_liquidity = history.get('liquidity', 0)
        last_renounced = history.get('renounced', False)
        alert_count = history.get('count', 0)
        
        # Check hourly limit
        hour_ago = current_time - 3600
        if last_alert_time > hour_ago and alert_count >= REALERT_MAX_PER_HOUR:
            result['eligible'] = False
            result['skip_reason'] = f'Max {REALERT_MAX_PER_HOUR} alerts/hour reached'
            return result
        
        # Check cooldown
        cooldown_seconds = REALERT_COOLDOWN_MINUTES * 60
        if current_time - last_alert_time < cooldown_seconds:
            # Still in cooldown - check for significant improvements
            current_score = score_data.get('score', 0)
            current_liquidity = token_data.get('liquidity_usd', 0)
            current_renounced = token_data.get('renounced', False)
            
            score_improved = current_score >= last_score + REALERT_SCORE_IMPROVEMENT
            liquidity_improved = (
                last_liquidity > 0 and 
                current_liquidity >= last_liquidity * (1 + REALERT_LIQUIDITY_IMPROVEMENT)
            )
            renounced_changed = current_renounced and not last_renounced
            
            if score_improved:
                result['is_realert'] = True
                result['improvement_type'] = f'Score +{current_score - last_score}'
            elif liquidity_improved:
                result['is_realert'] = True
                pct = ((current_liquidity - last_liquidity) / last_liquidity) * 100
                result['improvement_type'] = f'Liquidity +{pct:.0f}%'
            elif renounced_changed:
                result['is_realert'] = True
                result['improvement_type'] = 'Ownership renounced'
            else:
                # No significant improvement, skip
                result['eligible'] = False
                result['skip_reason'] = 'In cooldown, no significant improvement'
                return result
        else:
            # Cooldown passed, this is a regular re-alert
            result['is_realert'] = True
            result['improvement_type'] = 'Cooldown expired'
        
        return result
    
    def _update_alert_history(self, token_address: str, score_data: dict, 
                               token_data: dict) -> None:
        """Update alert history for a token."""
        token_addr = token_address.lower()
        current_time = time.time()
        
        if token_addr in self.alert_history:
            hour_ago = current_time - 3600
            if self.alert_history[token_addr].get('timestamp', 0) > hour_ago:
                self.alert_history[token_addr]['count'] += 1
            else:
                self.alert_history[token_addr]['count'] = 1
        else:
            self.alert_history[token_addr] = {'count': 1}
        
        self.alert_history[token_addr].update({
            'timestamp': current_time,
            'score': score_data.get('score', 0),
            'liquidity': token_data.get('liquidity_usd', 0),
            'renounced': token_data.get('renounced', False)
        })
    
    def _format_operator_hint(self, operator_hint: dict) -> str:
        """Format operator hint for message."""
        if not operator_hint:
            return ""
        
        risk_emoji = {
            'HIGH': '🔴',
            'MEDIUM': '🟡',
            'LOW': '🟢'
        }
        
        risk_level = operator_hint.get('risk_level', 'MEDIUM')
        
        return f"""
📋 *Operator Hint:*
• Suggested Entry: {operator_hint.get('suggested_entry', 'N/A')}
• Risk Level: {risk_emoji.get(risk_level, '⚪')} {risk_level}
• Confidence: {operator_hint.get('confidence', 'Snapshot only')}
"""
    
    def _format_security_status(self, score_data: dict, token_data: dict) -> str:
        """Format security validation status for message."""
        lines = []
        
        # Momentum status
        if score_data.get('momentum_confirmed'):
            lines.append("✅ Momentum confirmed")
        else:
            lines.append("⏳ Snapshot only")
        
        # Manipulation checks
        if score_data.get('fake_pump_suspected'):
            lines.append("🚨 Fake pump suspected")
        if score_data.get('mev_pattern_detected'):
            lines.append("🤖 MEV pattern detected")
        
        # Wallet status
        dev_flag = score_data.get('dev_activity_flag', 'UNKNOWN')
        if dev_flag == 'SAFE':
            lines.append("✅ Dev activity: SAFE")
        elif dev_flag == 'WARNING':
            lines.append("⚠️ Dev activity: WARNING")
        elif dev_flag == 'DUMP':
            lines.append("🔴 Dev activity: DUMP")
        
        # Smart money
        if score_data.get('smart_money_involved'):
            lines.append("🧠 Smart money detected")
        
        # Market phase
        phase = score_data.get('market_phase', '')
        if phase:
            phase_emoji = {'launch': '🚀', 'growth': '📈', 'mature': '🏛️'}
            lines.append(f"{phase_emoji.get(phase, '📊')} Phase: {phase.upper()}")
        
        return '\n'.join(['• ' + line for line in lines])
    
    async def send_alert_async(self, token_data, score_data):
        """Send formatted alert to Telegram with enhanced features."""
        if not self.enabled:
            return False
        
        token_address = token_data.get('address')
        
        # Check re-alert eligibility
        eligibility = self._check_realert_eligibility(token_address, score_data, token_data)
        
        if not eligibility['eligible']:
            # print(f"ℹ️  Alert skipped: {eligibility['skip_reason']}")
            return False
        
        # Check score threshold (must be >= INFO level)
        alert_level = score_data.get('alert_level')
        if not alert_level:
            return False
        
        # Alert level emojis
        alert_emojis = {
            "INFO": "🟦",
            "WATCH": "🟨",
            "TRADE-EARLY": "🟧",
            "TRADE": "🟥"
        }
        
        emoji = alert_emojis.get(alert_level, "⚪")
        
        # Get chain prefix (defaults to [BASE] for backward compatibility)
        chain_prefix = token_data.get('chain_prefix', '[BASE]')
        
        # Add V3 tag if Uniswap V3
        dex_tag = ""
        if token_data.get('dex_type') == 'uniswap_v3':
            dex_tag = "[V3] "
        
        # Re-alert indicator
        realert_tag = ""
        if eligibility['is_realert']:
            realert_tag = f"\n🔁 *RE-ALERT* ({eligibility['improvement_type']})"
        
        # Build enhanced message
        operator_hint = score_data.get('operator_hint', {})
        operator_section = self._format_operator_hint(operator_hint)
        security_status = self._format_security_status(score_data, token_data)
        
        # MARKET INTEL: Format insights
        insights_section = ""
        
        # 1. Rotation Bias
        rot_bonus = score_data.get('breakdown', {}).get('rotation_bonus', 0)
        if rot_bonus > 0:
            insights_section += f"🔄 Market Focus: +{rot_bonus} Bias Applied\n"
            
        # 2. Pattern Matching
        pattern = token_data.get('pattern_insight')
        if pattern and pattern.get('confidence_label') != 'NO_MATCH':
            sim = pattern['pattern_similarity']
            conf = pattern['confidence_label']
            outcomes = pattern.get('matched_outcomes', {})
            outcome_str = ", ".join([f"{k} {v}%" for k, v in outcomes.items() if v > 20])
            insights_section += f"🧩 Pattern Match: {sim}% ({conf})\n"
            if outcome_str:
                insights_section += f"   ↳ History: {outcome_str}\n"

        # 3. Phase 5 Intelligence
        narrative = token_data.get('narrative_insight')
        smart_money = token_data.get('smart_money_insight')
        conviction = token_data.get('conviction_insight')
        
        if conviction and conviction.get('conviction_score', 0) > 0:
            score = conviction['conviction_score']
            verdict = conviction['verdict']
            insights_section += f"🧠 Conviction Score: {score}/100 ({verdict})\n"
            
        if narrative and narrative.get('confidence', 0) > 0.6:
             insights_section += f"🌊 Narrative: {narrative['narrative']} ({narrative['trend']})\n"
             
        if smart_money and smart_money.get('tier1_wallets', 0) > 0:
            insights_section += f"🐋 Smart Money: {smart_money['tier1_wallets']} Tier-1 Detected\n"

        if insights_section:
            # Escape special characters for Markdown
            insights_section = insights_section.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
            insights_section = "💡 *Market Intelligence:*\n" + insights_section + "\n"
        
        message = f"""{emoji} *{chain_prefix} {dex_tag}{alert_level} ALERT* {emoji}{realert_tag}

*Token:* `{token_data.get('name')}` ({token_data.get('symbol')})
*Chain:* {chain_prefix}
*Address:* `{token_data.get('address')}`
*Score:* *{score_data['score']}/100*

📊 *Metrics:*
• Age: {token_data.get('age_minutes', 0):.1f} min
• Liquidity: ${token_data.get('liquidity_usd', 0):,.0f}

🔍 *Risk Flags:*
{chr(10).join(['• ' + flag for flag in score_data.get('risk_flags', [])]) if score_data.get('risk_flags') else '• None ✅'}

{insights_section}🛡️ *Security Status:*
{security_status}
{operator_section}
*Verdict:* {score_data['verdict']}

⚠️ _Informational only. No automated trading._
"""
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            # Update alert history
            self._update_alert_history(token_address, score_data, token_data)
            return True
        except TelegramError as e:
            print(f"Telegram send error: {e}")
            return False
    
    def send_alert(self, token_data, score_data):
        """
        Wrapper for send_alert_async.
        Handles both sync and async contexts (though usually called from async context now).
        """
        if not self.enabled:
            return False
            
        try:
            # Check if there is a running loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop and loop.is_running():
                # If we are in a running loop, we should create a task
                # But typically this function is called where we want to await it or fire-and-forget
                # Best practice here since we are in async architecture: 
                # This sync wrapper should ideally NOT be used in async code.
                # However, for compatibility, if we are in a loop, we return a Future or Task
                # But Python sync functions can't return awaitables to sync callers.
                # We will create a background task.
                loop.create_task(self.send_alert_async(token_data, score_data))
                return True
            else:
                # No loop, run sync
                return asyncio.run(self.send_alert_async(token_data, score_data))
                
        except Exception as e:
            print(f"Error sending Telegram alert: {e}")
            return False
    
    def clear_history(self):
        """Clear alert history (for testing or reset)."""
        self.alert_history = {}
    
    def get_alert_count(self, token_address: str) -> int:
        """Get current alert count for a token."""
        token_addr = token_address.lower()
        if token_addr in self.alert_history:
            return self.alert_history[token_addr].get('count', 0)
        return 0
    
    async def send_upgrade_alert_async(self, token_data: dict, original_score_data: dict, 
                                        upgraded_score_data: dict, upgrade_result: dict):
        """
        Send auto-upgrade notification to Telegram.
        
        Args:
            token_data: Token analysis data
            original_score_data: Original TRADE-EARLY score data
            upgraded_score_data: New TRADE score data after upgrade
            upgrade_result: Result from check_auto_upgrade()
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        chain_prefix = token_data.get('chain_prefix', '[BASE]')
        upgrade_reason = upgrade_result.get('upgrade_reason', 'Conditions met')
        
        # Build upgrade message with distinct styling
        message = f"""🔄 *AUTO-UPGRADE* {chain_prefix} 🔄

🟧 TRADE-EARLY → 🟥 *TRADE*

*Token:* `{token_data.get('name')}` ({token_data.get('symbol')})
*Chain:* {chain_prefix}
*Address:* `{token_data.get('address')}`
*Score:* *{upgraded_score_data.get('score', 0)}/100*

📊 *Upgrade Triggered By:*
• {upgrade_reason}
• Liquidity: ${token_data.get('liquidity_usd', 0):,.0f}

{self._format_operator_hint(upgraded_score_data.get('operator_hint', {}))}
🛡️ *Security Status:*
{self._format_security_status(upgraded_score_data, token_data)}

*Verdict:* {upgraded_score_data.get('verdict', 'TRADE')}

⚠️ _Informational only. Manual entry required._
"""
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            # Update alert history
            self._update_alert_history(token_data.get('address', ''), upgraded_score_data, token_data)
            return True
        except TelegramError as e:
            print(f"Telegram upgrade alert error: {e}")
            return False
    
    def send_upgrade_alert(self, token_data: dict, original_score_data: dict,
                           upgraded_score_data: dict, upgrade_result: dict):
        """Synchronous wrapper for send_upgrade_alert_async"""
        if not self.enabled:
            return False
        
        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.send_upgrade_alert_async(token_data, original_score_data, 
                                               upgraded_score_data, upgrade_result)
            )
            return result
        except Exception as e:
            print(f"Error sending Telegram upgrade alert: {e}")
            return False
    
    async def send_trade_early_alert_async(self, token_data: dict, score_data: dict):
        """
        Send TRADE-EARLY alert with pending upgrade conditions.
        
        Args:
            token_data: Token analysis data
            score_data: Current score data with TRADE-EARLY verdict
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        chain_prefix = token_data.get('chain_prefix', '[BASE]')
        
        # Build pending conditions status
        liquidity_usd = token_data.get('liquidity_usd', 0)
        momentum_confirmed = score_data.get('momentum_confirmed', False)
        fake_pump = score_data.get('fake_pump_suspected', False)
        mev_detected = score_data.get('mev_pattern_detected', False)
        dev_flag = score_data.get('dev_activity_flag', 'UNKNOWN')
        
        conditions = []
        conditions.append(f"{'✅' if momentum_confirmed else '❌'} Momentum {'confirmed' if momentum_confirmed else 'not confirmed'}")
        conditions.append(f"✅ Liquidity: ${liquidity_usd:,.0f}")
        conditions.append(f"{'✅' if not fake_pump else '❌'} {'No fake pump' if not fake_pump else 'Fake pump detected'}")
        conditions.append(f"{'✅' if not mev_detected else '❌'} {'No MEV' if not mev_detected else 'MEV detected'}")
        conditions.append(f"{'✅' if dev_flag != 'DUMP' else '❌'} Dev activity: {dev_flag}")
        
        message = f"""🟧 {chain_prefix} *TRADE-EARLY ALERT* 🟧

*Token:* `{token_data.get('name')}` ({token_data.get('symbol')})
*Chain:* {chain_prefix}
*Address:* `{token_data.get('address')}`
*Score:* *{score_data.get('score', 0)}/100*

📊 *Metrics:*
• Age: {token_data.get('age_minutes', 0):.1f} min
• Liquidity: ${liquidity_usd:,.0f}

⏳ *Pending Upgrade Conditions:*
{chr(10).join(['• ' + c for c in conditions])}

{self._format_operator_hint(score_data.get('operator_hint', {}))}
*Verdict:* {score_data.get('verdict', 'TRADE-EARLY')}

⚠️ _Informational only. Monitor for upgrade._
"""
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            self._update_alert_history(token_data.get('address', ''), score_data, token_data)
            return True
        except TelegramError as e:
            print(f"Telegram TRADE-EARLY alert error: {e}")
            return False
    
    def send_trade_early_alert(self, token_data: dict, score_data: dict):
        """Synchronous wrapper for send_trade_early_alert_async"""
        if not self.enabled:
            return False
        
        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                self.send_trade_early_alert_async(token_data, score_data)
            )
            return result
        except Exception as e:
            print(f"Error sending Telegram TRADE-EARLY alert: {e}")
            return False
    
    async def send_message_async(self, message: str) -> bool:
        """
        Send a simple text message to Telegram.
        """
        if not self.enabled:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
        except TelegramError as e:
            print(f"Telegram send error: {e}")
            return False
    
    async def _send_telegram_message(self, message: str):
        """Internal async telegram sender."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except TelegramError as e:
            print(f"Telegram API error: {e}")
