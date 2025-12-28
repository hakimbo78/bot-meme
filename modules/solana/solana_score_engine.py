import time
from typing import Dict, List, Optional

from .solana_utils import (
    SOL_INFLOW_LOW,
    SOL_INFLOW_MEDIUM,
    SOL_INFLOW_HIGH,
    BUY_VELOCITY_LOW,
    BUY_VELOCITY_MEDIUM,
    BUY_VELOCITY_HIGH,
    MIN_LIQUIDITY_TRADE,
    solana_log
)
from .metadata_less_scorer import MetadataLessScorer

# 3️⃣ Standardized Skip Reasons (ENUM)
SKIP_REASONS = [
    "LOW_LIQUIDITY",
    "LOW_BUY_VELOCITY",
    "NO_SMART_WALLET",
    "LOW_PRIORITY_FEE",
    "AGE_TOO_YOUNG",
    "AGE_TOO_OLD",
    "RISK_FLAG",
    "LOW_SCORE"
]

class SolanaScoreEngine:
    """
    Solana-specific token scoring engine.
    
    SINGLE SOURCE OF TRUTH for Solana scoring logic.
    Completely isolated from EVM TokenScorer.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize score engine.
        
        Args:
            config: Optional config overrides
        """
        self.config = config or {}
        
        # Debug Configuration
        debug_config = self.config.get('debug', {})
        self.debug_enabled = debug_config.get('enabled', False)
        self.log_top_n = debug_config.get('log_top_n', 3)
        self.log_interval_seconds = debug_config.get('log_interval_seconds', 30)
        
        # State for throttled logging
        self._last_log_time = time.time()
        self._candidate_buffer = []
        
        # Score bounds
        self._max_score = 100
        self._min_score = 0
        
        # Alert thresholds
        self._thresholds = {
            'INFO': self.config.get('alert_thresholds', {}).get('INFO', 30),
            'WATCH': self.config.get('alert_thresholds', {}).get('WATCH', 50),
            'TRADE': self.config.get('alert_thresholds', {}).get('TRADE', 70)
        }
    
    def calculate_score(self, token_data: Dict) -> Dict:
        """
        Calculate Solana score for a token with component breakdown.
        
        Args:
            token_data: Unified token data from SolanaScanner
            
        Returns:
            Dict with score, breakdown, alert_level, risk_flags, etc.
        """
        risk_flags = []
        skip_reason = None
        
        # =================================================================
        # CALCULATE RAW COMPONENTS
        # =================================================================
        
        # 1. Inflow (+20 max)
        sol_inflow = token_data.get('sol_inflow', 0)
        if sol_inflow >= SOL_INFLOW_HIGH: inflow_score = 20
        elif sol_inflow >= SOL_INFLOW_MEDIUM: inflow_score = 15
        elif sol_inflow >= SOL_INFLOW_LOW: inflow_score = 10
        else: inflow_score = 5 if sol_inflow > 0 else 0
        
        # 2. Velocity (+20 max)
        buy_velocity = token_data.get('buy_velocity', 0)
        if buy_velocity >= BUY_VELOCITY_HIGH: velocity_score = 20
        elif buy_velocity >= BUY_VELOCITY_MEDIUM: velocity_score = 15
        elif buy_velocity >= BUY_VELOCITY_LOW: velocity_score = 10
        else: velocity_score = 5 if buy_velocity > 0 else 0
        
        # 3. Raydium (+20 max)
        has_raydium = token_data.get('has_raydium_pool', False)
        liquidity_usd = token_data.get('liquidity_usd', 0)
        if has_raydium:
            if liquidity_usd >= MIN_LIQUIDITY_TRADE: raydium_score = 20
            elif liquidity_usd >= MIN_LIQUIDITY_TRADE / 2: raydium_score = 15
            else: raydium_score = 10
        else:
            raydium_score = 0
            risk_flags.append("No Raydium pool")

        # 4. Jupiter (+20 max)
        jupiter_listed = token_data.get('jupiter_listed', False)
        jupiter_volume = token_data.get('jupiter_volume_24h', 0)
        if jupiter_listed:
            if jupiter_volume >= 100000: jupiter_score = 20
            elif jupiter_volume >= 10000: jupiter_score = 15
            else: jupiter_score = 10
        else:
            jupiter_score = 0
            
        # 5. Trend (+10 max)
        liquidity_trend = token_data.get('liquidity_trend', 'unknown')
        if liquidity_trend == 'growing': trend_score = 10
        elif liquidity_trend == 'stable': trend_score = 5
        else:
            trend_score = 0
            if liquidity_trend == 'declining': risk_flags.append("Liquidity declining")
            
        # 6. Creator Penalty (-30)
        creator_sold = token_data.get('creator_sold', False)
        if creator_sold:
            creator_penalty = -30
            risk_flags.append("⚠️ CREATOR SOLD")
        else:
            creator_penalty = 0
            
        # 7. Concentration Penalty (-15 to 0)
        unique_buyers = token_data.get('unique_buyers', 0)
        if unique_buyers < 5:
            concentration_penalty = -15
            risk_flags.append("Low buyer diversity")
        elif unique_buyers < 10:
            concentration_penalty = -5
        else:
            concentration_penalty = 0

        # =================================================================
        # MAP TO REQUESTED COMPONENTS
        # =================================================================
        # score_components structure:
        # {
        #     "liquidity": int,
        #     "buy_velocity": int,
        #     "wallet_quality": int,
        #     "priority_fee": int, # Placeholder for now
        #     "age_bonus": int,    # Placeholder for now
        #     "risk_penalty": int
        # }
        
        score_components = {
            "liquidity": inflow_score + raydium_score + trend_score,
            "buy_velocity": velocity_score,
            "wallet_quality": jupiter_score + concentration_penalty,
            "priority_fee": 0,
            "age_bonus": 0,
            # Small bonus only when metadata exists (optional in sniper mode)
            "metadata_bonus": 10 if token_data.get('metadata_status') == 'present' else 0,
            "risk_penalty": creator_penalty
        }
        
        # Calculate Total
        total_score = sum(score_components.values())
        final_score = max(self._min_score, min(total_score, self._max_score))
        
        # =================================================================
        # VERDICT & SKIP REASON
        # =================================================================
        alert_level = self._classify_alert(final_score)
        
        if final_score >= self._thresholds['TRADE']:
            verdict = "TRADE"
        elif final_score >= self._thresholds['WATCH']:
            verdict = "WATCH"
        elif final_score >= self._thresholds['INFO']:
            verdict = "INFO"
        else:
            verdict = "SKIP"
            
        # Determine Skip Reason if Skipped
        if verdict == "SKIP":
            if creator_penalty < 0:
                skip_reason = "RISK_FLAG"
            elif score_components["liquidity"] < 10:
                skip_reason = "LOW_LIQUIDITY"
            elif score_components["buy_velocity"] < 5:
                skip_reason = "LOW_BUY_VELOCITY"
            else:
                skip_reason = "LOW_SCORE"

        # =================================================================
        # DEBUG LOGGING (Buffered)
        # =================================================================
        if self.debug_enabled:
            # Buffer result for throttled logging
            self._buffer_candidate(
                token_data=token_data,
                score=final_score,
                breakdown=score_components,
                skip_reason=skip_reason,
                verdict=verdict
            )
            
            # Check if we should flush logs
            if self._should_log_now():
                self._flush_debug_logs()

        return {
            'score': final_score,
            'solana_score': final_score,
            'breakdown': score_components,  # Returns the new breakdown format
            'alert_level': alert_level,
            'verdict': verdict,
            'risk_flags': risk_flags,
            'thresholds': self._thresholds,
            'skip_reason': skip_reason
        }
    
    def _classify_alert(self, score: int) -> str:
        """Classify alert level based on score."""
        if score >= self._thresholds['TRADE']:
            return 'TRADE'
        elif score >= self._thresholds['WATCH']:
            return 'WATCH'
        elif score >= self._thresholds['INFO']:
            return 'INFO'
        return 'NONE'

    # =================================================================
    # DEBUG LOGGING IMPL
    # =================================================================
    def _buffer_candidate(self, token_data, score, breakdown, skip_reason, verdict):
        """Add candidate to buffer."""
        self._candidate_buffer.append({
            'symbol': token_data.get('symbol', '???'),
            'score': score,
            'breakdown': breakdown,
            'skip_reason': skip_reason,
            'verdict': verdict,
            'tx_signature': token_data.get('tx_signature'),
            'metadata_status': token_data.get('metadata_status', 'missing')
        })
        
    def _should_log_now(self) -> bool:
        """Check if time interval has passed."""
        return (time.time() - self._last_log_time) >= self.log_interval_seconds
        
    def _flush_debug_logs(self):
        """Log top N candidates and clear buffer."""
        if not self._candidate_buffer:
            # Heartbeat - Show that engine is alive even if no tokens scored
            print(f"[SOLANA][DEBUG] Engine Heartbeat | Candidates=0 | Time={time.strftime('%H:%M:%S')}", flush=True)
            self._last_log_time = time.time()
            return
            
        # Sort by score descending
        sorted_candidates = sorted(self._candidate_buffer, key=lambda x: x['score'], reverse=True)
        top_candidates = sorted_candidates[:self.log_top_n]
        
        for cand in top_candidates:
            self._log_debug(cand)
            
        # Reset
        self._candidate_buffer = []
        self._last_log_time = time.time()
        
    def _log_debug(self, candidate):
        """
        Log in exact requested format:
        [SOLANA][DEBUG] SYMBOL | Score=XX | Breakdown={...} SkipReason=...
        """
        symbol = candidate['symbol']
        score = candidate['score']
        sig = candidate.get('tx_signature')
        meta_status = candidate.get('metadata_status', 'missing')
        
        if candidate['verdict'] == 'SKIP':
            # Skip Format
            breakdown_str = " ".join([f"{k}:{v}" for k, v in candidate['breakdown'].items()])
            # Simplify breakdown for log readability as per example: Breakdown={liq:20, buy:12...}
            # The user requested: Breakdown={liq:20, buy:12, wallet:8, priority:5, age:4, risk:-10}
            bd = candidate['breakdown']
            fmt_bd = (f"{{liq:{bd['liquidity']}, buy:{bd['buy_velocity']}, "
                      f"wallet:{bd['wallet_quality']}, priority:{bd['priority_fee']}, "
                      f"age:{bd['age_bonus']}, meta:{bd.get('metadata_bonus', 0)}, risk:{bd['risk_penalty']}}}")
            
            skip = candidate['skip_reason']
            if sig:
                print(f"[SOLANA][DEBUG] {symbol} | Sig={str(sig)[:8]}... | Score={score} | Metadata={meta_status} | Breakdown={fmt_bd} SkipReason={skip}", flush=True)
            else:
                print(f"[SOLANA][DEBUG] {symbol} | Score={score} | Metadata={meta_status} | Breakdown={fmt_bd} SkipReason={skip}", flush=True)
            
        else:
            # Pass Format
            # [SOLANA][DEBUG] SYMBOL | Score=72 | QUALIFIED_FOR=WATCH
            verdict = candidate['verdict']
            if sig:
                print(f"[SOLANA][DEBUG] {symbol} | Sig={str(sig)[:8]}... | Score={score} | Metadata={meta_status} | QUALIFIED_FOR={verdict}", flush=True)
            else:
                print(f"[SOLANA][DEBUG] {symbol} | Score={score} | Metadata={meta_status} | QUALIFIED_FOR={verdict}", flush=True)

    def get_score_description(self, score: int) -> str:
        """Get human-readable score description."""
        if score >= 85: return "🟢 EXCELLENT - Strong Solana opportunity"
        elif score >= 70: return "🟡 GOOD - Valid trade candidate"
        elif score >= 50: return "🟠 MODERATE - Monitor closely"
        elif score >= 30: return "🔴 WEAK - High risk"
        else: return "⚫ SKIP - Does not meet criteria"
    
    def get_thresholds(self) -> Dict:
        """Get current alert thresholds."""
        return self._thresholds.copy()
