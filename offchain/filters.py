"""
OFF-CHAIN FILTERS - AGGRESSIVE MODE (REALISTIC)

Three-level filtering system for fast sniper execution:

LEVEL-0 (VIABILITY CHECK):
- Checks if pair is alive (not dead/honeypot)
- PASS if: liq >= 10k AND (vol24h >= 100 OR tx24h >= 5 OR priceChange24h != 0)

LEVEL-1 (MOMENTUM DETECTION):
- Scoring system (NOT hard gates)
- Score calculation:
  +2: volume.h1 >= 50
  +1: volume.h1 >= 20
  +2: txns.h1 >= 3
  +1: txns.h1 >= 1
  +1: priceChange.h1 > 0
  +1: priceChange.h24 > 5%
- PASS if: score >= 3

LEVEL-2 (FAKE LIQUIDITY CHECK):
- DROP if: liq > 500k AND vol24h < 200 AND tx24h < 10
- Otherwise: PASS

DexScreener API fields used (100% compliant):
- liquidity.usd
- volume.h1, volume.h24
- txns.h1, txns.h24
- priceChange.h1, priceChange.h24
"""

from typing import Dict, Optional


class OffChainFilter:
    """
    Multi-level off-chain filter - AGGRESSIVE MODE (REALISTIC).
    
    Designed to:
    1. NOT kill all pairs in Level-0
    2. Allow pairs with volume.h1 = 0 to pass
    3. Use scoring instead of hard gates
    4. Be realistic for slow market conditions
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize filter with configuration.
        
        Args:
            config: Filter configuration dict
        """
        self.config = config or {}
        
        # ================================================================
        # LEVEL-0 THRESHOLDS (Viability Check)
        # ================================================================
        self.min_liquidity = self.config.get('min_liquidity', 10000)  # $10k minimum
        
        # ================================================================
        # LEVEL-1 THRESHOLDS (Momentum Scoring)
        # ================================================================
        self.momentum_score_threshold = self.config.get('momentum_score_threshold', 3)
        
        # ================================================================
        # LEVEL-2 THRESHOLDS (Fake Liquidity Check)
        # ================================================================
        self.fake_liq_threshold = self.config.get('fake_liq_threshold', 500000)
        self.fake_liq_min_volume_24h = self.config.get('fake_liq_min_volume_24h', 200)
        self.fake_liq_min_tx_24h = self.config.get('fake_liq_min_tx_24h', 10)
        
        # DEXTools guarantee rule
        self.dextools_top_rank = self.config.get('dextools_top_rank', 50)
        
        # Track filter stats
        self.stats = {
            'total_evaluated': 0,
            'level0_filtered': 0,
            'level1_filtered': 0,
            'level2_filtered': 0,
            'passed': 0,
            'dextools_forced': 0,
        }
    
    def apply_filters(self, normalized_pair: Dict) -> tuple[bool, Optional[str], Optional[Dict]]:
        """
        Apply all filter levels to a normalized pair.
        
        Args:
            normalized_pair: Normalized pair event dict
            
        Returns:
            (passed: bool, reason: str or None, metadata: dict)
            - True + None + metadata: Pair passed all filters
            - False + reason + None: Pair filtered out with reason
        """
        self.stats['total_evaluated'] += 1
        
        # Extract key metrics for logging
        pair_addr = normalized_pair.get('pair_address', 'UNKNOWN')[:8]
        chain = normalized_pair.get('chain', 'UNKNOWN').upper()
        
        liquidity = normalized_pair.get('liquidity', 0) or 0
        volume_1h = normalized_pair.get('volume_1h', 0) or 0
        volume_24h = normalized_pair.get('volume_24h', 0) or 0
        tx_1h = normalized_pair.get('tx_1h', 0) or 0
        tx_24h = normalized_pair.get('tx_24h', 0) or 0
        price_change_1h = normalized_pair.get('price_change_1h', 0) or 0
        price_change_24h = normalized_pair.get('price_change_24h', 0) or 0
        
        # DEXTOOLS GUARANTEE RULE
        if self._check_dextools_guarantee(normalized_pair):
            self.stats['dextools_forced'] += 1
            self.stats['passed'] += 1
            
            metadata = {
                'level0': 'BYPASS',
                'level1': 'BYPASS',
                'level2': 'BYPASS',
                'final': 'PASS',
                'reason': 'DEXTOOLS_GUARANTEE'
            }
            
            self._log_evaluation(
                pair_addr, chain, liquidity, volume_1h, tx_1h, 
                volume_24h, tx_24h, price_change_1h, price_change_24h,
                'BYPASS', 'BYPASS (DEXTOOLS)', 'PASS'
            )
            
            return True, None, metadata
        
        # ================================================================
        # LEVEL-0: VIABILITY CHECK
        # ================================================================
        passed, reason = self._apply_level_0(normalized_pair)
        level0_status = 'PASS' if passed else f'FAIL ({reason})'
        
        if not passed:
            self.stats['level0_filtered'] += 1
            
            self._log_evaluation(
                pair_addr, chain, liquidity, volume_1h, tx_1h,
                volume_24h, tx_24h, price_change_1h, price_change_24h,
                level0_status, '-', f'FILTERED: {reason}'
            )
            
            return False, f"Level-0: {reason}", None
        
        # ================================================================
        # LEVEL-1: MOMENTUM SCORING
        # ================================================================
        passed, reason, score = self._apply_level_1(normalized_pair)
        level1_status = f'PASS (score={score})' if passed else f'FAIL (score={score})'
        
        if not passed:
            self.stats['level1_filtered'] += 1
            
            self._log_evaluation(
                pair_addr, chain, liquidity, volume_1h, tx_1h,
                volume_24h, tx_24h, price_change_1h, price_change_24h,
                level0_status, level1_status, f'FILTERED: {reason}'
            )
            
            return False, f"Level-1: {reason}", None
        
        # ================================================================
        # LEVEL-2: FAKE LIQUIDITY CHECK
        # ================================================================
        passed, reason = self._apply_level_2(normalized_pair)
        level2_status = 'PASS' if passed else f'FAIL ({reason})'
        
        if not passed:
            self.stats['level2_filtered'] += 1
            
            self._log_evaluation(
                pair_addr, chain, liquidity, volume_1h, tx_1h,
                volume_24h, tx_24h, price_change_1h, price_change_24h,
                level0_status, level1_status, f'FILTERED: {reason}'
            )
            
            return False, f"Level-2: {reason}", None
        
        # ================================================================
        # ALL FILTERS PASSED
        # ================================================================
        self.stats['passed'] += 1
        
        metadata = {
            'level0': 'PASS',
            'level1': f'PASS (score={score})',
            'level2': 'PASS',
            'final': 'PASS',
            'momentum_score': score
        }
        
        self._log_evaluation(
            pair_addr, chain, liquidity, volume_1h, tx_1h,
            volume_24h, tx_24h, price_change_1h, price_change_24h,
            level0_status, level1_status, '✅ PASS'
        )
        
        return True, None, metadata
    
    def _check_dextools_guarantee(self, pair: Dict) -> bool:
        """
        Check if pair meets DEXTools guarantee criteria.
        
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
        Apply Level-0 filters (Viability Check).
        
        PASS if:
        - liquidity.usd >= 10,000
        - AND (volume.h24 >= 100 OR txns.h24 >= 5 OR priceChange.h24 != 0)
        
        Returns:
            (passed: bool, reason: str or None)
        """
        # CHECK 1: Liquidity
        liquidity = pair.get('liquidity', 0) or 0
        
        if liquidity < self.min_liquidity:
            return False, f"Low liquidity (${liquidity:,.0f} < ${self.min_liquidity:,})"
        
        # CHECK 2: ANY activity in 24h
        volume_24h = pair.get('volume_24h', 0) or 0
        tx_24h = pair.get('tx_24h', 0) or 0
        price_change_24h = pair.get('price_change_24h', 0) or 0
        
        has_volume = volume_24h >= 100
        has_txns = tx_24h >= 5
        has_price_change = price_change_24h != 0
        
        if not (has_volume or has_txns or has_price_change):
            return False, f"No activity (V24h:${volume_24h:.0f}, Tx24h:{tx_24h}, Δ24h:{price_change_24h:.1f}%)"
        
        return True, None
    
    def _apply_level_1(self, pair: Dict) -> tuple[bool, Optional[str], int]:
        """
        Apply Level-1 filters (Momentum Scoring).
        
        Scoring:
        +2 if volume.h1 >= 50
        +1 if volume.h1 >= 20
        +2 if txns.h1 >= 3
        +1 if txns.h1 >= 1
        +1 if priceChange.h1 > 0
        +1 if priceChange.h24 > 5%
        
        PASS if: score >= 3
        
        Returns:
            (passed: bool, reason: str or None, score: int)
        """
        score = 0
        
        # Extract metrics (handle None safely)
        volume_1h = pair.get('volume_1h', 0) or 0
        tx_1h = pair.get('tx_1h', 0) or 0
        price_change_1h = pair.get('price_change_1h', 0) or 0
        price_change_24h = pair.get('price_change_24h', 0) or 0
        
        # Scoring logic
        if volume_1h >= 50:
            score += 2
        elif volume_1h >= 20:
            score += 1
        
        if tx_1h >= 3:
            score += 2
        elif tx_1h >= 1:
            score += 1
        
        if price_change_1h > 0:
            score += 1
        
        if price_change_24h > 5:
            score += 1
        
        # Pass criteria
        if score >= self.momentum_score_threshold:
            return True, None, score
        
        # Failed
        reason = f"Low momentum score ({score} < {self.momentum_score_threshold})"
        return False, reason, score
    
    def _apply_level_2(self, pair: Dict) -> tuple[bool, Optional[str]]:
        """
        Apply Level-2 filters (Fake Liquidity Check).
        
        DROP if:
        - liquidity > 500k AND volume.h24 < 200 AND txns.h24 < 10
        
        Otherwise: PASS
        
        Returns:
            (passed: bool, reason: str or None)
        """
        liquidity = pair.get('liquidity', 0) or 0
        volume_24h = pair.get('volume_24h', 0) or 0
        tx_24h = pair.get('tx_24h', 0) or 0
        
        # Check for fake liquidity pattern
        if liquidity > self.fake_liq_threshold:
            if volume_24h < self.fake_liq_min_volume_24h and tx_24h < self.fake_liq_min_tx_24h:
                return False, f"Fake liquidity (Liq:${liquidity:,.0f}, V24h:${volume_24h:.0f}, Tx24h:{tx_24h})"
        
        return True, None
    
    def _log_evaluation(self, pair_addr: str, chain: str, liquidity: float,
                       volume_1h: float, tx_1h: int, volume_24h: float, tx_24h: int,
                       price_change_1h: float, price_change_24h: float,
                       level0: str, level1: str, final: str):
        """
        Log pair evaluation in detailed format.
        
        Format:
        PAIR | Liq | Vol1h | Tx1h | Vol24h | Tx24h | Δ1h | Δ24h | L0 | L1 | FINAL
        """
        # Format values
        liq_str = f"${liquidity/1000:.0f}k" if liquidity >= 1000 else f"${liquidity:.0f}"
        vol1h_str = f"${volume_1h:.0f}" if volume_1h > 0 else "N/A"
        tx1h_str = f"{tx_1h:.0f}" if tx_1h > 0 else "0"
        vol24h_str = f"${volume_24h:.0f}"
        tx24h_str = f"{tx_24h:.0f}"
        delta1h_str = f"{price_change_1h:+.1f}%"
        delta24h_str = f"{price_change_24h:+.1f}%"
        
        print(
            f"[OFFCHAIN] [{chain}] {pair_addr}... | "
            f"Liq:{liq_str} | V1h:{vol1h_str} | Tx1h:{tx1h_str} | "
            f"V24h:{vol24h_str} | Tx24h:{tx24h_str} | "
            f"Δ1h:{delta1h_str} | Δ24h:{delta24h_str} | "
            f"L0:{level0} | L1:{level1} | {final}"
        )
    
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
            filtered = (
                self.stats['level0_filtered'] + 
                self.stats['level1_filtered'] + 
                self.stats['level2_filtered']
            )
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
            'level2_filtered': 0,
            'passed': 0,
            'dextools_forced': 0,
        }
