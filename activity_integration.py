"""
ACTIVITY SCANNER INTEGRATION MODULE
====================================

Bridges the secondary activity scanner with the existing pipeline.
Handles context injection, score overrides, and activity-based alerts.

CRITICAL RULES:
- NO refactoring existing logic
- ADDITIVE integration only
- Backward compatible
- Clean separation of concerns

Author: Antigravity AI
Date: 2025-12-29
"""

from typing import Dict, List, Optional
from secondary_activity_scanner import SecondaryActivityScanner, enrich_token_data_with_activity, apply_activity_override_to_score


class ActivityIntegration:
    """
    Integration layer between activity scanner and main pipeline
    
    Responsibilities:
    1. Coordinate activity scanners across chains
    2. Inject activity context into token data
    3. Apply activity override rules to scoring
    4. Generate activity-aware alerts
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.scanners: Dict[str, SecondaryActivityScanner] = {}
        
        # Activity stats
        self.total_signals = 0
        self.signals_by_chain = {}
        self.last_scan_time = {}
    
    def register_scanner(self, chain_name: str, scanner: SecondaryActivityScanner):
        """Register an activity scanner for a chain"""
        self.scanners[chain_name] = scanner
        self.signals_by_chain[chain_name] = 0
        print(f"✅ [ACTIVITY INT] Registered scanner for {chain_name.upper()}")
    
    def scan_all_chains(self) -> List[Dict]:
        """
        Scan all registered chains for activity signals
        
        Returns: List of activity signals from all chains
        """
        if not self.enabled:
            return []
        
        all_signals = []
        
        for chain_name, scanner in self.scanners.items():
            try:
                signals = scanner.scan_recent_activity()
                
                if signals:
                    all_signals.extend(signals)
                    self.signals_by_chain[chain_name] = len(signals)
                    self.total_signals += len(signals)
                    
                    print(f"🔥 [ACTIVITY INT] {chain_name.upper()}: {len(signals)} signals")
            
            except Exception as e:
                print(f"⚠️  [ACTIVITY INT] {chain_name.upper()}: Scan error: {e}")
        
        return all_signals
    
    def scan_chain_activity(self, chain_name: str, target_block: int) -> List[Dict]:
        """
        Scan a specific chain for activity signals (Event-Driven)
        """
        if not self.enabled:
            return []
            
        scanner = self.scanners.get(chain_name)
        if not scanner:
            return []
            
        try:
            signals = scanner.scan_recent_activity(target_block=target_block)
            
            if signals:
                self.signals_by_chain[chain_name] = len(signals)
                self.total_signals += len(signals)
                print(f"🔥 [ACTIVITY INT] {chain_name.upper()}: {len(signals)} signals in block {target_block}")
                
            return signals
        except Exception as e:
            print(f"⚠️  [ACTIVITY INT] {chain_name.upper()}: Scan error: {e}")
            return []
    
    def process_activity_signal(self, signal: Dict, token_data: Optional[Dict] = None) -> Dict:
        """
        Process an activity signal and prepare for pipeline injection
        
        Args:
            signal: Activity signal from scanner
            token_data: Optional existing token data to enrich
        
        Returns:
            Enriched token data ready for analyzer/scorer
        """
        if token_data is None:
            # Create minimal token data from signal
            token_data = {
                'pair_address': signal.get('pool_address', ''),
                'token_address': signal.get('token_address', ''),
                'chain': signal.get('chain', ''),
                'dex': signal.get('dex', ''),
            }
        
        # Enrich with activity context
        enriched_data = enrich_token_data_with_activity(token_data, signal)
        
        return enriched_data
    
    def should_force_enqueue(self, signal: Dict) -> bool:
        """
        DEXTOOLS TOP GAINER GUARANTEE RULE (PART 8)
        
        Determine if signal should force bypass and enqueue for deep analysis
        
        Condition:
            IF activity_score >= 70 AND momentum_confirmed == True
            THEN FORCE enqueue for deep analysis, BYPASS age & factory filters
        
        Returns: True if should force enqueue
        """
        activity_score = signal.get('activity_score', 0)
        
        # For activity signals, we ALWAYS force enqueue if score >= 70
        # Momentum will be checked during scoring phase
        if activity_score >= 70:
            return True
        
        return False
    
    def apply_scoring_override(self, score_data: Dict, activity_signal: Dict) -> Dict:
        """
        Apply activity override rules to score data (PART 7)
        
        ACTIVITY OVERRIDE RULES:
        - Min liquidity: $3k -> $1k
        - Pair age limit: BYPASSED
        - Base score: +20
        - Momentum: REQUIRED
        - Factory origin: BYPASSED
        
        Args:
            score_data: Original score data from scorer
            activity_signal: Activity signal context
        
        Returns:
            Modified score data with overrides applied
        """
        return apply_activity_override_to_score(score_data, activity_signal)
    
    def generate_activity_alert_tag(self, signal: Dict) -> str:
        """
        Generate alert tag for Telegram/Dashboard (PART 10)
        
        Returns: '[ACTIVITY]' or '[V3 ACTIVITY]'
        """
        dex = signal.get('dex', '')
        
        if dex == 'uniswap_v3':
            return '[V3 ACTIVITY]'
        else:
            return '[ACTIVITY]'
    
    def get_activity_badge_data(self, signal: Dict) -> Dict:
        """
        Get dashboard badge data (PART 10)
        
        Returns: Dict with badge info for UI
        """
        signals = signal.get('signals', {})
        
        return {
            'badge': '🔥 ACTIVITY',
            'swap_burst_count': 1 if signals.get('swap_burst') else 0,
            'unique_traders': signal.get('unique_traders', 0),
            'chain': signal.get('chain', ''),
            'dex': signal.get('dex', ''),
            'activity_score': signal.get('activity_score', 0),
            'signals_active': f"{signal.get('active_signals', 0)}/4"
        }
    
    def calculate_market_heat_contribution(self) -> Dict:
        """
        Calculate activity contribution to market heat (PART 9)
        
        Returns: Dict with heat components
        """
        total_activity_signals = sum(self.signals_by_chain.values())
        
        # Count specific signal types across all chains
        swap_burst_count = 0
        trader_growth_count = 0
        
        for scanner in self.scanners.values():
            for candidate in scanner.activity_candidates.values():
                # Approximate signal counting (would need full signal detection)
                if candidate.swap_count >= 3:
                    swap_burst_count += 1
                if len(candidate.trader_history_5m) >= 10:
                    trader_growth_count += 1
        
        # Calculate heat contribution
        from secondary_activity_scanner import calculate_market_heat_with_activity
        activity_heat = calculate_market_heat_with_activity(
            primary_heat=0,  # Will be added by caller
            activity_signals=total_activity_signals,
            swap_burst_count=swap_burst_count,
            trader_growth_count=trader_growth_count
        )
        
        return {
            'activity_heat': activity_heat,
            'total_signals': total_activity_signals,
            'swap_bursts': swap_burst_count,
            'trader_growth': trader_growth_count
        }
    
    def get_integration_stats(self) -> Dict:
        """Get integration statistics"""
        scanner_stats = {}
        for chain_name, scanner in self.scanners.items():
            scanner_stats[chain_name] = scanner.get_stats()
        
        return {
            'enabled': self.enabled,
            'total_signals': self.total_signals,
            'signals_by_chain': dict(self.signals_by_chain),
            'scanner_stats': scanner_stats
        }
    
    def print_status(self):
        """Print current status"""
        if not self.enabled:
            print("❌ [ACTIVITY INT] Activity scanner DISABLED")
            return
        
        print(f"\n🔥 [ACTIVITY INT] Status:")
        print(f"   ├─ Enabled: {self.enabled}")
        print(f"   ├─ Total signals: {self.total_signals}")
        print(f"   ├─ Active scanners: {len(self.scanners)}")
        
        for chain_name, count in self.signals_by_chain.items():
            scanner = self.scanners.get(chain_name)
            if scanner:
                pools = len(scanner.activity_candidates)
                print(f"   ├─ {chain_name.upper()}: {count} signals, {pools} pools monitored")
        
        print(f"   └─ Integration: ACTIVE ✅")


# ================================================
# SCORER INTEGRATION HELPERS
# ================================================

def apply_activity_context_to_analysis(analysis_data: Dict, activity_signal: Dict) -> Dict:
    """
    Apply activity context to analysis data before scoring
    
    This modifies analyzer output to account for activity override rules.
    """
    modified_analysis = analysis_data.copy()
    
    # Override min liquidity check
    if activity_signal.get('activity_override'):
        # Lower liquidity requirement for activity-detected tokens
        modified_analysis['min_liquidity_override'] = 1000
        
        # Bypass age limit
        modified_analysis['bypass_age_limit'] = True
        
        # Bypass factory origin requirement
        modified_analysis['bypass_factory'] = True
        
        # Add activity context
        modified_analysis['activity_detected'] = True
        modified_analysis['activity_score'] = activity_signal.get('activity_score', 0)
    
    return modified_analysis


def should_require_momentum_for_activity(score_data: Dict, activity_signal: Dict) -> bool:
    """
    Check if momentum is required for activity-detected tokens (PART 7)
    
    Activity override rules state: Momentum = REQUIRED
    
    Returns: True if momentum should be required
    """
    if activity_signal.get('activity_override'):
        return True
    
    return False


# ================================================
# EXPORT
# ================================================

__all__ = [
    'ActivityIntegration',
    'apply_activity_context_to_analysis',
    'should_require_momentum_for_activity'
]
