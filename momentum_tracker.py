"""
Momentum Tracker - Multi-cycle validation for token metrics
Tracks liquidity, price, and volume across multiple blocks to confirm sustained momentum.

This module reduces false positives by requiring tokens to demonstrate
consistent growth patterns before receiving high scores.
"""
import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from config import (
    MOMENTUM_SNAPSHOTS,
    MOMENTUM_INTERVAL_BLOCKS,
    MOMENTUM_LIQUIDITY_TOLERANCE,
    MOMENTUM_SCORE_MAX
)
from safe_math import safe_div, safe_ratio


@dataclass
class Snapshot:
    """Single point-in-time snapshot of token metrics"""
    timestamp: float
    block_number: int
    liquidity_usd: float
    price_estimate: float  # Derived from reserves ratio
    volume_indicator: float  # Simple volume proxy
    

@dataclass
class TokenMomentum:
    """Aggregated momentum data for a token"""
    token_address: str
    snapshots: List[Snapshot] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    

class MomentumTracker:
    """
    Tracks token metrics across multiple blocks to confirm sustained momentum.
    
    Features:
    - In-memory snapshot storage (lightweight, no persistence)
    - Configurable snapshot count and block intervals
    - Validates liquidity stability, price consistency, and volume persistence
    - Auto-cleanup after final evaluation
    """
    
    def __init__(self, adapter=None):
        """
        Initialize MomentumTracker.
        
        Args:
            adapter: Chain adapter for fetching block/liquidity data
        """
        self.adapter = adapter
        self._token_data: Dict[str, TokenMomentum] = {}
        self._cleanup_threshold = 300  # Clean up tokens older than 5 minutes
    
    def add_snapshot(self, token_address: str, liquidity_usd: float, 
                     price_estimate: float, volume_indicator: float,
                     block_number: int) -> None:
        """
        Add a new snapshot for a token.
        
        Args:
            token_address: Token contract address
            liquidity_usd: Current liquidity in USD
            price_estimate: Estimated price (from reserves ratio)
            volume_indicator: Volume proxy metric
            block_number: Current block number
        """
        token_addr = token_address.lower()
        
        if token_addr not in self._token_data:
            self._token_data[token_addr] = TokenMomentum(token_address=token_addr)
        
        snapshot = Snapshot(
            timestamp=time.time(),
            block_number=block_number,
            liquidity_usd=liquidity_usd,
            price_estimate=price_estimate,
            volume_indicator=volume_indicator
        )
        
        self._token_data[token_addr].snapshots.append(snapshot)
        
        # Cleanup old entries periodically
        self._cleanup_old_entries()
    
    def has_enough_snapshots(self, token_address: str) -> bool:
        """Check if we have enough snapshots for validation"""
        token_addr = token_address.lower()
        if token_addr not in self._token_data:
            return False
        return len(self._token_data[token_addr].snapshots) >= MOMENTUM_SNAPSHOTS
    
    def validate_momentum(self, token_address: str) -> Dict:
        """
        Validate momentum based on collected snapshots.
        
        Returns:
            Dict with:
            - momentum_confirmed: bool
            - momentum_score: int (0-20)
            - momentum_details: dict with specific validations
        """
        token_addr = token_address.lower()
        
        # Default response for insufficient data
        default_result = {
            'momentum_confirmed': False,
            'momentum_score': 0,
            'momentum_details': {
                'snapshots_collected': 0,
                'liquidity_stable': False,
                'price_consistent': False,
                'volume_persistent': False,
                'reason': 'Insufficient snapshots'
            }
        }
        
        if token_addr not in self._token_data:
            return default_result
        
        snapshots = self._token_data[token_addr].snapshots
        
        if len(snapshots) < MOMENTUM_SNAPSHOTS:
            default_result['momentum_details']['snapshots_collected'] = len(snapshots)
            default_result['momentum_details']['reason'] = f'Only {len(snapshots)}/{MOMENTUM_SNAPSHOTS} snapshots'
            return default_result
        
        # Use the last N snapshots
        recent_snapshots = snapshots[-MOMENTUM_SNAPSHOTS:]
        
        # Validate liquidity stability (Δ < ±15%)
        liquidity_stable = self._check_liquidity_stability(recent_snapshots)
        
        # Validate price consistency (no full retrace)
        price_consistent = self._check_price_consistency(recent_snapshots)
        
        # Validate volume persistence (not zero)
        volume_persistent = self._check_volume_persistence(recent_snapshots)
        
        # Calculate momentum score
        score = 0
        if liquidity_stable:
            score += 7
        if price_consistent:
            score += 8
        if volume_persistent:
            score += 5
        
        # Momentum is confirmed only if all criteria pass
        momentum_confirmed = liquidity_stable and price_consistent and volume_persistent
        
        return {
            'momentum_confirmed': momentum_confirmed,
            'momentum_score': min(score, MOMENTUM_SCORE_MAX),
            'momentum_details': {
                'snapshots_collected': len(recent_snapshots),
                'liquidity_stable': liquidity_stable,
                'price_consistent': price_consistent,
                'volume_persistent': volume_persistent,
                'reason': 'All criteria passed' if momentum_confirmed else 'Some criteria failed'
            }
        }
    
    def _check_liquidity_stability(self, snapshots: List[Snapshot]) -> bool:
        """
        Check if liquidity remained within ±15% tolerance.
        """
        if not snapshots:
            return False
        
        baseline = snapshots[0].liquidity_usd
        if baseline <= 0:
            return False
        
        for snapshot in snapshots[1:]:
            # SAFE: Use safe_ratio to prevent division by zero if baseline == 0
            change_ratio = safe_ratio(snapshot.liquidity_usd, baseline, default=999.0)
            if change_ratio > MOMENTUM_LIQUIDITY_TOLERANCE:
                return False
        
        return True
    
    def _check_price_consistency(self, snapshots: List[Snapshot]) -> bool:
        """
        Check for price consistency - no full retrace.
        Price should not drop below initial price significantly.
        """
        if not snapshots:
            return False
        
        initial_price = snapshots[0].price_estimate
        if initial_price <= 0:
            return True  # Can't calculate, assume OK
        
        # Check that price hasn't fully retraced (dropped > 50%)
        for snapshot in snapshots[1:]:
            if snapshot.price_estimate < initial_price * 0.5:
                return False
        
        return True
    
    def _check_volume_persistence(self, snapshots: List[Snapshot]) -> bool:
        """
        Check that volume indicator is not zero across all snapshots.
        """
        if not snapshots:
            return False
        
        # At least one snapshot should have non-zero volume
        for snapshot in snapshots:
            if snapshot.volume_indicator > 0:
                return True
        
        return False
    
    def clear_token(self, token_address: str) -> None:
        """Remove token data after final evaluation"""
        token_addr = token_address.lower()
        if token_addr in self._token_data:
            del self._token_data[token_addr]
    
    def _cleanup_old_entries(self) -> None:
        """Remove entries older than cleanup threshold"""
        current_time = time.time()
        tokens_to_remove = []
        
        for token_addr, data in self._token_data.items():
            if current_time - data.created_at > self._cleanup_threshold:
                tokens_to_remove.append(token_addr)
        
        for token_addr in tokens_to_remove:
            del self._token_data[token_addr]
    
    def get_quick_momentum(self, token_address: str, liquidity_usd: float,
                           price_estimate: float = 1.0, 
                           volume_indicator: float = 1.0,
                           block_number: int = 0) -> Dict:
        """
        Quick momentum check for single-pass analysis.
        If we don't have enough snapshots, add one and return unconfirmed status.
        If we have enough, validate and return results.
        
        This is the primary method to call from analyzer.
        
        Args:
            token_address: Token contract address
            liquidity_usd: Current liquidity in USD
            price_estimate: Optional price estimate
            volume_indicator: Optional volume proxy
            block_number: Current block number
            
        Returns:
            Momentum validation result dict
        """
        # Add current snapshot
        self.add_snapshot(
            token_address=token_address,
            liquidity_usd=liquidity_usd,
            price_estimate=price_estimate,
            volume_indicator=volume_indicator,
            block_number=block_number
        )
        
        # Check if we have enough for validation
        if self.has_enough_snapshots(token_address):
            result = self.validate_momentum(token_address)
            # Don't clear immediately - may need for re-analysis
            return result
        
        # Not enough snapshots yet
        token_addr = token_address.lower()
        current_count = len(self._token_data.get(token_addr, TokenMomentum(token_address=token_addr)).snapshots)
        
        return {
            'momentum_confirmed': False,
            'momentum_score': 0,
            'momentum_details': {
                'snapshots_collected': current_count,
                'liquidity_stable': False,
                'price_consistent': False,
                'volume_persistent': False,
                'reason': f'Collecting snapshots: {current_count}/{MOMENTUM_SNAPSHOTS}'
            }
        }
