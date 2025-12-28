"""
Sniper Kill Switch - Auto-cancel mechanism for active sniper targets

Kill Switch Triggers (ANY = immediate cancel):
- Liquidity drop >= 20%
- Dev wallet LP removal detected
- Dev transfer detected  
- MEV / bundle detected
- Momentum invalidated
- sniper_score drops >= 15

When triggered:
- Sends CANCELLED alert immediately
- Logs with [SNIPER] prefix
"""
import time
from typing import Dict, Optional, List
from .sniper_config import get_sniper_config


class SniperKillSwitch:
    """
    Kill Switch - monitors active sniper targets and cancels if conditions deteriorate.
    
    This is a safety mechanism to warn operators when initial conditions
    are no longer valid.
    """
    
    def __init__(self):
        self.config = get_sniper_config()
        self._liq_drop_threshold = self.config.get('killswitch_liquidity_drop_pct', 0.20)
        self._score_drop_threshold = self.config.get('killswitch_score_drop', 15)
        
        # Active targets: {token_address: initial_state}
        self._active_targets: Dict[str, Dict] = {}
    
    def register_sniper_target(self, token_address: str, initial_state: Dict) -> None:
        """
        Register a token as an active sniper target for monitoring.
        
        Args:
            token_address: Token contract address
            initial_state: Dict with initial values to compare against:
                - liquidity_usd: float
                - sniper_score: int
                - momentum_confirmed: bool
                - dev_flag: str
                - mev_detected: bool
                - fake_pump: bool
                - timestamp: float (auto-set if not provided)
        """
        token_addr = token_address.lower()
        
        # Add timestamp if not present
        state = initial_state.copy()
        if 'timestamp' not in state:
            state['timestamp'] = time.time()
        
        self._active_targets[token_addr] = state
        print(f"[SNIPER] KillSwitch: Registered {token_addr[:10]}... for monitoring")
    
    def unregister_target(self, token_address: str) -> bool:
        """Remove a token from active monitoring."""
        token_addr = token_address.lower()
        if token_addr in self._active_targets:
            del self._active_targets[token_addr]
            print(f"[SNIPER] KillSwitch: Unregistered {token_addr[:10]}...")
            return True
        return False
    
    def check_kill_conditions(self, 
                               token_address: str,
                               current_state: Dict) -> Dict:
        """
        Check if any kill conditions are triggered.
        
        Args:
            token_address: Token contract address
            current_state: Current values to compare:
                - liquidity_usd: float
                - sniper_score: int (optional, from re-calculation)
                - momentum_confirmed: bool
                - dev_flag: str
                - mev_detected: bool
                - fake_pump: bool
                - lp_removed: bool (from wallet tracker)
                - dev_transfer: bool (from wallet tracker)
                
        Returns:
            Dict with:
            - kill_triggered: bool
            - kill_reason: str
            - kill_type: str (type of trigger)
            - details: dict
        """
        token_addr = token_address.lower()
        
        # Default response (no kill)
        result = {
            'kill_triggered': False,
            'kill_reason': '',
            'kill_type': '',
            'details': {}
        }
        
        # Check if registered
        if token_addr not in self._active_targets:
            result['details']['note'] = 'Not a registered sniper target'
            return result
        
        initial = self._active_targets[token_addr]
        kill_reasons = []
        
        # 1. Liquidity Drop Check (>= 20%)
        initial_liq = initial.get('liquidity_usd', 0)
        current_liq = current_state.get('liquidity_usd', 0)
        
        if initial_liq > 0:
            liq_change = (initial_liq - current_liq) / initial_liq
            if liq_change >= self._liq_drop_threshold:
                kill_reasons.append({
                    'type': 'LIQUIDITY_DROP',
                    'reason': f'Liquidity dropped {liq_change*100:.1f}% (${initial_liq:,.0f} -> ${current_liq:,.0f})'
                })
        
        # 2. Dev LP Removal Check
        if current_state.get('lp_removed', False):
            kill_reasons.append({
                'type': 'LP_REMOVAL',
                'reason': 'Dev wallet LP removal detected'
            })
        
        # 3. Dev Transfer Check
        if current_state.get('dev_transfer', False):
            kill_reasons.append({
                'type': 'DEV_TRANSFER',
                'reason': 'Dev wallet transfer detected'
            })
        
        # 4. MEV Detection Check (new detection after alert)
        if current_state.get('mev_detected', False) and not initial.get('mev_detected', False):
            kill_reasons.append({
                'type': 'MEV_DETECTED',
                'reason': 'MEV / bundle pattern detected'
            })
        
        # 5. Fake Pump Detection (new detection after alert)
        if current_state.get('fake_pump', False) and not initial.get('fake_pump', False):
            kill_reasons.append({
                'type': 'FAKE_PUMP',
                'reason': 'Fake pump pattern detected'
            })
        
        # 6. Momentum Invalidated
        if initial.get('momentum_confirmed', True) and not current_state.get('momentum_confirmed', True):
            kill_reasons.append({
                'type': 'MOMENTUM_INVALIDATED',
                'reason': 'Momentum validation failed'
            })
        
        # 7. Score Drop Check (>= 15 points)
        initial_score = initial.get('sniper_score', 0)
        current_score = current_state.get('sniper_score', initial_score)  # Default to initial if not provided
        
        if initial_score > 0 and current_score > 0:
            score_drop = initial_score - current_score
            if score_drop >= self._score_drop_threshold:
                kill_reasons.append({
                    'type': 'SCORE_DROP',
                    'reason': f'Sniper score dropped {score_drop} points ({initial_score} -> {current_score})'
                })
        
        # 8. Dev Flag Escalation (SAFE -> WARNING/DUMP, or WARNING -> DUMP)
        initial_flag = initial.get('dev_flag', 'SAFE')
        current_flag = current_state.get('dev_flag', 'SAFE')
        flag_severity = {'SAFE': 0, 'WARNING': 1, 'DUMP': 2}
        
        if flag_severity.get(current_flag, 0) > flag_severity.get(initial_flag, 0):
            kill_reasons.append({
                'type': 'DEV_FLAG_ESCALATION',
                'reason': f'Dev flag escalated: {initial_flag} -> {current_flag}'
            })
        
        # Evaluate result
        if kill_reasons:
            # Use first kill reason as primary
            primary_kill = kill_reasons[0]
            
            result = {
                'kill_triggered': True,
                'kill_reason': primary_kill['reason'],
                'kill_type': primary_kill['type'],
                'details': {
                    'all_reasons': kill_reasons,
                    'initial_state': initial,
                    'current_state': current_state
                }
            }
            
            print(f"[SNIPER] KillSwitch TRIGGERED for {token_addr[:10]}...: {primary_kill['reason']}")
        
        return result
    
    def get_active_targets(self) -> List[str]:
        """Get list of actively monitored token addresses."""
        return list(self._active_targets.keys())
    
    def get_target_info(self, token_address: str) -> Optional[Dict]:
        """Get initial state for a registered target."""
        return self._active_targets.get(token_address.lower())
    
    def clear_expired_targets(self, max_age_minutes: int = 30) -> int:
        """
        Remove targets older than max_age_minutes.
        
        Args:
            max_age_minutes: Max age in minutes before auto-removal
            
        Returns:
            Number of targets removed
        """
        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        
        to_remove = []
        for token_addr, state in self._active_targets.items():
            age = current_time - state.get('timestamp', 0)
            if age > max_age_seconds:
                to_remove.append(token_addr)
        
        for token_addr in to_remove:
            del self._active_targets[token_addr]
            print(f"[SNIPER] KillSwitch: Expired {token_addr[:10]}... (>{max_age_minutes}m)")
        
        return len(to_remove)
    
    def format_kill_alert(self, token_data: Dict, kill_result: Dict) -> str:
        """
        Format a CANCELLED alert message.
        
        Args:
            token_data: Token information
            kill_result: Result from check_kill_conditions
            
        Returns:
            Formatted message string for Telegram
        """
        chain_prefix = token_data.get('chain_prefix', '[UNKNOWN]')
        name = token_data.get('name', 'UNKNOWN')
        symbol = token_data.get('symbol', '???')
        address = token_data.get('address', token_data.get('token_address', 'N/A'))
        
        kill_type = kill_result.get('kill_type', 'UNKNOWN')
        kill_reason = kill_result.get('kill_reason', 'Unknown reason')
        
        message = f"""❌🔫 {chain_prefix} SNIPER CANCELLED ❌

*Token:* `{name}` ({symbol})
*Address:* `{address[:20]}...`

🚨 *Kill Reason:* {kill_type}
*Details:* {kill_reason}

⚠️ *DO NOT ENTER* - Risk detected
_Exit immediately if already in position_

🚨 _This is an automated safety alert._
"""
        return message
