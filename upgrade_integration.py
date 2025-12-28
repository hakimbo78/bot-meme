"""
Integration Module for Auto-Upgrade System

Combines priority detection, smart wallet detection, and auto-upgrade engine
into a unified workflow for TRADE → SNIPER upgrades.

Usage:
    from upgrade_integration import UpgradeIntegration
    
    integration = UpgradeIntegration(config)
    
    # Register TRADE alert for monitoring
    integration.register_trade(token_data, score_data)
    
    # Check for upgrades (call periodically)
    integration.process_pending_upgrades(telegram_notifier)
"""

from typing import Dict, List, Optional
from pathlib import Path
import sys

# Import the new modules
try:
    from modules_solana.priority_detector import SolanaPriorityDetector
    from modules_solana.smart_wallet_detector import SmartWalletDetector
    from sniper.auto_upgrade import AutoUpgradeEngine
    from telegram_alerts_ext import send_sniper_upgrade_alert
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"[UPGRADE_INTEGRATION] Module import failed: {e}")
    MODULES_AVAILABLE = False


class UpgradeIntegration:
    """
    Unified integration for auto-upgrade workflow.
    
    Features:
    - Monitors TRADE alerts for upgrade eligibility
    - Detects priority TX signals (Solana)
    - Detects smart wallet involvement
    - Calculates final score
    - Upgrades to SNIPER if threshold met
    - Sends Telegram alerts
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize upgrade integration.
        
        Args:
            config: Configuration dict with:
                - priority_detector: priority detector config
                - smart_wallet: smart wallet config
                - auto_upgrade: auto-upgrade engine config
        """
        self.config = config or {}
        
        if not MODULES_AVAILABLE:
            print("[UPGRADE_INTEGRATION] ⚠️ Modules not available, feature disabled")
            self.enabled = False
            return
        
        # Initialize components
        priority_config = self.config.get('priority_detector', {})
        smart_wallet_config = self.config.get('smart_wallet', {})
        upgrade_config = self.config.get('auto_upgrade', {})
        
        self.priority_detector = SolanaPriorityDetector(priority_config)
        self.smart_wallet_detector = SmartWalletDetector(smart_wallet_config)
        self.auto_upgrade_engine = AutoUpgradeEngine(upgrade_config)
        
        self.enabled = upgrade_config.get('enabled', True)
        
        print(f"[UPGRADE_INTEGRATION] Initialized (enabled={self.enabled})")
    
    def register_trade(self, token_data: Dict, score_data: Dict) -> bool:
        """
        Register a TRADE alert for upgrade monitoring.
        
        Args:
            token_data: Token analysis data
            score_data: Current score data
        
        Returns:
            True if registered successfully
        """
        if not self.enabled:
            return False
        
        return self.auto_upgrade_engine.register_trade_alert(token_data, score_data)
    
    def check_signals(self, token_address: str, transaction_data: Optional[Dict] = None,
                      wallet_addresses: Optional[List[str]] = None) -> Dict:
        """
        Check for priority and smart wallet signals for a token.
        
        Args:
            token_address: Token address to check
            transaction_data: Optional transaction data for priority detection
            wallet_addresses: Optional list of wallet addresses to check
        
        Returns:
            Dict with:
                - priority_score: int (0-50)
                - smart_wallet_score: int (0-40)
                - priority_reasons: List[str]
                - smart_wallet_reasons: List[str]
                - is_priority: bool
                - is_smart_money: bool
        """
        result = {
            'priority_score': 0,
            'smart_wallet_score': 0,
            'priority_reasons': [],
            'smart_wallet_reasons': [],
            'is_priority': False,
            'is_smart_money': False
        }
        
        # Check priority signals
        if transaction_data:
            try:
                priority_result = self.priority_detector.analyze_transaction(transaction_data)
                result['priority_score'] = priority_result.get('priority_score', 0)
                result['priority_reasons'] = priority_result.get('priority_reasons', [])
                result['is_priority'] = priority_result.get('is_priority', False)
            except Exception as e:
                print(f"[UPGRADE_INTEGRATION] Priority detection error: {e}")
        
        # Check smart wallet signals
        if wallet_addresses:
            try:
                smart_wallet_result = self.smart_wallet_detector.analyze_wallets(wallet_addresses)
                result['smart_wallet_score'] = smart_wallet_result.get('smart_wallet_score', 0)
                result['smart_wallet_reasons'] = smart_wallet_result.get('smart_wallet_reasons', [])
                result['is_smart_money'] = smart_wallet_result.get('is_smart_money', False)
            except Exception as e:
                print(f"[UPGRADE_INTEGRATION] Smart wallet detection error: {e}")
        
        return result
    
    def process_single_token(self, token_address: str, new_signals: Dict,
                             telegram_notifier=None) -> Dict:
        """
        Process a single token for potential upgrade.
        
        Args:
            token_address: Token address
            new_signals: Dict from check_signals()
            telegram_notifier: Optional TelegramNotifier instance for alerts
        
        Returns:
            Dict with upgrade result
        """
        if not self.enabled:
            return {'processed': False, 'reason': 'Integration disabled'}
        
        # Check upgrade eligibility
        upgrade_result = self.auto_upgrade_engine.check_upgrade(token_address, new_signals)
        
        if upgrade_result.get('should_upgrade'):
            # Get token data from monitoring
            monitoring_data = self.auto_upgrade_engine.monitored_tokens.get(token_address.lower())
            
            if monitoring_data and telegram_notifier:
                # Send upgrade alert
                try:
                    success = send_sniper_upgrade_alert(
                        telegram_notifier,
                        monitoring_data['token_data'],
                        monitoring_data['initial_score_data'],
                        {'score': upgrade_result['final_score']},  # Create simple final score data
                        upgrade_result
                    )
                    
                    if success:
                        print(f"[UPGRADE_INTEGRATION] ✅ SNIPER alert sent: {monitoring_data['name']}")
                    
                    return {
                        'processed': True,
                        'upgraded': True,
                        'alert_sent': success,
                        'final_score': upgrade_result['final_score']
                    }
                except Exception as e:
                    print(f"[UPGRADE_INTEGRATION] Alert error: {e}")
                    return {
                        'processed': True,
                        'upgraded': True,
                        'alert_sent': False,
                        'error': str(e)
                    }
        
        return {
            'processed': True,
            'upgraded': False,
            'final_score': upgrade_result.get('final_score', 0)
        }
    
    def process_pending_upgrades(self, telegram_notifier=None,
                                  transaction_fetcher=None,
                                  wallet_fetcher=None) -> Dict:
        """
        Process all pending tokens for potential upgrades.
        
        This should be called periodically in the main loop.
        
        Args:
            telegram_notifier: TelegramNotifier instance for alerts
            transaction_fetcher: Optional function to fetch transaction data for a token
            wallet_fetcher: Optional function to fetch wallet addresses for a token
        
        Returns:
            Dict with processing summary
        """
        if not self.enabled:
            return {'processed': 0, 'upgraded': 0}
        
        summary = {
            'processed': 0,
            'upgraded': 0,
            'errors': 0
        }
        
        # Get currently monitored tokens
        monitored = list(self.auto_upgrade_engine.monitored_tokens.keys())
        
        for token_address in monitored:
            try:
                # Fetch new signals
                transaction_data = None
                wallet_addresses = None
                
                if transaction_fetcher:
                    try:
                        transaction_data = transaction_fetcher(token_address)
                    except Exception as e:
                        print(f"[UPGRADE_INTEGRATION] TX fetch error for {token_address[:8]}: {e}")
                
                if wallet_fetcher:
                    try:
                        wallet_addresses = wallet_fetcher(token_address)
                    except Exception as e:
                        print(f"[UPGRADE_INTEGRATION] Wallet fetch error for {token_address[:8]}: {e}")
                
                # Check signals
                new_signals = self.check_signals(token_address, transaction_data, wallet_addresses)
                
                # Only process if there are actual signals
                if new_signals['is_priority'] or new_signals['is_smart_money']:
                    result = self.process_single_token(token_address, new_signals, telegram_notifier)
                    
                    summary['processed'] += 1
                    if result.get('upgraded'):
                        summary['upgraded'] += 1
            
            except Exception as e:
                print(f"[UPGRADE_INTEGRATION] Error processing {token_address[:8]}: {e}")
                summary['errors'] += 1
        
        return summary
    
    def get_monitoring_summary(self) -> Dict:
        """Get summary of monitoring status."""
        if not self.enabled:
            return {'enabled': False}
        
        auto_upgrade_summary = self.auto_upgrade_engine.get_monitoring_summary()
        wallet_stats = self.smart_wallet_detector.get_tier_stats()
        
        return {
            'enabled': True,
            'monitored_tokens': auto_upgrade_summary.get('active_count', 0),
            'upgraded_tokens': auto_upgrade_summary.get('upgraded_count', 0),
            'smart_wallets': wallet_stats.get('total', 0),
            'tier1_wallets': wallet_stats.get('tier1', 0)
        }
