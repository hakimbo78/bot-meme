"""
OFF-CHAIN FILTERS

Multi-level filtering to eliminate 95% of noise before on-chain verification.

FILTERING STRATEGY:

Level-0 (Quality Gate - eliminates dead/low-activity pairs):
- liquidity >= $1,000
- volume.h1 >= $300
- txns.h1 >= 10

Level-1 (Momentum Detection - identifies breakouts):
- priceChange.h1 >= 5% OR
- volume spike ratio >= 2.0x (h1 vs h24 average)
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
        
        # ================================================================
        # LEVEL-0 THRESHOLDS (Quality Gate)
        # ================================================================
        # DexScreener API provides h1/h24 data ONLY
        self.min_liquidity = self.config.get('min_liquidity', 1000)  # $1,000 minimum
        self.min_volume_1h = self.config.get('min_volume_1h', 300)  # $300 h1 volume
        self.min_tx_1h = self.config.get('min_tx_1h', 10)  # 10 h1 transactions
        
        self.max_age_hours = self.config.get('max_age_hours', None)  # None = disabled
        
        # ================================================================
        # LEVEL-1 THRESHOLDS (Momentum Gate)
        # ================================================================
        self.min_price_change_1h = self.config.get('min_price_change_1h', 5.0)  # 5% gain in 1h
        self.min_volume_spike_ratio = self.config.get('min_volume_spike_ratio', 2.0)  # 2.0x volume spike
        
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
        Apply Level-0 filters (Quality Gate).
        
        Checks:
        - liquidity >= min_liquidity
        - volume_1h >= min_volume_1h
        - tx_1h >= min_tx_1h
        - age <= max_age_hours (if enabled)
        
        Returns:
            (passed: bool, reason: str or None)
        """
        # ================================================================
        # CHECK 1: Liquidity
        # ================================================================
        liquidity = pair.get('liquidity', 0)
        if liquidity < self.min_liquidity:
            return False, f"Low liquidity (${liquidity:,.0f} < ${self.min_liquidity:,})"
        
        # ================================================================
        # CHECK 2: Volume (H1 - direct from API)
        # ================================================================
        volume_1h = pair.get('volume_1h')
        
        if volume_1h is None or volume_1h < self.min_volume_1h:
            vol_display = f"${volume_1h:,.0f}" if volume_1h else "N/A"
            return False, f"Low h1 volume ({vol_display} < ${self.min_volume_1h:,})"
        
        # ================================================================
        # CHECK 3: Transaction Count (H1 - direct from API)
        # ================================================================
        tx_1h = pair.get('tx_1h')
        
        if tx_1h is None or tx_1h < self.min_tx_1h:
            tx_display = f"{tx_1h:.0f}" if tx_1h else "N/A"
            return False, f"Low h1 transactions ({tx_display} < {self.min_tx_1h})"
        
        # ================================================================
        # CHECK 4: Age (if enabled)
        # ================================================================
        if self.max_age_hours is not None:
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
        - Strong price change in 1h
        - Volume spike (h1 vs h24 average)
        
        Returns:
            (passed: bool, reason: str or None)
        """
        reasons = []
        
        # ================================================================
        # CHECK 1: Price Momentum (h1 only - DexScreener native)
        # ================================================================
        # DexScreener provides h1 price change, which is reliable
        # m5 price change is often missing/unreliable, so we don't use it
        price_change_1h = pair.get('price_change_1h', 0) or 0
        
        has_price_momentum = price_change_1h >= self.min_price_change_1h
        
        if not has_price_momentum:
            reasons.append(f"Weak price momentum (1h: {price_change_1h:.1f}% < {self.min_price_change_1h:.1f}%)")
        
        # ================================================================
        # CHECK 2: Volume Spike (h1 vs h24 average)
        # ================================================================
        # Compare h1 volume to average hourly volume from h24
        # If h1 > 1.3x average hourly → spike!
        volume_1h = pair.get('volume_1h', 0) or 0
        volume_24h = pair.get('volume_24h', 0) or 0
        
        volume_spike_ratio = 0
        
        if volume_24h > 0 and volume_1h > 0:
            # Calculate average hourly volume from 24h data
            avg_hourly_volume = volume_24h / 24
            
            # Compare current hour to average
            volume_spike_ratio = volume_1h / avg_hourly_volume
        
        has_volume_spike = volume_spike_ratio >= self.min_volume_spike_ratio
        
        if not has_volume_spike:
            reasons.append(f"No volume spike (h1/avg: {volume_spike_ratio:.2f}x < {self.min_volume_spike_ratio:.2f}x)")
        
        # ================================================================
        # PASS CRITERIA: At least ONE momentum signal
        # ================================================================
        if has_price_momentum or has_volume_spike:
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
