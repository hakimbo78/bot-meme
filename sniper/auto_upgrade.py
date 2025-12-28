"""
Auto-Upgrade Engine (TRADE → SNIPER)

Monitors existing TRADE alerts continuously.
If TX priority OR smart wallet signals appear after initial TRADE:
- Recalculate score with new signals
- Upgrade status to SNIPER if final_score >= 85

READ-ONLY informational system.
NO trading execution.

Output:
- Auto-upgrade alerts via Telegram
- Clear TRADE → SNIPER transition messaging
"""

import time
from typing import Dict, List, Optional, Set
from pathlib import Path
import json


class AutoUpgradeEngine:
    """
    Continuously monitor TRADE alerts for upgrade to SNIPER.
    
    Upgrade triggers:
    - TX priority signals appear (priority_score > 0)
    - Smart wallet detected (smart_wallet_score > 0)
    - Final score >= upgrade_threshold (default 85)
    
    Features:
    - Persistent tracking of TRADE tokens
    - Automatic score recalculation
    - Cooldown management
    - Clear upgrade reasoning
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize auto-upgrade engine.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        
        # Configuration
        self.enabled = self.config.get('enabled', True)
        self.upgrade_threshold = self.config.get('upgrade_threshold', 85)
        self.max_monitoring_minutes = self.config.get('max_monitoring_minutes', 30)
        self.cooldown_seconds = self.config.get('cooldown_seconds', 300)  # 5 min between upgrades
        
        # Scoring weights
        self.base_weight = self.config.get('base_weight', 1.0)
        self.priority_weight = self.config.get('priority_weight', 1.0)
        self.smart_wallet_weight = self.config.get('smart_wallet_weight', 1.0)
        
        # State tracking
        self.monitored_tokens = {}  # token_address -> monitoring data
        self.upgraded_tokens = set()  # Set of upgraded token addresses
        self.last_upgrade_time = {}  # token_address -> timestamp
        
        # Persistence
        self.state_file = Path('data/auto_upgrade_state.json')
        self._load_state()
        
        print(f"[AUTO-UPGRADE] Engine initialized (enabled={self.enabled}, threshold={self.upgrade_threshold})")
    
    def register_trade_alert(self, token_data: Dict, score_data: Dict) -> bool:
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
        
        token_address = token_data.get('address', token_data.get('token_address', ''))
        if not token_address:
            return False
        
        # Normalize address
        token_address = token_address.lower()
        
        # Skip if already upgraded
        if token_address in self.upgraded_tokens:
            return False
        
        # Register for monitoring
        self.monitored_tokens[token_address] = {
            'token_data': token_data,
            'initial_score_data': score_data,
            'registered_time': time.time(),
            'last_check_time': time.time(),
            'check_count': 0,
            'chain': token_data.get('chain', 'unknown'),
            'name': token_data.get('name', 'UNKNOWN'),
            'symbol': token_data.get('symbol', '???')
        }
        
        self._save_state()
        
        print(f"[AUTO-UPGRADE] Registered: {token_data.get('name', 'UNKNOWN')} ({token_address[:8]}...)")
        
        return True
    
    def check_upgrade(self, token_address: str, new_signals: Dict) -> Dict:
        """
        Check if a monitored token should be upgraded to SNIPER.
        
        Args:
            token_address: Token address to check
            new_signals: Dict with:
                - priority_score: int (0-50) from priority detector
                - smart_wallet_score: int (0-40) from smart wallet detector
                - priority_reasons: List[str]
                - smart_wallet_reasons: List[str]
        
        Returns:
            Dict with:
                - should_upgrade: bool
                - final_score: int
                - upgrade_reasons: List[str]
                - score_breakdown: Dict
        """
        result = {
            'should_upgrade': False,
            'final_score': 0,
            'upgrade_reasons': [],
            'score_breakdown': {}
        }
        
        # Normalize address
        token_address = token_address.lower()
        
        # Check if token is monitored
        if token_address not in self.monitored_tokens:
            return result
        
        monitoring_data = self.monitored_tokens[token_address]
        
        # Check if monitoring period expired
        elapsed_minutes = (time.time() - monitoring_data['registered_time']) / 60
        if elapsed_minutes > self.max_monitoring_minutes:
            # Stop monitoring this token
            print(f"[AUTO-UPGRADE] Monitoring expired for {monitoring_data['name']} ({elapsed_minutes:.1f}m)")
            del self.monitored_tokens[token_address]
            self._save_state()
            return result
        
        # Update check time
        monitoring_data['last_check_time'] = time.time()
        monitoring_data['check_count'] += 1
        
        # Get initial score
        initial_score_data = monitoring_data['initial_score_data']
        base_score = initial_score_data.get('score', 0)
        
        # Get new signal scores
        priority_score = new_signals.get('priority_score', 0)
        smart_wallet_score = new_signals.get('smart_wallet_score', 0)
        
        # Calculate final score
        # Formula: base_score + (priority_score * weight) + (smart_wallet_score * weight)
        # Cap final score at 95
        weighted_priority = priority_score * self.priority_weight
        weighted_smart_wallet = smart_wallet_score * self.smart_wallet_weight
        
        final_score = base_score + weighted_priority + weighted_smart_wallet
        final_score = min(95, int(final_score))
        
        result['final_score'] = final_score
        result['score_breakdown'] = {
            'base_score': base_score,
            'priority_score': priority_score,
            'smart_wallet_score': smart_wallet_score,
            'weighted_priority': weighted_priority,
            'weighted_smart_wallet': weighted_smart_wallet,
            'final_score': final_score
        }
        
        # Build upgrade reasons
        reasons = []
        
        if priority_score > 0:
            reasons.extend(new_signals.get('priority_reasons', []))
        
        if smart_wallet_score > 0:
            reasons.extend(new_signals.get('smart_wallet_reasons', []))
        
        # Check if meets upgrade threshold
        if final_score >= self.upgrade_threshold and reasons:
            # Check cooldown
            last_upgrade = self.last_upgrade_time.get(token_address, 0)
            cooldown_remaining = self.cooldown_seconds - (time.time() - last_upgrade)
            
            if cooldown_remaining > 0:
                print(f"[AUTO-UPGRADE] Cooldown active for {monitoring_data['name']} ({cooldown_remaining:.0f}s remaining)")
                return result
            
            # UPGRADE APPROVED
            result['should_upgrade'] = True
            result['upgrade_reasons'] = reasons
            
            # Mark as upgraded
            self.upgraded_tokens.add(token_address)
            self.last_upgrade_time[token_address] = time.time()
            
            # Remove from monitoring
            del self.monitored_tokens[token_address]
            self._save_state()
            
            # Log upgrade logic (Specific to Solana for debug visibility)
            if monitoring_data.get('chain') == 'solana':
                symbol = monitoring_data.get('symbol', '???')
                reason_str = " + ".join(reasons[:2]) # Keep it concise for log
                print(f"[SOLANA][DEBUG][UPGRADE] {symbol} | OldScore={base_score} → NewScore={final_score} | Reason={reason_str}", flush=True)
            
            print(f"[AUTO-UPGRADE] ✅ UPGRADE APPROVED: {monitoring_data['name']} ({base_score} → {final_score})", flush=True)
        
        return result
    
    def get_monitoring_summary(self) -> Dict:
        """
        Get summary of currently monitored tokens.
        
        Returns:
            Dict with monitoring statistics
        """
        current_time = time.time()
        
        active = []
        expired = []
        
        for addr, data in self.monitored_tokens.items():
            elapsed_minutes = (current_time - data['registered_time']) / 60
            remaining_minutes = self.max_monitoring_minutes - elapsed_minutes
            
            if remaining_minutes > 0:
                active.append({
                    'address': addr,
                    'name': data['name'],
                    'symbol': data['symbol'],
                    'chain': data['chain'],
                    'elapsed_minutes': elapsed_minutes,
                    'remaining_minutes': remaining_minutes,
                    'check_count': data['check_count']
                })
            else:
                expired.append(addr)
        
        # Clean up expired
        for addr in expired:
            del self.monitored_tokens[addr]
        
        if expired:
            self._save_state()
        
        return {
            'active_count': len(active),
            'upgraded_count': len(self.upgraded_tokens),
            'active_tokens': active
        }
    
    def clear_history(self):
        """Clear all monitoring data (for testing)."""
        self.monitored_tokens.clear()
        self.upgraded_tokens.clear()
        self.last_upgrade_time.clear()
        self._save_state()
        print("[AUTO-UPGRADE] History  cleared")
    
    def _save_state(self):
        """Save state to disk for persistence."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                'monitored_tokens': self.monitored_tokens,
                'upgraded_tokens': list(self.upgraded_tokens),
                'last_upgrade_time': self.last_upgrade_time
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        
        except Exception as e:
            print(f"[AUTO-UPGRADE] Error saving state: {e}")
    
    def _load_state(self):
        """Load state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.monitored_tokens = state.get('monitored_tokens', {})
                self.upgraded_tokens = set(state.get('upgraded_tokens', []))
                self.last_upgrade_time = state.get('last_upgrade_time', {})
                
                print(f"[AUTO-UPGRADE] Loaded state: {len(self.monitored_tokens)} monitored, {len(self.upgraded_tokens)} upgraded")
        
        except Exception as e:
            print(f"[AUTO-UPGRADE] Error loading state: {e}")
