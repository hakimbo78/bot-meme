"""
OFF-CHAIN FILTERS

Multi-level filtering to eliminate 95% of noise before on-chain verification.

FILTERING STRATEGY:

Level-0 (cheap, off-chain only):
- liquidity > X
- volume_5m > Y
- tx_5m > Z
- age < N hours

Level-1 (momentum based):
- price_change_5m OR 15m OR 1h
- volume spike ratio
- tx acceleration
"""

from typing import Dict, Optional


class OffChainFilter:
    """
    Multi-level off-chain filter to reduce noise by ~95%.
    
    Filters OUT pairs that don't meet minimum criteria.
    Only passing pairs trigger on-chain verification.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize filter with configuration.
        
        Args:
            config: Filter configuration dict
        """
        self.config = config or {}
        
        # Level-0 thresholds (basic filters)
        self.min_liquidity = self.config.get('min_liquidity', 5000)  # $5k minimum
        self.min_volume_5m = self.config.get('min_volume_5m', 1000)  # $1k in 5 min
        self.min_tx_5m = self.config.get('min_tx_5m', 5)  # At least 5 transactions
        self.max_age_hours = self.config.get('max_age_hours', 24)  # < 24 hours old
        
        # Level-1 thresholds (momentum filters)
        self.min_price_change_5m = self.config.get('min_price_change_5m', 20.0)  # 20% gain in 5m
        self.min_price_change_1h = self.config.get('min_price_change_1h', 50.0)  # 50% gain in 1h
        self.min_volume_spike_ratio = self.config.get('min_volume_spike_ratio', 2.0)  # 2x volume spike
        
        # DEXTools guarantee rule
        self.dextools_top_rank = self.config.get('dextools_top_rank', 50)  # Top 50 = force pass
        
        # Track filter stats
        self.stats = {
            'total_evaluated': 0,
            'level0_filtered': 0,
            'level1_filtered': 0,
            'passed': 0,
            'dextools_forced': 0,
        }
    
    def apply_filters(self, normalized_pair: Dict) -> tuple[bool, Optional[str]]:
        """
        Apply all filter levels to a normalized pair.
        
        Args:
            normalized_pair: Normalized pair event dict
            
        Returns:
            (passed: bool, reason: str or None if passed)
            - True + None: Pair passed all filters
            - False + reason: Pair filtered out with reason
        """
        self.stats['total_evaluated'] += 1
        
        # DEXTOOLS GUARANTEE RULE
        # If source == "dextools" AND rank <= 50: Force pass + boost score
        if self._check_dextools_guarantee(normalized_pair):
            self.stats['dextools_forced'] += 1
            self.stats['passed'] += 1
            return True, None
        
        # LEVEL-0: Basic filters
        passed, reason = self._apply_level_0(normalized_pair)
        if not passed:
            self.stats['level0_filtered'] += 1
            return False, f"Level-0: {reason}"
        
        # LEVEL-1: Momentum filters
        passed, reason = self._apply_level_1(normalized_pair)
        if not passed:
            self.stats['level1_filtered'] += 1
            return False, f"Level-1: {reason}"
        
        # All filters passed
        self.stats['passed'] += 1
        return True, None
    
    def _check_dextools_guarantee(self, pair: Dict) -> bool:
        """
        Check if pair meets DEXTools guarantee criteria.
        
        DEXTools top-ranked pairs bypass filters and get score boost.
        
        Args:
            pair: Normalized pair dict
            
        Returns:
            True if DEXTools guaranteed, False otherwise
        """
        source = pair.get('source', '')
        rank = pair.get('dextools_rank', 9999)
        
        return source == 'dextools' and rank <= self.dextools_top_rank
    
    def _apply_level_0(self, pair: Dict) -> tuple[bool, Optional[str]]:
        """
        Apply Level-0 filters (basic criteria).
        
        Returns:
            (passed: bool, reason: str or None)
        """
        # Check liquidity
        liquidity = pair.get('liquidity', 0)
        if liquidity < self.min_liquidity:
            return False, f"Low liquidity (${liquidity:,.0f} < ${self.min_liquidity:,})"
        
        # Check volume (use 5m if available AND meaningful, else 1h, else 24h)
        volume_5m = pair.get('volume_5m')
        volume_1h = pair.get('volume_1h')
        volume_24h = pair.get('volume_24h', 0)
        
        # Treat very low vol_5m (<$5) as None to enable fallback
        # API sometimes returns $1-2 which is not meaningful
        if volume_5m is not None and volume_5m < 5:
            volume_5m = None
        
        volume_to_check = volume_5m if volume_5m is not None else (volume_1h if volume_1h is not None else volume_24h)
        
        if volume_to_check < self.min_volume_5m:
            return False, f"Low volume (${volume_to_check:,.0f} < ${self.min_volume_5m:,})"
        
        # Check transaction count
        tx_5m = pair.get('tx_5m')
        tx_1h = pair.get('tx_1h')
        tx_24h = pair.get('tx_24h', 0)
        
        tx_to_check = tx_5m if tx_5m is not None else (tx_1h if tx_1h is not None else tx_24h)
        
        if tx_to_check < self.min_tx_5m:
            return False, f"Low transactions ({tx_to_check} < {self.min_tx_5m})"
        
        # Check age (if available)
        age_minutes = pair.get('age_minutes')
        if age_minutes is not None:
            max_age_minutes = self.max_age_hours * 60
            if age_minutes > max_age_minutes:
                return False, f"Too old ({age_minutes:.0f} min > {max_age_minutes} min)"
        
        return True, None
    
    def _apply_level_1(self, pair: Dict) -> tuple[bool, Optional[str]]:
        """
        Apply Level-1 filters (momentum criteria).
        
        At least ONE of these must be true:
        - Strong price change in short timeframe
        - Volume spike
        - High transaction acceleration
        
        Returns:
            (passed: bool, reason: str or None)
        """
        reasons = []
        
        # Check price momentum
        price_change_5m = pair.get('price_change_5m', 0) or 0
        price_change_1h = pair.get('price_change_1h', 0) or 0
        
        has_price_momentum = (
            price_change_5m >= self.min_price_change_5m or
            price_change_1h >= self.min_price_change_1h
        )
        
        if not has_price_momentum:
            reasons.append(f"Weak price momentum (5m: {price_change_5m:.1f}%, 1h: {price_change_1h:.1f}%)")
        
        # Check volume spike
        volume_5m = pair.get('volume_5m', 0) or 0
        volume_1h = pair.get('volume_1h', 0) or 0
        volume_24h = pair.get('volume_24h', 0) or 0
        
        # FIX: vol_5m is often $0 (API doesn't provide it)
        # Use vol_1h vs 24h average instead
        volume_spike_ratio = 0
        
        if volume_24h > 0 and volume_1h > 0:
            # Calculate average hourly volume from 24h data
            avg_hourly_volume = volume_24h / 24
            
            # Compare current hour to average
            # If vol_1h > 1.5x average hourly → spike!
            volume_spike_ratio = volume_1h / avg_hourly_volume
            
        elif volume_5m > 0 and volume_1h > 0:
            # Fallback: If vol_5m actually exists, use it
            volume_spike_ratio = (volume_5m * 12) / volume_1h
            
        elif volume_5m > 0 and volume_24h > 0:
            # Last resort: vol_5m vs daily average
            volume_spike_ratio = (volume_5m * 288) / volume_24h
        
        has_volume_spike = volume_spike_ratio >= self.min_volume_spike_ratio
        
        if not has_volume_spike:
            reasons.append(f"No volume spike (ratio: {volume_spike_ratio:.2f}x)")
        
        # Check transaction acceleration
        tx_5m = pair.get('tx_5m', 0) or 0
        tx_1h = pair.get('tx_1h', 0) or 0
        
        if tx_1h > 0:
            tx_acceleration = (tx_5m * 12) / tx_1h  # Tx rate vs hourly average
        else:
            tx_acceleration = 0
        
        has_tx_acceleration = tx_acceleration >= 1.5  # 50% faster than average
        
        if not has_tx_acceleration:
            reasons.append(f"No TX acceleration (ratio: {tx_acceleration:.2f}x)")
        
        # Pass if ANY momentum signal is present
        if has_price_momentum or has_volume_spike or has_tx_acceleration:
            return True, None
        
        # No momentum signals
        return False, " AND ".join(reasons)
    
    def get_stats(self) -> Dict:
        """
        Get filter statistics.
        
        Returns:
            Dict with filter stats
        """
        total = self.stats['total_evaluated']
        if total == 0:
            filter_rate = 0
        else:
            filtered = self.stats['level0_filtered'] + self.stats['level1_filtered']
            filter_rate = (filtered / total) * 100
        
        return {
            **self.stats,
            'filter_rate_pct': filter_rate,
            'pass_rate_pct': 100 - filter_rate if total > 0 else 0,
        }
    
    def reset_stats(self):
        """Reset filter statistics."""
        self.stats = {
            'total_evaluated': 0,
            'level0_filtered': 0,
            'level1_filtered': 0,
            'passed': 0,
            'dextools_forced': 0,
        }
