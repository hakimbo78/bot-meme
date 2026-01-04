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
    
    async def send_recommendation(self, token_data: dict, score_data: dict, 
                                   security_data: dict = None) -> bool:
        """
        Send appropriate recommendation based on score tier.
        
        Args:
            token_data: Token info from DexScreener
            score_data: Scoring result with 'final_score'
            security_data: Security audit results (RugCheck/GoPlus)
            
        Returns:
            True if recommendation sent, False otherwise
        """
        score = score_data.get('final_score', 0)
        tier = self.get_signal_tier(score)
        
        if tier == 'BUY':
            return await self.send_buy_recommendation(token_data, score_data, security_data)
        elif tier == 'WATCH':
            return await self.send_watch_recommendation(token_data, score_data, security_data)
        else:
            logger.debug(f"Score {score} below WATCH threshold - no recommendation")
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
            dexscreener_url = token_data.get('url', f"https://dexscreener.com/{chain.lower()}/{address}")
            
            # Security data
            lp_locked = security_data.get('lp_locked_percent', 100) if security_data else 100
            top10_holders = security_data.get('top10_holders_percent', 0) if security_data else 0
            honeypot = security_data.get('is_honeypot', False) if security_data else False
            risk_level = security_data.get('risk_level', 'SAFE') if security_data else 'SAFE'
            
            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)} minutes"
            else:
                age_str = f"{age_hours:.1f} hours"
            
            # Build message
            message = f"""🚀 *BUY RECOMMENDATION* 🚀

🪙 *Token:* {self._escape_md(name)} ({symbol})
🔗 *Chain:* {chain}
📊 *Score:* {score:.0f}/100

📈 *Why Buy?*
• Liquidity: ${liquidity:,.0f}
• Age: {age_str} (Fresh Launch)
• Volume 24h: ${volume_24h:,.0f}
• Price Change 1h: {'+' if price_change_1h >= 0 else ''}{price_change_1h:.1f}%
• Risk Level: {risk_level} ✅

🔐 *Security Audit:*
• LP Locked: {lp_locked:.0f}%
• Top 10 Holders: {top10_holders:.1f}%
• Honeypot Check: {'❌ DETECTED' if honeypot else '✅ PASS'}

🔗 [DexScreener]({dexscreener_url})
📝 Contract: `{address[:20]}...{address[-8:]}`

⚠️ _DYOR - This is a recommendation, not financial advice._"""
            
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
            dexscreener_url = token_data.get('url', f"https://dexscreener.com/{chain.lower()}/{address}")
            
            # Security data
            lp_locked = security_data.get('lp_locked_percent', 100) if security_data else 100
            top10_holders = security_data.get('top10_holders_percent', 0) if security_data else 0
            risk_level = security_data.get('risk_level', 'WARN') if security_data else 'WARN'
            
            # Format age
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)} minutes"
            else:
                age_str = f"{age_hours:.1f} hours"
            
            # Determine "Why Watch" reasons based on issues
            watch_reasons = []
            if lp_locked < 90:
                watch_reasons.append(f"LP Lock only {lp_locked:.0f}% (Need 90%+)")
            if top10_holders > 50:
                watch_reasons.append(f"Top 10 Holders: {top10_holders:.1f}% (Concentrated)")
            if liquidity < 20000:
                watch_reasons.append(f"Liquidity ${liquidity:,.0f} (Low)")
            if score < 70:
                watch_reasons.append(f"Score {score:.0f} (Below BUY threshold)")
            
            if not watch_reasons:
                watch_reasons.append("Borderline metrics - needs confirmation")
            
            reasons_str = '\n'.join([f"• {r}" for r in watch_reasons[:3]])
            
            # Build message
            message = f"""👀 *WATCH - MONITOR THIS* 👀

🪙 *Token:* {self._escape_md(name)} ({symbol})
🔗 *Chain:* {chain}
📊 *Score:* {score:.0f}/100

📊 *Potential Indicators:*
• Liquidity: ${liquidity:,.0f}
• Age: {age_str}
• Volume 24h: ${volume_24h:,.0f}
• Price Change 1h: {'+' if price_change_1h >= 0 else ''}{price_change_1h:.1f}%

⚠️ *Why Watch (Not Buy Yet):*
{reasons_str}

🔐 *Security Status:*
• LP Locked: {lp_locked:.0f}%
• Top 10 Holders: {top10_holders:.1f}%
• Risk Level: {risk_level}

🔗 [DexScreener]({dexscreener_url})
📝 Contract: `{address[:20]}...{address[-8:]}`

💡 _Monitor for: Volume spike, LP lock improvement, or holder distribution change._"""
            
            await self.telegram._enqueue_message(message)
            logger.info(f"📤 [WATCH SIGNAL] {symbol} (Score: {score:.0f})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WATCH recommendation: {e}")
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
