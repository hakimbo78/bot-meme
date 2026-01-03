"""
Telegram Command Handler
Handles interactive bot commands for trade monitoring
"""

import asyncio
import aiohttp
import logging
import os
from typing import Optional, Dict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class TelegramCommandHandler:
    """Handle Telegram bot commands for trade monitoring."""
    
    def __init__(self, position_tracker, trade_executor, telegram_notifier):
        """
        Initialize command handler.
        
        Args:
            position_tracker: PositionTracker instance for position data
            trade_executor: TradeExecutor instance for executing sells
            telegram_notifier: TelegramNotifier for sending responses
        """
        self.position_tracker = position_tracker
        self.trade_executor = trade_executor
        self.telegram = telegram_notifier
        
        # Load Telegram config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip().strip('"').strip("'")
        self.authorized_chat_id = os.getenv('TELEGRAM_CHAT_ID', '').strip().strip('"').strip("'")
        
        if not self.bot_token or not self.authorized_chat_id:
            logger.warning("Telegram bot token or chat ID missing. Commands disabled.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Telegram commands enabled for chat {self.authorized_chat_id}")
        
        # Track last update ID to avoid processing duplicates
        self.last_update_id = 0
        self.poll_interval = 2.0  # Poll every 2 seconds
        
    async def start_polling(self):
        """Start polling for commands (runs as background task)."""
        if not self.enabled:
            logger.info("Command handler disabled (missing config)")
            return
            
        logger.info("📱 Telegram command handler started")
        
        while True:
            try:
                await self._poll_updates()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Command polling error: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _poll_updates(self):
        """Poll Telegram for new messages."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 1,
                'allowed_updates': ['message']
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status != 200:
                        return
                    
                    data = await resp.json()
                    
                    if not data.get('ok'):
                        return
                    
                    updates = data.get('result', [])
                    
                    for update in updates:
                        self.last_update_id = max(self.last_update_id, update['update_id'])
                        await self._process_update(update)
                        
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue polling
        except Exception as e:
            logger.debug(f"Poll update error: {e}")
    
    async def _process_update(self, update: dict):
        """Process a single update."""
        try:
            message = update.get('message')
            if not message:
                return
            
            chat_id = str(message.get('chat', {}).get('id', ''))
            text = message.get('text', '').strip()
            
            # Security: Only respond to authorized chat
            if chat_id != self.authorized_chat_id:
                logger.warning(f"Ignored command from unauthorized chat: {chat_id}")
                return
            
            # Ignore non-command messages
            if not text.startswith('/'):
                return
            
            # Parse command
            parts = text.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            logger.info(f"📨 Received command: {command} {args}")
            
            # Route to handler
            if command == '/positions':
                await self._handle_positions()
            elif command == '/summary':
                await self._handle_summary()
            elif command == '/close':
                await self._handle_close(args)
            elif command == '/help' or command == '/start':
                await self._handle_help()
            else:
                await self._send_response(f"❓ Unknown command: {command}\nSend /help for available commands")
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            await self._send_response(f"❌ Error processing command: {str(e)}")
    
    async def _handle_positions(self):
        """Handle /positions command."""
        try:
            positions = self.position_tracker.get_open_positions()
            
            if not positions:
                await self._send_response("📭 No open positions")
                return
            
            response = f"📊 *OPEN POSITIONS ({len(positions)})*\n\n"
            
            for pos in positions:
                pos_id = pos.get('id', '?')
                chain = pos.get('chain', '?').upper()
                token_addr = pos.get('token_address', 'Unknown')
                token_short = f"{token_addr[:6]}...{token_addr[-4:]}" if len(token_addr) > 10 else token_addr
                
                entry_val = pos.get('entry_value_usd', 0)
                current_val = pos.get('current_value_usd', 0)
                pnl_usd = pos.get('pnl_usd', 0)
                pnl_pct = pos.get('pnl_percent', 0)
                status = pos.get('status', 'OPEN')
                high_pnl = pos.get('high_pnl', 0)
                
                # Format status for display (remove underscores)
                status_display = status.replace('_', ' ')
                
                # Status emoji
                status_emoji = "🌙" if "PARTIAL" in status or "MOONBAG" in status else "📈"
                pnl_emoji = "🟢" if pnl_usd >= 0 else "🔴"
                
                response += f"*#{pos_id}* - {chain} | `{token_short}`\n"
                response += f"💰 Entry: ${entry_val:.2f}\n"
                
                # If current_value is 0 or very stale, indicate price is updating
                if current_val == 0 or abs(pnl_pct) > 99:
                    response += f"📈 Current: Updating... ⏳\n"
                else:
                    response += f"📈 Current: ${current_val:.2f} ({pnl_emoji}{pnl_pct:+.1f}%)\n"
                
                if status != 'OPEN':
                    response += f"Status: {status_display} {status_emoji}\n"
                if high_pnl > 0:
                    response += f"High PnL: {high_pnl:.1f}%\n"
                
                response += "\n"
            
            # Portfolio total
            total_entry = sum(p.get('entry_value_usd', 0) for p in positions)
            total_current = sum(p.get('current_value_usd', 0) for p in positions)
            total_pnl = total_current - total_entry
            total_pnl_pct = (total_pnl / total_entry * 100) if total_entry > 0 else 0
            
            response += f"💼 *Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)*"
            
            await self._send_response(response)
            
        except Exception as e:
            logger.error(f"Error in /positions: {e}")
            await self._send_response(f"❌ Error fetching positions: {str(e)}")
    
    async def _handle_summary(self):
        """Handle /summary command."""
        try:
            positions = self.position_tracker.get_open_positions()
            
            if not positions:
                await self._send_response("📭 No open positions to summarize")
                return
            
            # Calculate totals
            total_entry = sum(p.get('entry_value_usd', 0) for p in positions)
            total_current = sum(p.get('current_value_usd', 0) for p in positions)
            total_pnl = total_current - total_entry
            total_pnl_pct = (total_pnl / total_entry * 100) if total_entry > 0 else 0
            
            # Find best/worst
            best_pos = max(positions, key=lambda p: p.get('pnl_percent', 0))
            worst_pos = min(positions, key=lambda p: p.get('pnl_percent', 0))
            
            response = f"💼 *PORTFOLIO SUMMARY*\n\n"
            response += f"📊 Open Positions: {len(positions)}\n"
            response += f"💰 Total Entry: ${total_entry:.2f}\n"
            response += f"📈 Current Value: ${total_current:.2f}\n"
            
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            response += f"{pnl_emoji} *Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.1f}%)*\n\n"
            
            response += f"🏆 Best: #{best_pos.get('id')} ({best_pos.get('pnl_percent', 0):+.1f}%)\n"
            response += f"📉 Worst: #{worst_pos.get('id')} ({worst_pos.get('pnl_percent', 0):+.1f}%)\n"
            
            # Count by status
            moonbag_count = sum(1 for p in positions if 'PARTIAL' in p.get('status', '') or 'MOONBAG' in p.get('status', ''))
            if moonbag_count > 0:
                response += f"\n🌙 Moonbag Positions: {moonbag_count}"
            
            await self._send_response(response)
            
        except Exception as e:
            logger.error(f"Error in /summary: {e}")
            await self._send_response(f"❌ Error generating summary: {str(e)}")
    
    async def _handle_close(self, args: list):
        """Handle /close [id] command."""
        try:
            if not args:
                await self._send_response("❌ Usage: `/close [position_id]`\nExample: `/close 32`")
                return
            
            try:
                position_id = int(args[0])
            except ValueError:
                await self._send_response(f"❌ Invalid position ID: {args[0]}")
                return
            
            # Get position
            position = self.position_tracker.get_position(position_id)
            if not position:
                await self._send_response(f"❌ Position #{position_id} not found")
                return
            
            # Extract position data
            chain = position.get('chain')
            token_address = position.get('token_address')
            entry_amount = position.get('entry_amount', 0)
            status = position.get('status', 'OPEN')
            
            # Validate
            if status not in ['OPEN', 'PARTIAL_OPEN']:
                await self._send_response(f"⚠️ Position #{position_id} is already closed (Status: {status})")
                return
            
            # Notify start
            token_short = f"{token_address[:6]}...{token_address[-4:]}" if len(token_address) > 10 else token_address
            await self._send_response(f"⏳ Closing position #{position_id} ({token_short})...\nPlease wait...")
            
            # Execute sell
            success, result = await self.trade_executor.execute_sell(
                chain=chain,
                token_address=token_address,
                amount_raw=entry_amount,
                position_id=position_id,
                new_status='CLOSED_MANUAL'
            )
            
            if success:
                await self._send_response(
                    f"✅ *Position #{position_id} CLOSED*\n\n"
                    f"Token: `{token_short}`\n"
                    f"Tx Hash: `{result}`\n"
                    f"Status: Manual Close"
                )
            else:
                await self._send_response(
                    f"❌ *Failed to close position #{position_id}*\n\n"
                    f"Error: {result}\n"
                    f"Please check logs or try again"
                )
                
        except Exception as e:
            logger.error(f"Error in /close: {e}")
            await self._send_response(f"❌ Error closing position: {str(e)}")
    
    async def _handle_help(self):
        """Handle /help command."""
        help_text = """
📱 *TRADING BOT COMMANDS*

*Position Monitoring:*
/positions - Show all open positions with live P&L
/summary - Portfolio overview and statistics

*Trade Management:*
/close [id] - Manually close a position
  Example: `/close 32`

*Help:*
/help - Show this message

_Note: Commands only work from authorized chat_
"""
        await self._send_response(help_text)
    
    async def _send_response(self, message: str):
        """Send command response via Telegram."""
        try:
            # Use telegram notifier's queue system
            await self.telegram.send_message_async(message)
        except Exception as e:
            logger.error(f"Failed to send command response: {e}")
