import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from .solana_utils import (
    solana_log,
    shorten_address,
    RUNNING_MIN_AGE,
    RUNNING_MAX_AGE,
    MIN_LIQUIDITY_RUNNING
)
from .solana_score_engine import SolanaScoreEngine


@dataclass
class RunningConfig:
    """Configuration for running token detection."""
    enabled: bool = True
    min_age_minutes: int = 30
    max_age_days: int = 14
    min_liquidity_usd: float = 50000
    volume_spike_multiplier: float = 2.0
    min_running_score: int = 60
    cooldown_minutes: int = 60


class SolanaRunningDetector:
    """
    Detects tokens with running/momentum signals.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize running detector.
        """
        chain_config = config or {}
        running_config = chain_config.get('running', {})
        
        self.config = RunningConfig(
            enabled=running_config.get('enabled', True),
            min_age_minutes=running_config.get('min_age_minutes', 30),
            max_age_days=running_config.get('max_age_days', 14),
            min_liquidity_usd=running_config.get('min_liquidity_usd', 50000),
            volume_spike_multiplier=running_config.get('volume_spike_multiplier', 2.0),
            min_running_score=running_config.get('min_running_score', 60),
            cooldown_minutes=running_config.get('cooldown_minutes', 60)
        )
        
        # Debug Configuration
        debug_config = chain_config.get('debug', {})
        self.debug_enabled = debug_config.get('enabled', False)
        self.log_top_n = debug_config.get('log_top_n', 3)
        self.log_interval_seconds = debug_config.get('log_interval_seconds', 30)
        
        # State
        self._last_log_time = time.time()
        self._candidate_buffer = []
        
        self.score_engine = SolanaScoreEngine(chain_config)
        self._alerted_tokens: Dict[str, float] = {}
        
        # Stats
        self._stats = {
            'total_checked': 0,
            'total_eligible': 0,
            'total_alerted': 0
        }
    
    def is_enabled(self) -> bool:
        return self.config.enabled
    
    def check_running_eligibility(self, token_data: Dict, jupiter_scanner=None) -> Dict:
        """
        Check if token shows running signals with debug logging.
        """
        self._stats['total_checked'] += 1
        
        result = {
            'eligible': False,
            'phase': None,
            'signals': [],
            'skip_reasons': [],
            'running_score': 0
        }
        
        if not self.config.enabled:
            return result
        
        token_address = token_data.get('token_address', token_data.get('address', ''))
        
        # 1. Cooldown
        if self._is_on_cooldown(token_address):
            return result
            
        # 2. Age
        age_seconds = token_data.get('age_seconds', 0)
        min_age_s = self.config.min_age_minutes * 60
        max_age_s = self.config.max_age_days * 86400
        
        if age_seconds < min_age_s:
            if self.debug_enabled: self._buffer_debug(token_data, 10, "AGE_TOO_YOUNG", "SKIP")
            return result
        if age_seconds > max_age_s:
            if self.debug_enabled: self._buffer_debug(token_data, 10, "AGE_TOO_OLD", "SKIP")
            return result
            
        # 3. Liquidity
        liquidity_usd = token_data.get('liquidity_usd', 0)
        if liquidity_usd < self.config.min_liquidity_usd:
            if self.debug_enabled: self._buffer_debug(token_data, 20, "LOW_LIQUIDITY", "SKIP")
            return result
            
        # 4. Score
        score_result = self.score_engine.calculate_score(token_data)
        running_score = score_result.get('score', 0)
        
        if running_score < self.config.min_running_score:
            if self.debug_enabled: self._buffer_debug(token_data, running_score, "LOW_SCORE", "SKIP")
            return result
            
        # Eligible
        result['eligible'] = True
        result['running_score'] = running_score
        result['score_data'] = score_result
        
        if self.debug_enabled:
            self._buffer_debug(token_data, running_score, "QUALIFIED", "PASS")
            
        # Flush check
        if self.debug_enabled and self._should_log_now():
            self._flush_debug_logs()
            
        return result

    def _buffer_debug(self, token_data, score, skip_reason, status):
        self._candidate_buffer.append({
            'symbol': token_data.get('symbol', '???'),
            'score': score,
            'skip_reason': skip_reason,
            'status': status
        })

    def _should_log_now(self):
        return (time.time() - self._last_log_time) >= self.log_interval_seconds

    def _flush_debug_logs(self):
        if not self._candidate_buffer:
            self._last_log_time = time.time()
            return
        sorted_cands = sorted(self._candidate_buffer, key=lambda x: x['score'], reverse=True)
        for cand in sorted_cands[:self.log_top_n]:
            sym = cand['symbol']
            score = cand['score']
            reason = cand['skip_reason']
            if cand['status'] == 'PASS':
                print(f"[SOLANA][DEBUG][RUNNING] {sym} | Score={score} | QUALIFIED_FOR=RUNNING", flush=True)
            else:
                print(f"[SOLANA][DEBUG][RUNNING] {sym} | Score={score} | SkipReason={reason}", flush=True)
        self._candidate_buffer = []
        self._last_log_time = time.time()

    def mark_alerted(self, token_address: str):
        self._alerted_tokens[token_address] = time.time()
        self._stats['total_alerted'] += 1
    
    def _is_on_cooldown(self, token_address: str) -> bool:
        if token_address not in self._alerted_tokens: return False
        return time.time() - self._alerted_tokens[token_address] < self.config.cooldown_minutes * 60

    def get_stats(self) -> Dict:
        return {'enabled': self.config.enabled, 'stats': self._stats.copy()}

