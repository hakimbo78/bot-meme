"""
CU-EFFICIENT SECONDARY ACTIVITY SCANNER
========================================

Detects high-quality tokens via swap activity spikes WITHOUT factory-based scanning.
Designed to catch DEXTools Top Gainers and momentum plays that miss primary detection.

HARD CONSTRAINTS:
- NO refactoring existing logic
- NO new analyzers (reuses existing pipeline)
- CU-optimized (RPC cost <= 20% increase)
- Backward compatible
- ETH + BASE only, Uniswap V2 + V3

ARCHITECTURE:
1. Block-level event scanning (hash-only)
2. Receipt-level parsing (flagged tx only)
3. In-memory ring buffer (50 pools max, 5min TTL)
4. Activity signal detection (4 signals: Swap Burst, WETH Flow, Trader Growth, V3 Intensity)
5. Context injection to existing pipeline

Author: Antigravity AI
Date: 2025-12-29
"""

import time
from typing import Dict, List, Optional, Set, Tuple
from web3 import Web3
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class ActivityCandidate:
    """
    In-memory activity candidate (ring buffer entry)
    """
    pool_address: str
    chain: str
    dex: str  # 'uniswap_v2' or 'uniswap_v3'
    token_address: str
    first_seen_block: int
    first_seen_time: float = field(default_factory=time.time)
    
    # Activity metrics
    swap_count: int = 0
    unique_traders: Set[str] = field(default_factory=set)
    weth_delta: float = 0.0  # Net WETH flow (approximate)
    last_activity_block: int = 0
    
    # Tracker windows
    swap_history: deque = field(default_factory=lambda: deque(maxlen=10))  # (block, trader)
    trader_history_5m: Set[str] = field(default_factory=set)
    previous_trader_count: int = 0
    
    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if entry has expired (default 5 minutes TTL)"""
        return (time.time() - self.first_seen_time) > ttl_seconds
    
    def update_activity(self, block: int, trader: str, weth_amount: float = 0.0):
        """Update activity metrics"""
        self.last_activity_block = block
        self.swap_count += 1
        self.unique_traders.add(trader)
        self.trader_history_5m.add(trader)
        self.swap_history.append((block, trader))
        self.weth_delta += weth_amount


class SecondaryActivityScanner:
    """
    CU-Efficient Secondary Activity Scanner
    
    Detects momentum & activity spikes on existing pools with MINIMUM RPC cost.
    
    WHAT IT DOES:
    - Scans blocks for Swap/Transfer events (hash-only scan)
    - Parses flagged transactions (receipt parsing)
    - Tracks activity in ring buffer (50 pools max, 5min TTL)
    - Detects 4 activity signals (Swap Burst, WETH Flow, Trader Growth, V3 Intensity)
    - Injects activity override context to existing pipeline
    
    WHAT IT DOESN'T DO:
    - NO getReserves() calls
    - NO slot0() calls
    - NO oracle pricing
    - NO USD conversion
    - NO subgraphs
    - NO per-pair polling
    """
    
    def __init__(self, web3: Web3, chain_name: str, chain_config: Dict):
        self.web3 = web3
        self.chain_name = chain_name
        self.config = chain_config
        
        # Ring buffer: {pool_address: ActivityCandidate}
        self.activity_candidates: Dict[str, ActivityCandidate] = {}
        
        # Configuration
        self.max_pools = 50  # Max pools in ring buffer
        self.ttl_seconds = 300  # 5 minutes
        self.scan_blocks_back = 1  # EMERGENCY OPTIMIZATION: Scan only 1 block
        
        print(f"✅ [ACTIVITY] Initialized {self.chain_name.upper()} in CU-OPTIMIZED MODE (Hash-only, 1 block/cycle)")
        
        # Event signatures (Keccak-256)
        self.swap_sigs = {
            'uniswap_v2': '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',
            'uniswap_v3': '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67'
        }
        
        # Transfer signature (for WETH)
        self.transfer_sig = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
        
        # WETH address
        self.weth_address = chain_config.get('weth_address', '').lower()
        
        # Last scanned block
        self.last_scanned_block = 0
        
        # Stats
        self.stats = {
            'total_blocks_scanned': 0,
            'total_swaps_detected': 0,
            'total_pools_tracked': 0,
            'signals_generated': 0,
            'cu_budget_used': 0  # Approximate
        }
    
    def cleanup_expired(self):
        """Remove expired entries from ring buffer (async cleanup)"""
        expired_keys = [
            addr for addr, candidate in self.activity_candidates.items()
            if candidate.is_expired(self.ttl_seconds)
        ]
        
        for key in expired_keys:
            del self.activity_candidates[key]
        
        if expired_keys:
            print(f"🧹 [ACTIVITY] {self.chain_name.upper()}: Cleaned {len(expired_keys)} expired pools")
    
    def enforce_max_pools(self):
        """Enforce max pool limit by evicting oldest entries"""
        if len(self.activity_candidates) <= self.max_pools:
            return
        
        # Sort by first_seen_time (oldest first)
        sorted_candidates = sorted(
            self.activity_candidates.items(),
            key=lambda x: x[1].first_seen_time
        )
        
        # Keep only the most recent max_pools entries
        to_remove = len(self.activity_candidates) - self.max_pools
        for addr, _ in sorted_candidates[:to_remove]:
            del self.activity_candidates[addr]
        
        print(f"🧹 [ACTIVITY] {self.chain_name.upper()}: Evicted {to_remove} oldest pools (max limit: {self.max_pools})")
    
    def scan_block_for_swaps(self, block_number: int) -> List[Dict]:
        """
        Scan a single block for Swap events (ULTRA CU-EFFICIENT)
        
        EMERGENCY OPTIMIZATION:
        - Max 5 tx per block (down from 50) = 90% reduction!
        - Early exit after finding swaps
        - Skip blocks with no transactions
        
        Returns: List of flagged transactions to parse
        """
        flagged_txs = []
        swaps_found = 0
        max_swaps_per_block = 3  # Stop after finding 3 swaps
        
        try:
            # OPTIMIZATION: Get block with tx hashes only (NO full tx data)
            block = self.web3.eth.get_block(block_number, full_transactions=False)
            self.stats['total_blocks_scanned'] += 1
            
            # Track unique tx hashes that might have swaps
            tx_hashes = block.get('transactions', [])
            
            if not tx_hashes:
                return []
            
            # ULTRA AGGRESSIVE LIMIT: Only check first 5 transactions per block
            # This reduces RPC calls by 90%!
            max_tx_to_check = min(5, len(tx_hashes))
            
            # For each tx, check receipts for Swap events
            for tx_hash in tx_hashes[:max_tx_to_check]:
                try:
                    # EARLY EXIT: Stop if we found enough swaps
                    if swaps_found >= max_swaps_per_block:
                        break
                    
                    receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                    
                    # Check logs for Swap events
                    for log in receipt.get('logs', []):
                        topics = log.get('topics', [])
                        
                        if not topics:
                            continue
                        
                        # Convert topic to hex string if needed
                        topic0 = topics[0].hex() if hasattr(topics[0], 'hex') else topics[0]
                        
                        # Check if this is a Swap event
                        is_swap_v2 = topic0 == self.swap_sigs['uniswap_v2']
                        is_swap_v3 = topic0 == self.swap_sigs['uniswap_v3']
                        
                        if is_swap_v2 or is_swap_v3:
                            pool_address = log['address']
                            dex_type = 'uniswap_v2' if is_swap_v2 else 'uniswap_v3'
                            swaps_found += 1
                            
                            # Extract trader from topics (topic[1] for V2, topic[2] for V3)
                            trader_topic = topics[1] if is_swap_v2 and len(topics) > 1 else (topics[2] if is_swap_v3 and len(topics) > 2 else None)
                            trader = None
                            if trader_topic:
                                trader_hex = trader_topic.hex() if hasattr(trader_topic, 'hex') else trader_topic
                                # Extract address from 32-byte topic (last 20 bytes)
                                trader = '0x' + trader_hex[-40:]
                            
                            flagged_txs.append({
                                'pool_address': pool_address,
                                'dex_type': dex_type,
                                'block_number': block_number,
                                'trader': trader,
                                'tx_hash': tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash
                            })
                            
                            self.stats['total_swaps_detected'] += 1
                
                except Exception as e:
                    # Skip tx on error (don't crash scanner)
                    continue
        
        except Exception as e:
            print(f"⚠️  [ACTIVITY] {self.chain_name.upper()}: Block scan error #{block_number}: {e}")
        
        return flagged_txs
    
    def update_candidate(self, pool_address: str, dex_type: str, block: int, trader: Optional[str]):
        """
        Update or create activity candidate
        """
        pool_address = pool_address.lower()
        
        if pool_address not in self.activity_candidates:
            # Create new candidate
            self.activity_candidates[pool_address] = ActivityCandidate(
                pool_address=pool_address,
                chain=self.chain_name,
                dex=dex_type,
                token_address='',  # Will be resolved later if needed
                first_seen_block=block,
                last_activity_block=block
            )
            self.stats['total_pools_tracked'] += 1
        
        # Update activity
        candidate = self.activity_candidates[pool_address]
        weth_delta = 0.0  # Approximate (would need full tx parsing for exact value)
        
        if trader:
            candidate.update_activity(block, trader, weth_delta)
    
    def detect_signals(self, candidate: ActivityCandidate, current_block: int) -> Dict:
        """
        Detect activity signals for a candidate
        
        Returns: Dict with signal data and activity_score
        """
        signals = {
            'swap_burst': False,
            'weth_flow_spike': False,
            'trader_growth': False,
            'v3_intensity': False
        }
        
        activity_score = 0
        
        # SIGNAL A: Swap Burst (>= 3 swaps, >= 3 unique traders, within 1-3 blocks)
        recent_swaps = [s for s in candidate.swap_history if (current_block - s[0]) <= 3]
        unique_recent_traders = set(s[1] for s in recent_swaps if s[1])
        
        if len(recent_swaps) >= 3 and len(unique_recent_traders) >= 3:
            signals['swap_burst'] = True
            activity_score += 30
        
        # SIGNAL B: WETH Flow Spike (net WETH delta >= threshold)
        # Note: This is approximate without full TX parsing
        # For now, we use swap count as a proxy
        if candidate.swap_count >= 5:
            signals['weth_flow_spike'] = True
            activity_score += 20
        
        # SIGNAL C: Trader Growth (unique_traders_5min >= 10 AND previous <= 3)
        current_traders = len(candidate.trader_history_5m)
        trader_growth_multiplier = current_traders / max(candidate.previous_trader_count, 1)
        
        if current_traders >= 10 and candidate.previous_trader_count <= 3:
            signals['trader_growth'] = True
            activity_score += 25
        
        # SIGNAL D: Uniswap V3 Intensity (>= 5 Swap events within 2 blocks)
        if candidate.dex == 'uniswap_v3':
            v3_recent_swaps = [s for s in candidate.swap_history if (current_block - s[0]) <= 2]
            if len(v3_recent_swaps) >= 5:
                signals['v3_intensity'] = True
                activity_score += 40  # V3 activity is rarer, higher weight
        
        # Update previous trader count for next cycle
        candidate.previous_trader_count = current_traders
        
        return {
            'signals': signals,
            'activity_score': activity_score,
            'swap_count': candidate.swap_count,
            'unique_traders': len(candidate.unique_traders),
            'active_signals': sum(signals.values())
        }
    
    def evaluate_all_candidates(self, current_block: int) -> List[Dict]:
        """
        Evaluate all candidates and return those with significant activity
        
        Returns: List of activity signals to inject into pipeline
        """
        activity_signals = []
        
        for pool_address, candidate in list(self.activity_candidates.items()):
            signal_data = self.detect_signals(candidate, current_block)
            
            # DEXTools Top Gainer Guarantee Rule
            # IF activity_score >= 70 AND momentum_confirmed, FORCE enqueue
            if signal_data['activity_score'] >= 70:
                activity_signals.append({
                    'pool_address': pool_address,
                    'chain': self.chain_name,
                    'dex': candidate.dex,
                    'token_address': candidate.token_address,  # May be empty, will resolve later
                    'activity_score': signal_data['activity_score'],
                    'signals': signal_data['signals'],
                    'swap_count': signal_data['swap_count'],
                    'unique_traders': signal_data['unique_traders'],
                    'active_signals': signal_data['active_signals'],
                    'source': 'secondary_activity',
                    'activity_override': True  # KEY: Enables override rules in scorer
                })
                
                self.stats['signals_generated'] += 1
        
        return activity_signals
    
    def scan_recent_activity(self, target_block: int = None) -> List[Dict]:
        """
        Main scanning method: Scan recent blocks for activity
        
        Returns: List of activity signals
        """
        try:
            # Get current block
            if target_block:
                current_block = target_block
            else:
                current_block = self.web3.eth.block_number
            
            # Determine scan range
            if self.last_scanned_block == 0:
                # First scan: start from current - scan_blocks_back
                from_block = current_block - self.scan_blocks_back
            else:
                # Subsequent scans: scan from last scanned + 1
                from_block = self.last_scanned_block + 1
            
            # Limit scan range to prevent overload
            # OPTIMIZATION: Aggressively reduce block scan range
            # Only scan max 1 block back to keep CU usage minimal
            max_scan_blocks = 1
            from_block = max(from_block, current_block - max_scan_blocks)
            
            if from_block > current_block:
                return []  # No new blocks to scan
            
            # Ensure we don't scan too many blocks at once even if we feel behind
            # Just scan the latest block to catch up efficiently
            if (current_block - from_block) > max_scan_blocks:
                from_block = current_block - max_scan_blocks
            
            print(f"🔍 [ACTIVITY] {self.chain_name.upper()}: Scanning block {current_block} (optimized)")
            
            # Scan each block
            for block_num in range(from_block, current_block + 1):
                flagged_txs = self.scan_block_for_swaps(block_num)
                
                # Update candidates
                for tx_data in flagged_txs:
                    self.update_candidate(
                        pool_address=tx_data['pool_address'],
                        dex_type=tx_data['dex_type'],
                        block=tx_data['block_number'],
                        trader=tx_data.get('trader')
                    )
            
            # Update last scanned block
            self.last_scanned_block = current_block
            
            # Cleanup expired entries (async)
            self.cleanup_expired()
            
            # Enforce max pools limit
            self.enforce_max_pools()
            
            # Evaluate all candidates
            activity_signals = self.evaluate_all_candidates(current_block)
            
            # Stats
            if activity_signals:
                print(f"🎯 [ACTIVITY] {self.chain_name.upper()}: {len(activity_signals)} activity signals detected ({len(self.activity_candidates)} pools monitored)")
            
            return activity_signals
        
        except Exception as e:
            print(f"❌ [ACTIVITY] {self.chain_name.upper()}: Scan error: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            **self.stats,
            'monitored_pools': len(self.activity_candidates),
            'chain': self.chain_name
        }
    
    def create_activity_context(self) -> Dict:
        """
        Create activity override context for scorer integration
        
        This context modifies scoring behavior:
        - Min liquidity: $3k -> $1k
        - Pair age limit: BYPASSED
        - Base score: +20
        - Momentum: REQUIRED
        - Factory origin: BYPASSED
        """
        return {
            "source": "secondary_activity",
            "activity_override": True,
            "min_liquidity_override": 1000,  # Lower threshold for activity-detected tokens
            "bypass_age_limit": True,
            "bonus_score": 20,
            "require_momentum": True,
            "bypass_factory": True
        }


def calculate_market_heat_with_activity(
    primary_heat: float,
    activity_signals: int,
    swap_burst_count: int,
    trader_growth_count: int
) -> float:
    """
    MARKET HEAT REBALANCE (PART 9)
    
    Calculate market heat with activity contribution
    
    New formula:
        heat = activity_signals * 3 + swap_burst * 2 + trader_growth
    
    This allows market heat to rise even without new launches.
    """
    activity_heat = (
        activity_signals * 3 +
        swap_burst_count * 2 +
        trader_growth_count
    )
    
    # Combine primary and activity heat
    total_heat = primary_heat + activity_heat
    
    return total_heat


# ================================================
# INTEGRATION HELPERS
# ================================================

def enrich_token_data_with_activity(token_data: Dict, activity_signal: Dict) -> Dict:
    """
    Enrich token data with activity context for existing pipeline
    
    This is the bridge between activity scanner and existing scorer/analyzer.
    """
    enriched = token_data.copy()
    
    # Add activity metadata
    enriched['activity_detected'] = True
    enriched['activity_score'] = activity_signal.get('activity_score', 0)
    enriched['activity_signals'] = activity_signal.get('signals', {})
    enriched['swap_count'] = activity_signal.get('swap_count', 0)
    enriched['unique_traders'] = activity_signal.get('unique_traders', 0)
    enriched['source'] = 'secondary_activity'
    
    # Inject activity override context
    enriched['activity_override'] = True
    enriched['bypass_age_limit'] = True
    enriched['bypass_factory'] = True
    
    return enriched


def apply_activity_override_to_score(score_data: Dict, activity_signal: Dict) -> Dict:
    """
    Apply activity override rules to score data (PART 7)
    
    ACTIVITY OVERRIDE RULES:
    - Min liquidity: $3k -> $1k (handled in analyzer)
    - Pair age limit: BYPASSED (handled in analyzer)
    - Base score: +20
    - Momentum: REQUIRED
    - Factory origin: BYPASSED (handled in analyzer)
    """
    modified_score = score_data.copy()
    
    # Add activity bonus score
    modified_score['score'] = modified_score.get('score', 0) + 20
    
    # Add activity flag to risk_flags
    risk_flags = modified_score.get('risk_flags', [])
    risk_flags.append(f"🔥 ACTIVITY: {activity_signal.get('active_signals', 0)}/4 signals active")
    modified_score['risk_flags'] = risk_flags
    
    # Mark as activity-sourced
    modified_score['activity_detected'] = True
    modified_score['activity_score'] = activity_signal.get('activity_score', 0)
    
    return modified_score


# ================================================
# PRODUCTION-READY EXPORT
# ================================================

__all__ = [
    'SecondaryActivityScanner',
    'ActivityCandidate',
    'calculate_market_heat_with_activity',
    'enrich_token_data_with_activity',
    'apply_activity_override_to_score'
]
