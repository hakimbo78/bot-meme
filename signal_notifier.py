"""
Signal Notifier - Recommendation Alert System
Sends BUY and WATCH recommendations to Telegram for signal-only mode.
"""

import asyncio
import logging
from typing import Dict, Optional
from telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class SignalNotifier:
    """
    Signal-Only Recommendation Notifier.
    Handles BUY and WATCH recommendation alerts for the signal bot mode.
    """
    
    # Score thresholds for signal tiers
    SCORE_THRESHOLDS = {
        'BUY': 70,      # Score >= 70: BUY recommendation
        'WATCH': 50,    # Score 50-69: WATCH recommendation
        # Score < 50: No recommendation (skip)
    }
    
    def __init__(self, telegram_notifier: TelegramNotifier):
        self.telegram = telegram_notifier
    
    def get_signal_tier(self, score: float) -> Optional[str]:
        """
        Determine signal tier based on score.
        
        Returns:
            'BUY' for score >= 70
            'WATCH' for score 50-69
            None for score < 50 (no recommendation)
        """
        if score >= self.SCORE_THRESHOLDS['BUY']:
            return 'BUY'
        elif score >= self.SCORE_THRESHOLDS['WATCH']:
            return 'WATCH'
        return None
    
    async def send_recommendation(self, signal_type: str, token_data: dict, score_data: dict, 
                                   security_data: dict = None) -> bool:
        """
        Send appropriate recommendation based on signal type.
        
        Args:
            signal_type: 'BUY', 'WATCH', or 'REBOUND'
            token_data: Token info from DexScreener
            score_data: Scoring result
            security_data: Security audit results (RugCheck/GoPlus)
            
        Returns:
            True if recommendation sent, False otherwise
        """
        if signal_type == 'BUY':
            return await self.send_buy_recommendation(token_data, score_data, security_data)
        elif signal_type == 'WATCH':
            return await self.send_watch_recommendation(token_data, score_data, security_data)
        elif signal_type == 'REBOUND':
            return await self.send_rebound_recommendation(token_data, score_data, security_data)
        else:
            logger.debug(f"Unknown signal type: {signal_type}")
            return False
    
    
    async def send_buy_recommendation(self, token_data: dict, score_data: dict,
                                       security_data: dict = None) -> bool:
        """
        Send BUY RECOMMENDATION alert to Telegram.
        """
        if not self.telegram.enabled:
            return False
        
        try:
            # Extract data
            name = token_data.get('name', 'Unknown')
            symbol = token_data.get('symbol', '???')
            chain = token_data.get('chain', 'UNKNOWN').upper()
            score = score_data.get('final_score', 0)
            
            liquidity = token_data.get('liquidity_usd', 0)
            volume_24h = token_data.get('volume_24h', 0)
            price_change_1h = token_data.get('price_change_h1', 0)
            age_hours = token_data.get('pair_age_hours', 0)
            address = token_data.get('address', token_data.get('token_address', ''))
            
            # Build proper DexScreener URL with chain mapping
            chain_map = {'SOLANA': 'solana', 'BASE': 'base', 'ETHEREUM': 'ethereum', 'ETH': 'ethereum'}
            chain_slug = chain_map.get(chain.upper(), chain.lower())
            # Use 'or' to handle empty string case (not just None)
            dexscreener_url = token_data.get('url') or f"https://dexscreener.com/{chain_slug}/{address}"
            
            # Security data from audit
            lp_locked = security_data.get('lp_locked_percent', 0) if security_data else 0
            lp_burned = security_data.get('lp_burned_percent', 0) if security_data else 0
            top10_holders = security_data.get('top10_holders_percent', 0) if security_data else 0
            honeypot = security_data.get('is_honeypot', False) if security_data else False
            is_mintable = security_data.get('is_mintable', False) if security_data else False
            is_freezable = security_data.get('is_freezable', False) if security_data else False
            risk_level = security_data.get('risk_level', 'UNKNOWN') if security_data else 'UNKNOWN'
            risk_score = security_data.get('risk_score', 50) if security_data else 50
            api_source = security_data.get('api_source', 'N/A') if security_data else 'N/A'
            
            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)} minutes"
            else:
                age_str = f"{age_hours:.1f} hours"
            
            # Security status emoji
            sec_emoji = '✅' if risk_level == 'SAFE' else '⚠️' if risk_level == 'WARN' else '❌'
            
            # Build message with FULL contract address and clickable link
            message = f"""🚀 *BUY RECOMMENDATION* 🚀

🪙 *Token:* {self._escape_md(name)} ({symbol})
🔗 *Chain:* {chain}
📊 *Score:* {score:.0f}/100

📈 *Why Buy?*
• Liquidity: ${liquidity:,.0f}
• Age: {age_str} (Fresh Launch)
• Volume 24h: ${volume_24h:,.0f}
• Price 1h: {'+' if price_change_1h >= 0 else ''}{price_change_1h:.1f}%

🔐 *Security Audit ({api_source.upper()}):* {sec_emoji} {risk_level}
• Risk Score: {risk_score}/100
• Honeypot: {'❌ YES' if honeypot else '✅ NO'}
• Mintable: {'⚠️ YES' if is_mintable else '✅ NO'}
• Freezable: {'⚠️ YES' if is_freezable else '✅ NO'}
• LP Lock: {lp_locked:.0f}% | Burn: {lp_burned:.0f}%
• Top10 Holders: {top10_holders:.1f}%

📝 *Contract:*
`{address}`

🔗 [View on DexScreener]({dexscreener_url})

⚠️ _DYOR - Not financial advice._"""
            
            await self.telegram._enqueue_message(message)
            logger.info(f"📤 [BUY SIGNAL] {symbol} (Score: {score:.0f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send BUY recommendation: {e}")
            return False
    
    async def send_watch_recommendation(self, token_data: dict, score_data: dict,
                                         security_data: dict = None) -> bool:
        """
        Send WATCH RECOMMENDATION alert to Telegram.
        """
        if not self.telegram.enabled:
            return False
        
        try:
            # Extract data
            name = token_data.get('name', 'Unknown')
            symbol = token_data.get('symbol', '???')
            chain = token_data.get('chain', 'UNKNOWN').upper()
            score = score_data.get('final_score', 0)
            
            liquidity = token_data.get('liquidity_usd', 0)
            volume_24h = token_data.get('volume_24h', 0)
            price_change_1h = token_data.get('price_change_h1', 0)
            age_hours = token_data.get('pair_age_hours', 0)
            address = token_data.get('address', token_data.get('token_address', ''))
            
            # Build proper DexScreener URL with chain mapping
            chain_map = {'SOLANA': 'solana', 'BASE': 'base', 'ETHEREUM': 'ethereum', 'ETH': 'ethereum'}
            chain_slug = chain_map.get(chain.upper(), chain.lower())
            # Use 'or' to handle empty string case (not just None)
            dexscreener_url = token_data.get('url') or f"https://dexscreener.com/{chain_slug}/{address}"
            
            # Security data from audit
            lp_locked = security_data.get('lp_locked_percent', 0) if security_data else 0
            lp_burned = security_data.get('lp_burned_percent', 0) if security_data else 0
            top10_holders = security_data.get('top10_holders_percent', 0) if security_data else 0
            is_mintable = security_data.get('is_mintable', False) if security_data else False
            is_freezable = security_data.get('is_freezable', False) if security_data else False
            risk_level = security_data.get('risk_level', 'UNKNOWN') if security_data else 'UNKNOWN'
            risk_score = security_data.get('risk_score', 50) if security_data else 50
            api_source = security_data.get('api_source', 'N/A') if security_data else 'N/A'
            
            # Get risks from audit for "Why Watch" reasons
            audit_risks = security_data.get('risks', []) if security_data else []
            
            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)} minutes"
            else:
                age_str = f"{age_hours:.1f} hours"
            
            # Security status emoji
            sec_emoji = '✅' if risk_level == 'SAFE' else '⚠️' if risk_level == 'WARN' else '❌'
            
            # Determine "Why Watch" reasons - include security risks
            watch_reasons = []
            
            # Add audit risks first
            for r in audit_risks[:2]:
                watch_reasons.append(r.replace('⚠️ ', '').replace('🚨 ', ''))
            
            # Add other reasons
            if lp_locked < 80:
                watch_reasons.append(f"LP Lock {lp_locked:.0f}%")
            if top10_holders > 60:
                watch_reasons.append(f"Top10 {top10_holders:.0f}%")
            if score < 70:
                watch_reasons.append(f"Score {score:.0f}")
            
            if not watch_reasons:
                watch_reasons.append("Borderline - needs confirmation")
            
            reasons_str = ' | '.join(watch_reasons[:3])
            
            # Build message with FULL contract address and clickable link
            message = f"""👀 *WATCH - MONITOR* 👀

🪙 *Token:* {self._escape_md(name)} ({symbol})
🔗 *Chain:* {chain}
📊 *Score:* {score:.0f}/100

📊 *Stats:*
• Liq: ${liquidity:,.0f} | Vol 24h: ${volume_24h:,.0f}
• Age: {age_str} | Price 1h: {'+' if price_change_1h >= 0 else ''}{price_change_1h:.1f}%

⚠️ *Why Watch:* {reasons_str}

🔐 *Security ({api_source.upper()}):* {sec_emoji} {risk_level}
• Honeypot: {'❌' if security_data.get('is_honeypot') else '✅'} | Mint: {'⚠️' if is_mintable else '✅'} | Freeze: {'⚠️' if is_freezable else '✅'}
• LP: {lp_locked:.0f}% Lock | {lp_burned:.0f}% Burn
• Top10: {top10_holders:.0f}%

📝 *Contract:*
`{address}`

🔗 [View on DexScreener]({dexscreener_url})

💡 _Monitor for volume spike or LP improvement._"""
            
            await self.telegram._enqueue_message(message)
            logger.info(f"📤 [WATCH SIGNAL] {symbol} (Score: {score:.0f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WATCH recommendation: {e}")
            return False
    
    async def send_rebound_recommendation(self, token_data: dict, score_data: dict,
                                           security_data: dict = None) -> bool:
        """
        Send REBOUND OPPORTUNITY alert to Telegram (ATH recovery play).
        """
        if not self.telegram.enabled:
            return False
        
        try:
            # Extract data
            symbol = token_data.get('symbol', '???')
            chain = token_data.get('chain', 'UNKNOWN').upper()
            score = score_data.get('score', 0)
            
            liquidity = token_data.get('liquidity', 0)
            volume_24h = token_data.get('volume_24h', 0)
            address = token_data.get('address', '')
            
            # ATH-specific data
            ath = token_data.get('ath', 0)
            ath_drop_pct = token_data.get('ath_drop_percent', 0)
            current_price = token_data.get('price', 0)
            
            # Build URL
            chain_map = {'SOLANA': 'solana', 'BASE': 'base', 'ETHEREUM': 'ethereum'}
            chain_slug = chain_map.get(chain, chain.lower())
            dexscreener_url = f"https://dexscreener.com/{chain_slug}/{address}"
            
            # Security info
            risk_level = security_data.get('risk_level', 'UNKNOWN') if security_data else 'UNKNOWN'
            risk_score = security_data.get('risk_score', 0) if security_data else 0
            
            # Build message
            message = f"🔄 **REBOUND OPPORTUNITY** 🔄\n\n"
            message += f"**Token:** {symbol} ({chain})\n"
            message += f"**Score:** {score}/100\n\n"
            
            message += f"📉 **ATH Analysis:**\n"
            message += f"• All-Time High: ${ath:.8f}\n"
            message += f"• Current Price: ${current_price:.8f}\n"
            message += f"• **Drop from ATH: {ath_drop_pct:.1f}%** 📉\n"
            message += f"• Potential Upside: {((ath/current_price - 1) * 100):.0f}% to ATH\n\n"
            
            message += f"💰 **Market Data:**\n"
            message += f"• Liquidity: ${liquidity:,.0f}\n"
            message += f"• Volume 24h: ${volume_24h:,.0f}\n\n"
            
            message += f"🔐 **Security:** {risk_level} ({risk_score}/100)\n\n"
            
            message += f"⚠️ **Recovery Play Risk Level: HIGH**\n"
            message += f"Only enter if you believe in recovery potential\n\n"
            
            message += f"[View on DexScreener]({dexscreener_url})"
            
            await self.telegram.send_message_async(message)
            return True
            
        except Exception as e:
            logger.error(f"Failed to send REBOUND recommendation: {e}")
            return False
    
    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape special characters for Telegram Markdown V1."""
        if not text:
            return text
        for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(char, f'\\{char}')
        return text


# Singleton instance
_signal_notifier = None

def get_signal_notifier(telegram_notifier: TelegramNotifier = None) -> SignalNotifier:
    """Get or create singleton SignalNotifier instance."""
    global _signal_notifier
    if _signal_notifier is None:
        if telegram_notifier is None:
            raise ValueError("telegram_notifier required for first initialization")
        _signal_notifier = SignalNotifier(telegram_notifier)
    return _signal_notifier
