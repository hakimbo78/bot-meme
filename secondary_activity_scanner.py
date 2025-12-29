"""
CU-EFFICIENT SECONDARY ACTIVITY SCANNER
========================================

Detects high-quality tokens via swap activity spikes WITHOUT factory-based scanning.
"Hunter" mode: Only monitors high-value pools (Score>=70) via optimized delta-logs.

HARD CONSTRAINTS:
- Pool Admission Rule (Score >= 70 required)
- Pool TTL (Auto-drop after 120 blocks inactivity)
- Delta-only Log Scan (No global block scanning)
- Max 10 pools per chain

ARCHITECTURE:
1. Pool Admission Gate (Filter high value only)
2. Delta Log Scanner (eth_getLogs per pool)
3. Activity Ring Buffer (Max 10 pools)
4. Context Injection

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
    In-memory activity candidate (tracked pool)
    """
    pool_address: str
    chain: str
    dex: str
    token_address: str
    
    # Admission Metadata
    initial_score: float
    liquidity_usd: float
    is_smart_wallet: bool = False
    is_trending: bool = False
    
    # Tracking State
    first_seen_block: int = 0
    last_scanned_block: int = 0
    last_activity_block: int = 0
    
    # Metrics
    swap_count: int = 0
    volume_usd: float = 0.0  # Approximate
    unique_traders: Set[str] = field(default_factory=set)
    activity_score: float = 0.0
    
    # TTL Management
    ttl_blocks: int = 120  # Default 120 blocks (~4 mins on Base)

    def is_dead(self, current_block: int) -> bool:
        """Check if pool is dead (TTL expired)"""
        return (current_block - self.last_activity_block) > self.ttl_blocks

    def update_metrics(self, tx_count: int, volume: float, traders: Set[str], current_block: int):
        """Update activity metrics"""
        self.swap_count += tx_count
        self.volume_usd += volume
        self.unique_traders.update(traders)
        
        if tx_count > 0:
            self.last_activity_block = current_block


class SecondaryActivityScanner:
    """
    Hunter-Mode Activity Scanner
    
    MONITORS ONLY:
    - High Score Pools (>= 70)
    - Trade Upgrades
    - Smart Wallet Hits
    
    STRICT LIMITS:
    - Max 10 pools per chain
    - Delta-only log scanning
    - 120 Block TTL
    """
    
    def __init__(self, web3: Web3, chain_name: str, chain_config: Dict):
        self.web3 = web3
        self.chain_name = chain_name
        self.config = chain_config
        
        # Tracked Pools: {pool_address: ActivityCandidate}
        self.tracked_pools: Dict[str, ActivityCandidate] = {}
        
        # Limits
        self.MAX_POOLS = 10
        self.TTL_BLOCKS = 120
        
        print(f"✅ [ACTIVITY] Initialized {self.chain_name.upper()} Hunter Mode (Max {self.MAX_POOLS} pools)")
        
        # Event signatures (Keccak-256)
        self.swap_sigs = {
            'uniswap_v2': '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',
            'uniswap_v3': '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67'
        }
        
        # Stats
        self.stats = {
            'scans_performed': 0,
            'signals_generated': 0,
            'pools_admitted': 0,
            'pools_dropped': 0
        }

    def is_activity_eligible(self, score: float, is_trade: bool, is_smart_wallet: bool, is_trending: bool) -> bool:
        """
        POOL ADMISSION RULE (Rule #1)
        """
        return (
            score >= 70 or
            is_trade or
            is_smart_wallet or
            is_trending
        )

    def track_pool(self, pool_data: Dict) -> bool:
        """
        Admit a pool to the activity scanner
        
        Args:
            pool_data: {
                'pool_address': str,
                'token_address': str,
                'dex': str,
                'score': float,
                'liquidity_usd': float,
                'is_trade': bool,
                'is_smart_wallet': bool,
                'is_trending': bool,
                'current_block': int
            }
        """
        pool_address = pool_data.get('pool_address', '').lower()
        if not pool_address:
            return False
            
        # Check eligibility
        eligible = self.is_activity_eligible(
            score=pool_data.get('score', 0),
            is_trade=pool_data.get('is_trade', False),
            is_smart_wallet=pool_data.get('is_smart_wallet', False),
            is_trending=pool_data.get('is_trending', False)
        )
        
        if not eligible:
            # pool_address not admitted msg if debug needed
            return False
            
        # Check if already tracked
        if pool_address in self.tracked_pools:
            return True
            
        # Enforce Rate Limit (Rule #5) via Priority Drop
        if len(self.tracked_pools) >= self.MAX_POOLS:
            dropped = self._enforce_limit(pool_data)
            if not dropped:
                return False  # Start pool wasn't good enough to replace anyone
                
        # Create Candidate
        current_block = pool_data.get('current_block', 0)
        candidate = ActivityCandidate(
            pool_address=pool_address,
            chain=self.chain_name,
            dex=pool_data.get('dex', 'uniswap_v2'),
            token_address=pool_data.get('token_address', ''),
            initial_score=pool_data.get('score', 0),
            liquidity_usd=pool_data.get('liquidity_usd', 0),
            is_smart_wallet=pool_data.get('is_smart_wallet', False),
            is_trending=pool_data.get('is_trending', False),
            first_seen_block=current_block,
            last_scanned_block=current_block,
            last_activity_block=current_block,
            ttl_blocks=self.TTL_BLOCKS
        )
        
        self.tracked_pools[pool_address] = candidate
        self.stats['pools_admitted'] += 1
        
        print(f"🧠 [ACTIVITY] Pool admitted: {pool_address[:10]} (score={candidate.initial_score:.0f})")
        return True

    def _enforce_limit(self, new_pool: Dict) -> bool:
        """
        Enforce max pools limit by dropping lowest priority.
        Returns True if space was made (or existed).
        Priority: Score > Liquidity > Smart Wallet
        """
        if len(self.tracked_pools) < self.MAX_POOLS:
            return True
            
        # Calculate new pool score/priority
        # Simple weighted sort metric: Score*1000 + Liquidity
        new_priority = new_pool.get('score', 0) * 1000 + new_pool.get('liquidity_usd', 0)
        if new_pool.get('is_smart_wallet'): new_priority += 50000
        
        # Find worst pool
        worst_pool_addr = None
        worst_priority = float('inf')
        
        for addr, p in self.tracked_pools.items():
            priority = p.initial_score * 1000 + p.liquidity_usd
            if p.is_smart_wallet: priority += 50000
            
            if priority < worst_priority:
                worst_priority = priority
                worst_pool_addr = addr
                
        if worst_pool_addr and worst_priority < new_priority:
            del self.tracked_pools[worst_pool_addr]
            print(f"🔥 [ACTIVITY] Kicked low-prio pool: {worst_pool_addr[:10]}")
            return True
            
        return False

    def has_smart_wallet_targets(self) -> bool:
        """Check if any tracked pool is a smart wallet target"""
        return any(p.is_smart_wallet for p in self.tracked_pools.values())

    def scan_pool_logs(self, candidate: ActivityCandidate, current_block: int) -> Optional[Dict]:
        """
        DELTA-ONLY LOG SCAN (Rule #3)
        eth_getLogs for specific pool address only.
        """
        from_block = candidate.last_scanned_block + 1
        if from_block > current_block:
            return None
            
        # Optimization: Don't scan huge ranges if we fell behind
        if (current_block - from_block) > 50:
            from_block = current_block - 10
            
        try:
            # Construct Topics based on DEX
            topics = [self.swap_sigs[candidate.dex]] if candidate.dex in self.swap_sigs else []
            
            logs = self.web3.eth.get_logs({
                'address': Web3.to_checksum_address(candidate.pool_address),
                'fromBlock': from_block,
                'toBlock': current_block,
                'topics': topics
            })
            
            candidate.last_scanned_block = current_block
            
            if not logs:
                return None
                
            # Process Activity
            tx_count = len(logs)
            traders = set()
            
            for log in logs:
                topics_list = log.get('topics', [])
                # Extract trader (Topic 1 for V2, Topic 2 for V3)
                if len(topics_list) > 2:
                    idx = 2 if candidate.dex == 'uniswap_v3' else 1
                    if len(topics_list) > idx:
                        trader_hex = topics_list[idx].hex() if hasattr(topics_list[idx], 'hex') else topics_list[idx]
                        traders.add('0x' + trader_hex[-40:])
            
            # Update Candidate
            candidate.update_metrics(tx_count, 0, traders, current_block)
            
            # Calculate Activity Score (Rule #4)
            # f(tx, smart_wallet, speed)
            activity_score = self._calculate_activity_score(candidate, tx_count)
            
            return {
                'pool_address': candidate.pool_address,
                'chain': self.chain_name,
                'tx_delta': tx_count,
                'unique_traders': len(traders),
                'activity_score': activity_score,
                'total_swaps': candidate.swap_count,
                'dex': candidate.dex
            }
            
        except Exception as e:
            # print(f"⚠️ [ACTIVITY] Log scan error {candidate.pool_address[:8]}: {e}")
            return None

    def _calculate_activity_score(self, candidate: ActivityCandidate, tx_delta: int) -> float:
        """
        Calculate activity score impact
        """
        base_score = tx_delta * 5.0  # 5 points per tx
        
        # Multipliers
        if candidate.is_smart_wallet:
            base_score *= 1.5
        
        # Cap per block to avoid infinite score
        return min(base_score, 50.0)

    def scan_recent_activity(self, target_block: int = None) -> List[Dict]:
        """
        Main Loop: Scan all tracked pools
        """
        if not target_block:
            try:
                target_block = self.web3.eth.block_number
            except:
                return []
                
        signals = []
        pools_to_drop = []
        
        # Log status (Only if active)
        if len(self.tracked_pools) > 0:
            print(f"🔥 [ACTIVITY] {self.chain_name.upper()}: {len(self.tracked_pools)} pools monitored (limit {self.MAX_POOLS})")
            # print("💸 [ACTIVITY] RPC usage optimized (delta-only)")
            
        
        for addr, candidate in self.tracked_pools.items():
            # 1. Check TTL (Rule #2)
            if candidate.is_dead(target_block):
                pools_to_drop.append(addr)
                continue
                
            # 2. Scan Logs
            result = self.scan_pool_logs(candidate, target_block)
            
            # 3. Generate Signal if significant
            if result and result['activity_score'] > 0:
                signals.append(result)
                self.stats['signals_generated'] += 1
                
        # Handle Drops
        for addr in pools_to_drop:
            del self.tracked_pools[addr]
            self.stats['pools_dropped'] += 1
            print(f"🗑️ [ACTIVITY] Pool dropped (TTL expired): {addr[:10]}")
            
        return signals

    def get_stats(self) -> Dict:
        return {
            **self.stats,
            'monitored_pools': len(self.tracked_pools)
        }


def calculate_market_heat_with_activity(
    primary_heat: float,
    activity_signals: int,
    swap_burst_count: int,
    trader_growth_count: int
) -> float:
    """Market heat contribution from activity"""
    return primary_heat + (activity_signals * 2)


# ================================================
# INTEGRATION HELPERS
# ================================================

def enrich_token_data_with_activity(token_data: Dict, activity_signal: Dict) -> Dict:
    """Enrich token data with activity context"""
    enriched = token_data.copy()
    enriched['activity_detected'] = True
    enriched['activity_score'] = activity_signal.get('activity_score', 0)
    enriched['source'] = 'secondary_activity'
    return enriched


def apply_activity_override_to_score(score_data: Dict, activity_signal: Dict) -> Dict:
    """
    Apply activity score boost:
    pair.score += activity_score * ACTIVITY_WEIGHT
    """
    modified_score = score_data.copy()
    
    # Activity Boost (Rule #4)
    activity_score = activity_signal.get('activity_score', 0)
    ACTIVITY_WEIGHT = 0.5
    
    bonus = activity_score * ACTIVITY_WEIGHT
    modified_score['score'] = min(100, modified_score.get('score', 0) + bonus)
    
    risk_flags = modified_score.get('risk_flags', [])
    risk_flags.append(f"🔥 ACTIVITY BOOST: +{bonus:.1f}")
    modified_score['risk_flags'] = risk_flags
    
    # Auto-upgrade trigger is handled by the caller checking the new score
    
    return modified_score


__all__ = [
    'SecondaryActivityScanner',
    'ActivityCandidate',
    'calculate_market_heat_with_activity',
    'enrich_token_data_with_activity',
    'apply_activity_override_to_score'
]
