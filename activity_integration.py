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
    5. GATEKEEPER: Route high-value pools to scanners
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

    def track_new_pool(self, token_data: Dict, score_data: Dict) -> bool:
        """
        ADMISSION GATE (Rule #1 Intermediary)
        Routes analyzed pools to the appropriate activity scanner.
        """
        if not self.enabled:
            return False

        chain = token_data.get('chain', 'base').lower()
        if chain == 'unknown':
             # Try to guess from prefix or config, but safest to skip
             return False
             
        scanner = self.scanners.get(chain)
        if not scanner:
            # Maybe it's an EVM chain that isn't registered yet or solana?
            return False

        # Prepare Pool Data for Admission
        pool_data = {
            'pool_address': token_data.get('address'),
            'token_address': token_data.get('address'),  # or token address if separated
            'dex': token_data.get('dex', 'uniswap_v2'),
            'score': score_data.get('score', 0),
            'liquidity_usd': token_data.get('liquidity_usd', 0),
            'is_trade': score_data.get('verdict') == 'TRADE',
            'is_smart_wallet': 'Smart Wallet' in str(score_data.get('risk_flags', [])),
            'is_trending': False, # Can be passed if available
            'current_block': 0 # Scanner will fetch if 0, or we can pass if known
        }
        
        # Try to fetch block number if possible (optimization)
        try:
            if hasattr(scanner.web3.eth, 'block_number'):
                pool_data['current_block'] = scanner.web3.eth.block_number
        except:
            pass

        return scanner.track_pool(pool_data)
    
    def has_smart_wallet_targets(self, chain_name: str) -> bool:
        """Check if chain has active smart wallet targets (Heat Gate Override)"""
        scanner = self.scanners.get(chain_name)
        return scanner.has_smart_wallet_targets() if scanner else False

    def scan_all_chains(self) -> List[Dict]:
        """
        Scan all registered chains for activity signals
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
            # Perform delta-scan on tracked pools
            signals = scanner.scan_recent_activity(target_block=target_block)
            
            if signals:
                self.signals_by_chain[chain_name] = len(signals)
                self.total_signals += len(signals)
                print(f"🔥 [ACTIVITY INT] {chain_name.upper()}: {len(signals)} signals in block {target_block}")
            else:
                 # Clean logging for heartbeat if needed (optional via rule 7)
                 pass
                
            return signals
        except Exception as e:
            print(f"⚠️  [ACTIVITY INT] {chain_name.upper()}: Scan error: {e}")
            return []
    
    def process_activity_signal(self, signal: Dict, token_data: Optional[Dict] = None) -> Dict:
        """
        Process an activity signal and prepare for pipeline injection
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
        Determine if signal should force bypass and enqueue for deep analysis
        """
        activity_score = signal.get('activity_score', 0)
        
        # Consistent Rule: High activity -> Re-analyze
        if activity_score >= 15:  # Lower threshold for re-check, but criticals need higher
            return True
        
        return False
    
    def apply_scoring_override(self, score_data: Dict, activity_signal: Dict) -> Dict:
        """
        Apply activity override rules to score data
        """
        return apply_activity_override_to_score(score_data, activity_signal)
    
    def generate_activity_alert_tag(self, signal: Dict) -> str:
        """
        Generate alert tag for Telegram/Dashboard
        """
        dex = signal.get('dex', '')
        
        if dex == 'uniswap_v3':
            return '[V3 ACTIVITY]'
        else:
            return '[ACTIVITY]'
    
    def get_activity_badge_data(self, signal: Dict) -> Dict:
        """
        Get dashboard badge data (PART 10)
        """
        return {
            'badge': '🔥 ACTIVITY',
            'swap_burst_count': 0, # Deprecated metric
            'unique_traders': signal.get('unique_traders', 0),
            'chain': signal.get('chain', ''),
            'dex': signal.get('dex', ''),
            'activity_score': signal.get('activity_score', 0),
            'signals_active': f"Score {signal.get('activity_score', 0):.0f}"
        }
    
    def calculate_market_heat_contribution(self) -> Dict:
        """
        Calculate activity contribution to market heat (PART 9)
        """
        total_activity_signals = sum(self.signals_by_chain.values())
        
        # Count monitored pools across all chains
        total_monitored = 0
        for scanner in self.scanners.values():
            total_monitored += len(scanner.tracked_pools)
        
        # Calculate heat contribution (Generic)
        activity_heat = total_activity_signals * 2 + total_monitored * 0.5
        
        return {
            'activity_heat': activity_heat,
            'total_signals': total_activity_signals,
            'monitored_pools': total_monitored
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
                pools = len(scanner.tracked_pools)
                print(f"   ├─ {chain_name.upper()}: {count} signals, {pools} pools monitored")
        
        print(f"   └─ Integration: ACTIVE ✅")


# ================================================
# SCORER INTEGRATION HELPERS
# ================================================

def apply_activity_context_to_analysis(analysis_data: Dict, activity_signal: Dict) -> Dict:
    """
    Apply activity context to analysis data before scoring
    """
    modified_analysis = analysis_data.copy()
    
    # Activity Override Rules
    if activity_signal.get('activity_override') or activity_signal.get('source') == 'secondary_activity':
        modified_analysis['min_liquidity_override'] = 1000
        modified_analysis['bypass_age_limit'] = True
        modified_analysis['bypass_factory'] = True
        modified_analysis['activity_detected'] = True
        modified_analysis['activity_score'] = activity_signal.get('activity_score', 0)
    
    return modified_analysis


def should_require_momentum_for_activity(score_data: Dict, activity_signal: Dict) -> bool:
    """
    Activity-detected tokens require momentum validation
    """
    if activity_signal.get('activity_override') or activity_signal.get('source') == 'secondary_activity':
        return True
    
    return False


__all__ = [
    'ActivityIntegration',
    'apply_activity_context_to_analysis',
    'should_require_momentum_for_activity'
]
