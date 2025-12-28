"""
Secondary State Manager
Manages state transitions for secondary market tokens
"""
from typing import Dict, Optional, List
from enum import Enum


class SecondaryState(Enum):
    """Secondary market states"""
    DISCOVERED = "discovered"
    SECONDARY_DETECTED = "secondary_detected"
    WATCH = "watch"
    EARLY_ENTRY = "early_entry"
    TRADE = "trade"
    MONITOR = "monitor"
    EXIT = "exit"


class SecondaryStateManager:
    """
    Manages state transitions and auto-upgrades for secondary market tokens.
    Integrates with existing state machine.
    """

    def __init__(self):
        # State storage: {token_address: {'state': SecondaryState, 'data': {...}}}
        self.token_states = {}

        # Auto-upgrade rules
        self.upgrade_rules = {
            SecondaryState.WATCH: SecondaryState.EARLY_ENTRY,
            SecondaryState.EARLY_ENTRY: SecondaryState.TRADE,
            SecondaryState.TRADE: SecondaryState.MONITOR  # Could upgrade to SNIPER if momentum confirmed
        }

    def get_state(self, token_address: str) -> Optional[SecondaryState]:
        """Get current state for token"""
        if token_address in self.token_states:
            return self.token_states[token_address]['state']
        return None

    def set_state(self, token_address: str, state: SecondaryState, metadata: Dict = None):
        """Set state for token with optional metadata"""
        if token_address not in self.token_states:
            self.token_states[token_address] = {'state': state, 'data': {}}

        self.token_states[token_address]['state'] = state
        if metadata:
            self.token_states[token_address]['data'].update(metadata)

    def initialize_token(self, token_address: str, trigger_data: Dict):
        """Initialize token in secondary pipeline"""
        momentum_type = trigger_data.get('momentum_type', 'normal')

        if momentum_type == "retroactive":
            # Skip WATCH for retroactive momentum
            initial_state = SecondaryState.EARLY_ENTRY
        else:
            initial_state = SecondaryState.WATCH

        metadata = {
            'momentum_type': momentum_type,
            'triggers': trigger_data.get('active_triggers', []),
            'detected_at': trigger_data.get('timestamp', 0),
            'initial_score': trigger_data.get('risk_score', 0)
        }

        self.set_state(token_address, initial_state, metadata)
        return initial_state

    def check_auto_upgrade(self, token_address: str, current_external_state: str = None) -> Optional[SecondaryState]:
        """
        Check if token should auto-upgrade based on external state.
        Returns new state if upgrade needed, None otherwise.
        """
        current_secondary_state = self.get_state(token_address)
        if not current_secondary_state:
            return None

        # Map external states to upgrade logic
        external_state_map = {
            'WATCH': SecondaryState.WATCH,
            'TRADE-EARLY': SecondaryState.EARLY_ENTRY,
            'TRADE': SecondaryState.TRADE,
            'SNIPER': SecondaryState.TRADE  # SNIPER is a variant of TRADE
        }

        external_secondary_state = external_state_map.get(current_external_state)
        if not external_secondary_state:
            return None

        # If external state is ahead of secondary state, upgrade
        state_order = list(SecondaryState)
        current_idx = state_order.index(current_secondary_state)
        external_idx = state_order.index(external_secondary_state)

        if external_idx > current_idx:
            new_state = state_order[min(external_idx, len(state_order) - 1)]
            self.set_state(token_address, new_state, {'upgraded_from': current_external_state})
            return new_state

        return None

    def should_skip_watch(self, token_address: str) -> bool:
        """Check if token should skip WATCH state"""
        state_data = self.token_states.get(token_address, {})
        return state_data.get('data', {}).get('momentum_type') == 'retroactive'

    def get_state_metadata(self, token_address: str) -> Dict:
        """Get full state metadata for token"""
        return self.token_states.get(token_address, {'state': None, 'data': {}})

    def cleanup_old_tokens(self, max_age_hours: int = 24):
        """Remove tokens that haven't been updated recently"""
        import time
        cutoff = time.time() - (max_age_hours * 3600)

        to_remove = []
        for token_addr, state_data in self.token_states.items():
            last_update = state_data['data'].get('last_update', 0)
            if last_update < cutoff:
                to_remove.append(token_addr)

        for addr in to_remove:
            del self.token_states[addr]

        return len(to_remove)

    def get_tokens_in_state(self, state: SecondaryState) -> List[str]:
        """Get all tokens currently in a specific state"""
        return [addr for addr, data in self.token_states.items() if data['state'] == state]

    def get_stats(self) -> Dict:
        """Get statistics about secondary states"""
        stats = {state.value: 0 for state in SecondaryState}
        for state_data in self.token_states.values():
            state = state_data['state']
            stats[state.value] += 1

        stats['total'] = len(self.token_states)
        return stats