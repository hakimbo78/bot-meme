"""
Telegram Alert Extensions for Auto-Upgrade Features

Additional alert methods for TRADE → SNIPER upgrades.
Import and use these alongside the main TelegramNotifier class.
"""

import asyncio
from telegram.error import TelegramError


async def send_sniper_upgrade_alert_async(notifier, token_data: dict, original_score_data: dict,
                                          final_score_data: dict, upgrade_info: dict):
    """
    Send TRADE → SNIPER auto-upgrade alert to Telegram.
    
    Args:
        notifier: TelegramNotifier instance
        token_data: Token analysis data
        original_score_data: Original TRADE score data
        final_score_data: Final score after priority/smart wallet signals
        upgrade_info: Dict from auto_upgrade engine with:
            - should_upgrade: bool
            - final_score: int
            - upgrade_reasons: List[str]
            - score_breakdown: Dict
    
    Returns:
        True if sent successfully
    """
    if not notifier.enabled:
        return False
    
    chain_prefix = token_data.get('chain_prefix', '[SOL]')
    
    # Extract score breakdown
    breakdown = upgrade_info.get('score_breakdown', {})
    base_score = breakdown.get('base_score', 0)
    priority_score = breakdown.get('priority_score', 0)
    smart_wallet_score = breakdown.get('smart_wallet_score', 0)
    final_score = breakdown.get('final_score', 0)
    
    # Format upgrade reasons
    reasons = upgrade_info.get('upgrade_reasons', [])
    reasons_text = '\n'.join(['• ' + r for r in reasons]) if reasons else '• Threshold met'
    
    # Build score evolution display
    score_evolution = f"{base_score} (base)"
    if priority_score > 0:
        score_evolution += f" + {priority_score} (priority)"
    if smart_wallet_score > 0:
        score_evolution += f" + {smart_wallet_score} (smart wallet)"
    score_evolution += f" = *{final_score}*"
    
    # Format security status
    security_lines = []
    if final_score_data.get('momentum_confirmed'):
        security_lines.append("✅ Momentum confirmed")
    if priority_score > 0:
        security_lines.append(f"⚡ Priority TX signals detected")
    if smart_wallet_score > 0:
        security_lines.append(f"🐋 Smart money detected")
    security_text = '\n'.join(['• ' + line for line in security_lines])
    
    message = f"""🎯 *AUTO-UPGRADE: TRADE → SNIPER* 🎯
{chain_prefix}

🟥 TRADE → 🔥 *SNIPER MODE*

*Token:* `{token_data.get('name')}` ({token_data.get('symbol')})
*Chain:* {chain_prefix}
*Address:* `{token_data.get('address')}`

📊 *Score Evolution:*
{score_evolution}

🚨 *Upgrade Triggers:*
{reasons_text}

📈 *Metrics:*
• Age: {token_data.get('age_minutes', 0):.1f} min
• Liquidity: ${token_data.get('liquidity_usd', 0):,.0f}
• Final Score: *{final_score}/95*

🛡️ *Signals:*
{security_text}

*Verdict:* SNIPER - High Priority Signal

⚠️ _READ-ONLY: Manual analysis required. NO execution._
"""
    
    try:
        await notifier.bot.send_message(
            chat_id=notifier.chat_id,
            text=message,
            parse_mode='Markdown'
        )
        # Update alert history
        notifier._update_alert_history(token_data.get('address', ''), final_score_data, token_data)
        return True
    except TelegramError as e:
        print(f"Telegram SNIPER upgrade alert error: {e}")
        return False


def send_sniper_upgrade_alert(notifier, token_data: dict, original_score_data: dict,
                               final_score_data: dict, upgrade_info: dict):
    """Synchronous wrapper for send_sniper_upgrade_alert_async"""
    if not notifier.enabled:
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
            send_sniper_upgrade_alert_async(notifier, token_data, original_score_data,
                                            final_score_data, upgrade_info)
        )
        return result
    except Exception as e:
        print(f"Error sending Telegram SNIPER upgrade alert: {e}")
        return False
