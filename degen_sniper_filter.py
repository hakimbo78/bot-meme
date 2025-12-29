"""
MODE C: DEGEN SNIPER FILTERS

EXTREMELY AGGRESSIVE filtering system for ultra-early token detection.

This implementation follows the exact specifications:
- Global guardrails to reject obvious garbage
- Level-0: Very loose viability check (ANY potential)
- Level-1: Early momentum triggers (ANY movement)
- Level-2: Structural quality (at least 2 conditions)
- Bonus signals for fresh LP, txn ratio, Solana activity
- Smart deduplication with bypass conditions
- Chain-specific rules
- Rate limiting

100% DexScreener API compliant (h1 and h24 only).
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta


class DegenSniperFilter:
    """
    MODE C: DEGEN SNIPER Filter
    
    Ultra-aggressive filtering for early detection while maintaining quality guardrails.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize DEGEN SNIPER filter.
        
        Args:
            config: DEGEN SNIPER configuration dict
        """
        self.config = config or {}
        
        # Extract configuration sections
        self.global_guardrails = self.config.get('global_guardrails', {})
        self.level_0 = self.config.get('level_0_viability', {})
        self.level_1 = self.config.get('level_1_momentum', {})
        self.level_2 = self.config.get('level_2_quality', {})
        self.bonus = self.config.get('bonus_signals', {})
        self.scoring = self.config.get('scoring', {})
        self.chain_rules = self.config.get('chain_rules', {})
        self.dedup_config = self.config.get('deduplication', {})
        self.rate_limit = self.config.get('rate_limiting', {})
        
        # Track seen pairs for deduplication
        self.seen_pairs = {}  # pair_address -> last_seen_data
        
        # Track alerts for rate limiting
        self.alert_history = {}  # pair_address -> list of alert timestamps
        self.chain_alert_history = {}  # chain -> list of alert timestamps
        
        # Statistics
        self.stats = {
            'total_evaluated': 0,
            'guardrail_rejected': 0,
            'level_0_rejected': 0,
            'level_1_failed': 0,
            'level_2_failed': 0,
            'score_failed': 0,
            'rate_limited': 0,
            'passed': 0,
        }
    
    def apply_filters(self, pair: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Apply all DEGEN SNIPER filters to a pair.
        
        Args:
            pair: Normalized pair data from DexScreener
            
        Returns:
            (passed: bool, reason: str or None, metadata: dict or None)
        """
        self.stats['total_evaluated'] += 1
        
        pair_address = pair.get('pair_address', 'UNKNOWN')
        chain = pair.get('chain', 'UNKNOWN').lower()
        
        # ================================================================
        # GLOBAL GUARDRAILS (MANDATORY)
        # ================================================================
        passed, reason = self._check_global_guardrails(pair)
        if not passed:
            self.stats['guardrail_rejected'] += 1
            self._log_evaluation(pair, 'GUARDRAIL_REJECT', reason, 0, [])
            return False, f"GUARDRAIL: {reason}", None
        
        # ================================================================
        # LEVEL-0: VIABILITY CHECK (VERY LOOSE)
        # ================================================================
        passed, reason = self._check_level_0(pair)
        if not passed:
            self.stats['level_0_rejected'] += 1
            self._log_evaluation(pair, 'LEVEL_0_FAIL', reason, 0, [])
            return False, f"LEVEL-0: {reason}", None
        
        # ================================================================
        # LEVEL-1: EARLY MOMENTUM TRIGGERS (ANY)
        # ================================================================
        level_1_triggered, l1_flags = self._check_level_1(pair)
        
        # ================================================================
        # LEVEL-2: STRUCTURAL QUALITY (AT LEAST 2)
        # ================================================================
        level_2_passed, l2_count, l2_flags = self._check_level_2(pair)
        
        # ================================================================
        # BONUS SIGNALS
        # ================================================================
        bonus_score, bonus_flags = self._check_bonus_signals(pair)
        
        # ================================================================
        # SCORING
        # ================================================================
        score = 0
        reason_flags = []
        
        # Level-1 points
        if level_1_triggered:
            score += self.scoring.get('level_1_trigger_points', 1)
            reason_flags.extend(l1_flags)
        
        # Level-2 points
        if level_2_passed:
            score += self.scoring.get('level_2_pass_points', 2)
            reason_flags.extend(l2_flags)
        else:
            # Level-2 failed
            self.stats['level_2_failed'] += 1
        
        # Bonus points (capped)
        max_bonus = self.scoring.get('max_bonus_points', 2)
        bonus_score = min(bonus_score, max_bonus)
        score += bonus_score
        reason_flags.extend(bonus_flags)
        
        # Check minimum score
        min_score = self.scoring.get('min_score_to_pass', 3)
        if score < min_score:
            self.stats['score_failed'] += 1
            reason = f"Score too low ({score} < {min_score})"
            self._log_evaluation(pair, 'SCORE_FAIL', reason, score, reason_flags)
            return False, f"SCORE: {reason}", None
        
        # ================================================================
        # DEDUPLICATION (SMART)
        # ================================================================
        is_duplicate = self._check_deduplication(pair)
        if is_duplicate:
            # Don't increment stats for duplicates within cooldown
            reason = "Duplicate within cooldown"
            self._log_evaluation(pair, 'DUPLICATE', reason, score, reason_flags)
            return False, f"DEDUP: {reason}", None
        
        # ================================================================
        # RATE LIMITING
        # ================================================================
        rate_limited, limit_reason = self._check_rate_limit(pair)
        if rate_limited:
            self.stats['rate_limited'] += 1
            self._log_evaluation(pair, 'RATE_LIMITED', limit_reason, score, reason_flags)
            return False, f"RATE_LIMIT: {limit_reason}", None
        
        # ================================================================
        # PASSED ALL FILTERS
        # ================================================================
        self.stats['passed'] += 1
        
        # Record alert
        self._record_alert(pair)
        
        # Build metadata
        metadata = {
            'score': score,
            'reason_flags': reason_flags,
            'level_1_triggered': level_1_triggered,
            'level_2_passed': level_2_passed,
            'level_2_count': l2_count,
            'bonus_score': bonus_score,
        }
        
        self._log_evaluation(pair, 'PASS', 'All filters passed', score, reason_flags)
        
        return True, None, metadata
    
    def _check_global_guardrails(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check mandatory global guardrails.
        
        Reject if:
        - liquidity.usd < 3000
        - volume.h24 == 0
        - pair age > 24h AND not trending
        - missing core fields
        """
        # Check liquidity
        liquidity = pair.get('liquidity', 0) or 0
        min_liq = self.global_guardrails.get('min_liquidity_usd', 3000)
        if liquidity < min_liq:
            return False, f"Liquidity too low (${liquidity:.0f} < ${min_liq})"
        
        # Check h24 volume
        volume_h24 = pair.get('volume_24h', 0) or 0
        if self.global_guardrails.get('require_h24_volume', True) and volume_h24 == 0:
            return False, "Zero h24 volume"
        
        # Check pair age (if available)
        pair_age_hours = pair.get('pair_age_hours', 0)
        max_age = self.global_guardrails.get('max_age_hours_if_not_trending', 24)
        is_trending = pair.get('is_trending', False)
        
        if pair_age_hours > max_age and not is_trending:
            return False, f"Too old without trending ({pair_age_hours:.0f}h > {max_age}h)"
        
        # Check core fields
        if self.global_guardrails.get('require_core_fields', True):
            required = ['pair_address', 'chain', 'liquidity']
            missing = [f for f in required if not pair.get(f)]
            if missing:
                return False, f"Missing core fields: {missing}"
        
        return True, None
    
    def _check_level_0(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        Level-0: Viability check (VERY LOOSE).
        
        PASS if ANY is true:
        - liquidity.usd >= 5000
        - volume.h24 >= 2000
        """
        liquidity = pair.get('liquidity', 0) or 0
        volume_h24 = pair.get('volume_24h', 0) or 0
        
        min_liq = self.level_0.get('min_liquidity_usd', 5000)
        min_vol = self.level_0.get('min_volume_h24', 2000)
        
        if liquidity >= min_liq:
            return True, None
        
        if volume_h24 >= min_vol:
            return True, None
        
        return False, f"No viability signal (Liq:${liquidity:.0f}, Vol24h:${volume_h24:.0f})"
    
    def _check_level_1(self, pair: Dict) -> Tuple[bool, List[str]]:
        """
        Level-1: Early momentum triggers (ANY).
        
        Trigger if ANY is true:
        - txns.h1 >= 1
        - volume.h1 >= 10
        - priceChange.h1 != 0
        
        Returns:
            (triggered: bool, flags: list of trigger reasons)
        """
        flags = []
        
        txns_h1 = pair.get('tx_1h', 0) or 0
        volume_h1 = pair.get('volume_1h', 0) or 0
        price_change_h1 = pair.get('price_change_1h', 0) or 0
        
        min_txns = self.level_1.get('min_txns_h1', 1)
        min_vol = self.level_1.get('min_volume_h1', 10)
        
        if txns_h1 >= min_txns:
            flags.append('EARLY_TX')
        
        if volume_h1 >= min_vol:
            flags.append('EARLY_VOL')
        
        if self.level_1.get('detect_any_price_change_h1', True) and price_change_h1 != 0:
            flags.append('PRICE_MOVE')
        
        triggered = len(flags) > 0
        return triggered, flags
    
    def _check_level_2(self, pair: Dict) -> Tuple[bool, int, List[str]]:
        """
        Level-2: Structural quality (AT LEAST 2 conditions).
        
        Require at least 2 of:
        - liquidity.usd >= 10000
        - volume.h24 >= 10000
        - txns.h24 >= 20
        - abs(priceChange.h24) >= 5
        
        Returns:
            (passed: bool, count: int, flags: list of met conditions)
        """
        flags = []
        conditions = self.level_2.get('conditions', {})
        
        liquidity = pair.get('liquidity', 0) or 0
        volume_h24 = pair.get('volume_24h', 0) or 0
        txns_h24 = pair.get('tx_24h', 0) or 0
        price_change_h24 = pair.get('price_change_24h', 0) or 0
        
        if liquidity >= conditions.get('liquidity_usd', 10000):
            flags.append('GOOD_LIQ')
        
        if volume_h24 >= conditions.get('volume_h24', 10000):
            flags.append('GOOD_VOL')
        
        if txns_h24 >= conditions.get('txns_h24', 20):
            flags.append('GOOD_TXN')
        
        if abs(price_change_h24) >= conditions.get('abs_price_change_h24', 5):
            flags.append('VOLATILE')
        
        count = len(flags)
        require_count = self.level_2.get('require_count', 2)
        passed = count >= require_count
        
        return passed, count, flags
    
    def _check_bonus_signals(self, pair: Dict) -> Tuple[int, List[str]]:
        """
        Check bonus early signals.
        
        Add +1 for each:
        - liquidity > volume_h24 (fresh LP)
        - txns.h1 / max(txns.h24, 1) >= 0.2
        - chain == SOLANA AND txns.h24 >= 10
        
        Returns:
            (bonus_score: int, flags: list of bonus reasons)
        """
        score = 0
        flags = []
        
        liquidity = pair.get('liquidity', 0) or 0
        volume_h24 = pair.get('volume_24h', 0) or 0
        txns_h1 = pair.get('tx_1h', 0) or 0
        txns_h24 = pair.get('tx_24h', 0) or 0
        chain = pair.get('chain', '').lower()
        
        # Fresh LP
        fresh_lp = self.bonus.get('fresh_lp', {})
        if fresh_lp.get('enabled', True) and liquidity > volume_h24:
            score += 1
            flags.append('FRESH_LP')
        
        # H1/H24 txn ratio
        ratio_config = self.bonus.get('h1_h24_txn_ratio', {})
        if ratio_config.get('enabled', True):
            min_ratio = ratio_config.get('min_ratio', 0.2)
            actual_ratio = txns_h1 / max(txns_h24, 1)
            if actual_ratio >= min_ratio:
                score += 1
                flags.append('WARMUP')
        
        # Solana active
        solana_config = self.bonus.get('solana_active', {})
        if solana_config.get('enabled', True):
            if chain == 'solana' and txns_h24 >= solana_config.get('min_txns_h24', 10):
                score += 1
                flags.append('SOL_ACTIVE')
        
        return score, flags
    
    def _check_deduplication(self, pair: Dict) -> bool:
        """
        Smart deduplication with bypass conditions.
        
        Base cooldown: 120 seconds
        Bypass if ANY changes since last scan:
        - txns.h1 increased
        - volume.h1 increased >= 5
        - abs(priceChange.h1) changed >= 0.1%
        
        Returns:
            True if duplicate (should skip), False if should process
        """
        pair_address = pair.get('pair_address')
        if not pair_address:
            return False
        
        # Check if we've seen this pair before
        if pair_address not in self.seen_pairs:
            # First time seeing this pair
            self.seen_pairs[pair_address] = {
                'timestamp': datetime.now(),
                'txns_h1': pair.get('tx_1h', 0) or 0,
                'volume_h1': pair.get('volume_1h', 0) or 0,
                'price_change_h1': pair.get('price_change_1h', 0) or 0,
            }
            return False
        
        last_seen = self.seen_pairs[pair_address]
        now = datetime.now()
        cooldown_seconds = self.dedup_config.get('base_cooldown_seconds', 120)
        
        # Check if still in cooldown
        time_since_last = (now - last_seen['timestamp']).total_seconds()
        if time_since_last < cooldown_seconds:
            # Check bypass conditions
            bypass = self.dedup_config.get('bypass_conditions', {})
            
            current_txns_h1 = pair.get('tx_1h', 0) or 0
            current_volume_h1 = pair.get('volume_1h', 0) or 0
            current_price_h1 = pair.get('price_change_1h', 0) or 0
            
            last_txns_h1 = last_seen['txns_h1']
            last_volume_h1 = last_seen['volume_h1']
            last_price_h1 = last_seen['price_change_h1']
            
            # Check txns.h1 increased
            if bypass.get('txns_h1_increased', True) and current_txns_h1 > last_txns_h1:
                # Bypass cooldown
                self.seen_pairs[pair_address] = {
                    'timestamp': now,
                    'txns_h1': current_txns_h1,
                    'volume_h1': current_volume_h1,
                    'price_change_h1': current_price_h1,
                }
                return False
            
            # Check volume.h1 increased >= threshold
            vol_threshold = bypass.get('volume_h1_increased', 5)
            if current_volume_h1 >= last_volume_h1 + vol_threshold:
                # Bypass cooldown
                self.seen_pairs[pair_address] = {
                    'timestamp': now,
                    'txns_h1': current_txns_h1,
                    'volume_h1': current_volume_h1,
                    'price_change_h1': current_price_h1,
                }
                return False
            
            # Check abs price change delta
            price_delta_threshold = bypass.get('abs_price_change_h1_delta', 0.1)
            price_delta = abs(current_price_h1 - last_price_h1)
            if price_delta >= price_delta_threshold:
                # Bypass cooldown
                self.seen_pairs[pair_address] = {
                    'timestamp': now,
                    'txns_h1': current_txns_h1,
                    'volume_h1': current_volume_h1,
                    'price_change_h1': current_price_h1,
                }
                return False
            
            # Still in cooldown, no bypass
            return True
        
        # Cooldown expired, update last seen
        self.seen_pairs[pair_address] = {
            'timestamp': now,
            'txns_h1': pair.get('tx_1h', 0) or 0,
            'volume_h1': pair.get('volume_1h', 0) or 0,
            'price_change_h1': pair.get('price_change_1h', 0) or 0,
        }
        return False
    
    def _check_rate_limit(self, pair: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check alert rate limits.
        
        - Max 1 alert per pair per 10 minutes
        - Max 10 alerts per chain per hour
        
        Returns:
            (rate_limited: bool, reason: str or None)
        """
        pair_address = pair.get('pair_address')
        chain = pair.get('chain', '').lower()
        now = datetime.now()
        
        # Check per-pair limit
        max_per_pair = self.rate_limit.get('max_alerts_per_pair_per_10min', 1)
        if pair_address in self.alert_history:
            recent_alerts = [
                ts for ts in self.alert_history[pair_address]
                if (now - ts).total_seconds() < 600  # 10 minutes
            ]
            if len(recent_alerts) >= max_per_pair:
                return True, f"Pair limit exceeded ({len(recent_alerts)}/{max_per_pair} in 10min)"
        
        # Check per-chain limit
        max_per_chain = self.rate_limit.get('max_alerts_per_chain_per_hour', 10)
        if chain in self.chain_alert_history:
            recent_chain_alerts = [
                ts for ts in self.chain_alert_history[chain]
                if (now - ts).total_seconds() < 3600  # 1 hour
            ]
            if len(recent_chain_alerts) >= max_per_chain:
                return True, f"Chain limit exceeded ({len(recent_chain_alerts)}/{max_per_chain} in 1h)"
        
        return False, None
    
    def _record_alert(self, pair: Dict):
        """Record alert for rate limiting."""
        pair_address = pair.get('pair_address')
        chain = pair.get('chain', '').lower()
        now = datetime.now()
        
        # Record pair alert
        if pair_address:
            if pair_address not in self.alert_history:
                self.alert_history[pair_address] = []
            self.alert_history[pair_address].append(now)
            
            # Clean old alerts (> 10 minutes)
            self.alert_history[pair_address] = [
                ts for ts in self.alert_history[pair_address]
                if (now - ts).total_seconds() < 600
            ]
        
        # Record chain alert
        if chain:
            if chain not in self.chain_alert_history:
                self.chain_alert_history[chain] = []
            self.chain_alert_history[chain].append(now)
            
            # Clean old alerts (> 1 hour)
            self.chain_alert_history[chain] = [
                ts for ts in self.chain_alert_history[chain]
                if (now - ts).total_seconds() < 3600
            ]
    
    def _log_evaluation(self, pair: Dict, status: str, reason: str, 
                       score: int, flags: List[str]):
        """
        Log pair evaluation in detailed format.
        
        Output format:
        [DEGEN_SNIPER] [CHAIN] pair_address | Liq | Vol1h/24h | Tx1h/24h | Δ1h/24h | Score | Flags | Status
        """
        chain = pair.get('chain', 'UNKNOWN').upper()
        pair_addr = pair.get('pair_address', 'UNKNOWN')
        if len(pair_addr) > 10:
            pair_addr = pair_addr[:8] + '...'
        
        liquidity = pair.get('liquidity', 0) or 0
        volume_h1 = pair.get('volume_1h', 0) or 0
        volume_h24 = pair.get('volume_24h', 0) or 0
        txns_h1 = pair.get('tx_1h', 0) or 0
        txns_h24 = pair.get('tx_24h', 0) or 0
        price_change_h1 = pair.get('price_change_1h', 0) or 0
        price_change_h24 = pair.get('price_change_24h', 0) or 0
        
        # Format values
        liq_str = f"${liquidity/1000:.1f}k" if liquidity >= 1000 else f"${liquidity:.0f}"
        vol_str = f"${volume_h1:.0f}/${volume_h24:.0f}"
        tx_str = f"{txns_h1:.0f}/{txns_h24:.0f}"
        delta_str = f"{price_change_h1:+.1f}%/{price_change_h24:+.1f}%"
        flags_str = ','.join(flags) if flags else 'NONE'
        
        status_emoji = {
            'PASS': '✅',
            'GUARDRAIL_REJECT': '❌',
            'LEVEL_0_FAIL': '❌',
            'SCORE_FAIL': '⚠️',
            'DUPLICATE': '⏭️',
            'RATE_LIMITED': '🚫',
        }.get(status, '❓')
        
        print(
            f"[DEGEN_SNIPER] [{chain}] {pair_addr} | "
            f"Liq:{liq_str} | Vol:{vol_str} | Tx:{tx_str} | "
            f"Δ:{delta_str} | Score:{score} | "
            f"Flags:[{flags_str}] | {status_emoji} {status}"
        )
        
        if reason and status != 'PASS':
            print(f"  └─ Reason: {reason}")
    
    def get_stats(self) -> Dict:
        """Get filter statistics."""
        total = self.stats['total_evaluated']
        if total == 0:
            pass_rate = 0
        else:
            pass_rate = (self.stats['passed'] / total) * 100
        
        return {
            **self.stats,
            'pass_rate_pct': pass_rate,
            'filter_rate_pct': 100 - pass_rate if total > 0 else 0,
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            'total_evaluated': 0,
            'guardrail_rejected': 0,
            'level_0_rejected': 0,
            'level_1_failed': 0,
            'level_2_failed': 0,
            'score_failed': 0,
            'rate_limited': 0,
            'passed': 0,
        }
