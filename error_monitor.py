"""
Error Monitoring & Health Check Module
Sends critical errors and service status to Telegram
"""
import time
from datetime import datetime
from collections import deque
from typing import Optional
from telegram_notifier import TelegramNotifier

class ErrorMonitor:
    """Monitor and report critical errors to Telegram"""
    
    def __init__(self, notifier: TelegramNotifier, cooldown_seconds: int = 300):
        """
        Args:
            notifier: TelegramNotifier instance
            cooldown_seconds: Minimum seconds between similar error alerts (default: 5 min)
        """
        self.notifier = notifier
        self.cooldown_seconds = cooldown_seconds
        self.error_history = deque(maxlen=100)  # Track last 100 errors
        self.last_error_alert = {}  # {error_key: timestamp}
        
    async def send_startup_alert(self, chains: list, features: dict):
        """Send bot startup notification"""
        try:
            chains_str = ", ".join([c.upper() for c in chains])
            features_str = "\n".join([f"  • {k}: {'✅' if v else '❌'}" for k, v in features.items()])
            
            message = f"""
🚀 **BOT STARTED**

**Chains:** {chains_str}

**Features:**
{features_str}

**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** Monitoring active
"""
            await self.notifier.send_message_async(message)
            print("📱 Startup alert sent to Telegram")
        except Exception as e:
            print(f"⚠️  Failed to send startup alert: {e}")
    
    async def send_error_alert(self, error_type: str, error_message: str, chain: Optional[str] = None):
        """
        Send critical error alert to Telegram with rate limiting
        
        Args:
            error_type: Type of error (e.g., "RPC_CONNECTION", "SCANNER_CRASH")
            error_message: Detailed error message
            chain: Affected chain (optional)
        """
        # Create unique error key for rate limiting
        error_key = f"{error_type}:{chain}" if chain else error_type
        current_time = time.time()
        
        # Check cooldown
        if error_key in self.last_error_alert:
            time_since_last = current_time - self.last_error_alert[error_key]
            if time_since_last < self.cooldown_seconds:
                # Skip duplicate error within cooldown period
                return
        
        # Record error
        self.error_history.append({
            'type': error_type,
            'message': error_message,
            'chain': chain,
            'timestamp': current_time
        })
        
        # Send alert
        try:
            chain_prefix = f"[{chain.upper()}] " if chain else ""
            
            # Fix: Avoid backslash in f-string expression
            clean_message = error_message.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            
            message = f"""
⚠️ *CRITICAL ERROR*

*Type:* {error_type}
*Chain:* {chain_prefix if chain else 'SYSTEM'}
*Message:* {clean_message}

*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Next alert after 5 min cooldown_
"""
            await self.notifier.send_message_async(message)
            self.last_error_alert[error_key] = current_time
            print(f"📱 Error alert sent to Telegram: {error_type}")
        except Exception as e:
            print(f"⚠️  Failed to send error alert: {e}")
    
    async def send_recovery_alert(self, component: str):
        """Send recovery notification"""
        try:
            message = f"""
✅ **SERVICE RECOVERED**

**Component:** {component}
**Status:** Back online
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            await self.notifier.send_message_async(message)
            print(f"📱 Recovery alert sent to Telegram: {component}")
        except Exception as e:
            print(f"⚠️  Failed to send recovery alert: {e}")
    
    async def send_health_report(self, stats: dict):
        """Send periodic health report"""
        try:
            message = f"""
📊 **HEALTH REPORT**

**Scans:** {stats.get('total_scans', 0)}
**Alerts Sent:** {stats.get('total_alerts', 0)}
**Errors (24h):** {stats.get('errors_24h', 0)}

**Chains Status:**
{stats.get('chains_status', 'N/A')}

**Uptime:** {stats.get('uptime', 'N/A')}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            await self.notifier.send_message_async(message)
            print("📱 Health report sent to Telegram")
        except Exception as e:
            print(f"⚠️  Failed to send health report: {e}")
