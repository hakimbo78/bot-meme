"""
Solana Sniper - High-Risk Early Token Detection

Sniper trigger criteria (ALL MUST PASS):
- Source = Pump.fun
- Token age ≤ 120 seconds
- SOL inflow ≥ 10 SOL
- Buy velocity ≥ 15/min
- Creator has NOT sold
- No Raydium migration yet

Output: SOLANA_SNIPER alert

CRITICAL: 
- READ-ONLY - No execution, no wallets
- HIGH RISK - Alerts include explicit warnings
"""
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .solana_utils import (
    solana_log,
    shorten_address,
    SNIPER_MAX_AGE,
    SOL_INFLOW_MEDIUM,
    BUY_VELOCITY_MEDIUM
)
from .solana_score_engine import SolanaScoreEngine


@dataclass
class SniperConfig:
    """Configuration for Solana sniper mode."""
    enabled: bool = True
    max_age_seconds: int = 120
    min_sol_inflow: float = 10.0
    min_buy_velocity: float = 15.0
    min_sniper_score: int = 70
    cooldown_minutes: int = 30
    max_alerts_per_hour: int = 10


class SolanaSniperDetector:
    """
    Detects early Solana tokens suitable for sniper alerts.
    
    HIGH RISK MODE - Tokens are very new with minimal validation.
    All alerts include explicit risk warnings.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize sniper detector.
        
        Args:
            config: Solana chain config with sniper settings
        """
        chain_config = config or {}
        sniper_config = chain_config.get('sniper', {})
        
        self.config = SniperConfig(
            enabled=sniper_config.get('enabled', True),
            max_age_seconds=sniper_config.get('max_age_seconds', 120),
            min_sol_inflow=sniper_config.get('min_sol_inflow', 10.0),
            min_buy_velocity=sniper_config.get('min_buy_velocity', 15.0),
            min_sniper_score=sniper_config.get('min_sniper_score', 70),
            cooldown_minutes=sniper_config.get('cooldown_minutes', 30),
            max_alerts_per_hour=sniper_config.get('max_alerts_per_hour', 10)
        )
        
        self.score_engine = SolanaScoreEngine(chain_config)
        
        # Cooldown tracking
        self._alerted_tokens: Dict[str, float] = {}  # token -> timestamp
        self._alerts_this_hour: List[float] = []  # timestamps
        
        # Debug Configuration
        debug_config = chain_config.get('debug', {})
        self.debug_enabled = debug_config.get('enabled', False)
        self.log_top_n = debug_config.get('log_top_n', 3)
        self.log_interval_seconds = debug_config.get('log_interval_seconds', 30)
        
        # Throttled logging state
        self._last_log_time = time.time()
        self._candidate_buffer = []

        # Stats
        self._stats = {
            'total_checked': 0,
            'total_passed': 0,
            'total_alerted': 0
        }
    
    def is_enabled(self) -> bool:
        """Check if sniper mode is enabled."""
        return self.config.enabled
    
    def check_sniper_eligibility(self, token_data: Dict) -> Dict:
        """
        Check if token is eligible for sniper alert.
        
        Args:
            token_data: Unified token data from SolanaScanner
            
        Returns:
            Dict with:
            - eligible: bool
            - trigger_reasons: list[str] (why it passed)
            - skip_reasons: list[str] (why it failed)
            - sniper_score: int (if eligible)
        """
        self._stats['total_checked'] += 1
        
        result = {
            'eligible': False,
            'trigger_reasons': [],
            'skip_reasons': [],
            'sniper_score': 0
        }
        
        if not self.config.enabled:
            result['skip_reasons'].append("Sniper mode disabled")
            return result
        
        token_address = token_data.get('token_address', token_data.get('address', ''))
        
        # =====================================================================
        # COOLDOWN CHECK
        # =====================================================================
        if self._is_on_cooldown(token_address):
            result['skip_reasons'].append("On cooldown")
            return result
        
        # =====================================================================
        # HOURLY RATE LIMIT
        # =====================================================================
        if not self._can_send_alert():
            result['skip_reasons'].append("Hourly alert limit reached")
            return result
        
        # =====================================================================
        # CRITERIA 1: Source must be Pump.fun
        # =====================================================================
        source = token_data.get('source', '')
        if source != 'pumpfun':
            result['skip_reasons'].append(f"Source is {source}, not pumpfun")
            return result
        result['trigger_reasons'].append("✓ Source: Pump.fun")
        
        # =====================================================================
        # CRITERIA 2: Token age ≤ max_age_seconds
        # =====================================================================
        age_seconds = token_data.get('age_seconds', 9999)
        if age_seconds > self.config.max_age_seconds:
            reason = "AGE_TOO_OLD"
            result['skip_reasons'].append(f"Too old: {age_seconds}s")
            if self.debug_enabled: self._buffer_debug(token_data, 0, reason, "SKIP")
            return result
        result['trigger_reasons'].append(f"✓ Age: {age_seconds}s")
        
        # =====================================================================
        # CRITERIA 3: SOL inflow ≥ min_sol_inflow
        # =====================================================================
        sol_inflow = token_data.get('sol_inflow', 0)
        if sol_inflow < self.config.min_sol_inflow:
            reason = "LOW_LIQUIDITY"
            result['skip_reasons'].append(f"Low inflow: {sol_inflow:.1f} SOL")
            if self.debug_enabled: self._buffer_debug(token_data, 10, reason, "SKIP")
            return result
        result['trigger_reasons'].append(f"✓ Inflow: {sol_inflow:.1f} SOL")
        
        # =====================================================================
        # CRITERIA 4: Buy velocity ≥ min_buy_velocity
        # =====================================================================
        buy_velocity = token_data.get('buy_velocity', 0)
        if buy_velocity < self.config.min_buy_velocity:
            reason = "LOW_BUY_VELOCITY"
            result['skip_reasons'].append(f"Low velocity: {buy_velocity:.1f}/min")
            if self.debug_enabled: self._buffer_debug(token_data, 20, reason, "SKIP")
            return result
        result['trigger_reasons'].append(f"✓ Velocity: {buy_velocity:.1f}/min")
        
        # =====================================================================
        # CRITERIA 5: Creator has NOT sold
        # =====================================================================
        creator_sold = token_data.get('creator_sold', False)
        if creator_sold:
            reason = "RISK_FLAG"
            result['skip_reasons'].append("Creator has sold")
            if self.debug_enabled: self._buffer_debug(token_data, 0, reason, "SKIP")
            return result
        result['trigger_reasons'].append("✓ Creator holding")
        
        # =====================================================================
        # CRITERIA 6: No Raydium migration yet (still early)
        # =====================================================================
        has_raydium = token_data.get('has_raydium_pool', False)
        if has_raydium:
            result['skip_reasons'].append("Already migrated to Raydium")
            return result
        result['trigger_reasons'].append("✓ Pre-migration")
        
        # =====================================================================
        # SCORE CHECK
        # =====================================================================
        score_result = self.score_engine.calculate_score(token_data)
        sniper_score = score_result.get('score', 0)
        
        # For sniper, we use a special scoring adjustment
        # Add bonus for meeting all sniper criteria
        sniper_score = min(sniper_score + 20, 100)
        
        if sniper_score < self.config.min_sniper_score:
            result['skip_reasons'].append(
                f"Score too low: {sniper_score} < {self.config.min_sniper_score}"
            )
            return result
        
        # =====================================================================
        # ALL CRITERIA PASSED
        # =====================================================================
        result['eligible'] = True
        result['sniper_score'] = sniper_score
        result['score_data'] = score_result
        
        self._stats['total_passed'] += 1
        
        if self.debug_enabled:
            self._buffer_debug(token_data, sniper_score, "QUALIFIED", "PASS")

        solana_log(f"🔫 SNIPER CANDIDATE: {shorten_address(token_address)} Score: {sniper_score}")
        
        # Check for flush
        if self.debug_enabled and self._should_log_now():
            self._flush_debug_logs()

        return result

    def _buffer_debug(self, token_data, score, skip_reason, status):
        """Buffer debug info for throttled logging."""
        self._candidate_buffer.append({
            'symbol': token_data.get('symbol', '???'),
            'score': score,
            'skip_reason': skip_reason,
            'status': status,
            'breakdown': token_data.get('breakdown', {}), # Might be from score engine
            'tx_signature': token_data.get('tx_signature'),
            'metadata_status': token_data.get('metadata_status', 'missing')
        })

    def _should_log_now(self):
        return (time.time() - self._last_log_time) >= self.log_interval_seconds

    def _flush_debug_logs(self):
        if not self._candidate_buffer:
            self._last_log_time = time.time()
            return
        
        # Sort by score
        sorted_cands = sorted(self._candidate_buffer, key=lambda x: x['score'], reverse=True)
        for cand in sorted_cands[:self.log_top_n]:
            sym = cand['symbol']
            score = cand['score']
            reason = cand['skip_reason']
            sig = cand.get('tx_signature')
            meta_status = cand.get('metadata_status', 'missing')
            if cand['status'] == 'PASS':
                if sig:
                    print(f"[SOLANA][DEBUG][SNIPER] {sym} | Sig={str(sig)[:8]}... | Score={score} | Metadata={meta_status} | QUALIFIED_FOR=SNIPER", flush=True)
                else:
                    print(f"[SOLANA][DEBUG][SNIPER] {sym} | Score={score} | Metadata={meta_status} | QUALIFIED_FOR=SNIPER", flush=True)
            else:
                if sig:
                    print(f"[SOLANA][DEBUG][SNIPER] {sym} | Sig={str(sig)[:8]}... | Score={score} | Metadata={meta_status} | SkipReason={reason}", flush=True)
                else:
                    print(f"[SOLANA][DEBUG][SNIPER] {sym} | Score={score} | Metadata={meta_status} | SkipReason={reason}", flush=True)
        
        self._candidate_buffer = []
        self._last_log_time = time.time()

    
    def mark_alerted(self, token_address: str):
        """Mark token as alerted to start cooldown."""
        now = time.time()
        self._alerted_tokens[token_address] = now
        self._alerts_this_hour.append(now)
        self._stats['total_alerted'] += 1
        
        # Cleanup old hourly records
        hour_ago = now - 3600
        self._alerts_this_hour = [t for t in self._alerts_this_hour if t > hour_ago]
        
        # Cleanup old cooldowns
        cooldown_cutoff = now - (self.config.cooldown_minutes * 60)
        self._alerted_tokens = {
            addr: ts for addr, ts in self._alerted_tokens.items()
            if ts > cooldown_cutoff
        }
    
    def _is_on_cooldown(self, token_address: str) -> bool:
        """Check if token is on cooldown."""
        if token_address not in self._alerted_tokens:
            return False
        
        last_alert = self._alerted_tokens[token_address]
        cooldown_seconds = self.config.cooldown_minutes * 60
        return time.time() - last_alert < cooldown_seconds
    
    def _can_send_alert(self) -> bool:
        """Check if we can send another alert this hour."""
        now = time.time()
        hour_ago = now - 3600
        
        # Count alerts in last hour
        recent_alerts = sum(1 for t in self._alerts_this_hour if t > hour_ago)
        return recent_alerts < self.config.max_alerts_per_hour
    
    def get_stats(self) -> Dict:
        """Get sniper statistics."""
        return {
            'enabled': self.config.enabled,
            'config': {
                'max_age_seconds': self.config.max_age_seconds,
                'min_sol_inflow': self.config.min_sol_inflow,
                'min_buy_velocity': self.config.min_buy_velocity,
                'min_sniper_score': self.config.min_sniper_score
            },
            'stats': self._stats.copy(),
            'tokens_on_cooldown': len(self._alerted_tokens),
            'alerts_this_hour': len(self._alerts_this_hour)
        }
