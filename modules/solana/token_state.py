"""
Token State Machine & Upgrade Engine

Manages token lifecycle through multiple detection and validation phases:

States:
- DETECTED: Pump.fun token detected
- METADATA_OK: Token metadata resolved
- LP_DETECTED: Raydium LP found
- SNIPER_ARMED: Ready for sniper execution
- BOUGHT: Executed
- SKIPPED: Failed validation

Rules:
- No buy without metadata + LP
- LP must exceed min_liquidity_sol
- Score must meet sniper_threshold
"""
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import time

from .solana_utils import solana_log


class TokenState(Enum):
    """Token lifecycle states."""
    DETECTED = "DETECTED"  # Pump.fun detected
    METADATA_PENDING = "METADATA_PENDING"  # Awaiting metadata or LP
    METADATA_OK = "METADATA_OK"  # Metadata resolved
    LP_DETECTED = "LP_DETECTED"  # Raydium LP found
    WATCH = "WATCH"  # Monitoring for opportunity
    SNIPER_ARMED = "SNIPER_ARMED"  # Ready to buy
    BOUGHT = "BOUGHT"  # Trade executed
    SKIPPED = "SKIPPED"  # Failed validation


@dataclass
class TokenStateRecord:
    """State transition record for a token."""
    mint: str
    symbol: str = "???"
    current_state: TokenState = TokenState.DETECTED
    state_history: list = field(default_factory=list)
    metadata_resolved: bool = False
    lp_detected: bool = False
    lp_valid: bool = False
    score: float = 0.0
    last_score: float = 0.0
    last_transition: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    lp_info: Dict[str, Any] = field(default_factory=dict)
    reason_skipped: str = ""
    buy_velocity: float = 0.0  # Buys per minute
    smart_wallet_detected: bool = False  # Smart money wallet activity
    
    def to_dict(self) -> Dict:
        """Convert to dict."""
        return {
            "mint": self.mint,
            "symbol": self.symbol,
            "state": self.current_state.value,
            "metadata_resolved": self.metadata_resolved,
            "lp_detected": self.lp_detected,
            "lp_valid": self.lp_valid,
            "score": self.score,
            "last_score": self.last_score,
            "age_seconds": time.time() - self.created_at,
            "reason_skipped": self.reason_skipped,
            "buy_velocity": self.buy_velocity,
            "smart_wallet_detected": self.smart_wallet_detected
        }
    
    @property
    def age_seconds(self) -> float:
        """Token age in seconds."""
        return time.time() - self.created_at


class TokenStateMachine:
    """
    Manages token state transitions.
    
    Tracks:
    - Current state for each token
    - Metadata resolution status
    - LP detection status
    - Score progression
    
    Enforces rules:
    - Metadata must resolve before LP
    - LP must be valid before arming
    - Score must meet threshold
    """
    
    def __init__(
        self,
        min_lp_sol: float = 10.0,
        sniper_score_threshold: float = 70.0,
        safe_mode: bool = True
    ):
        """
        Initialize state machine.
        
        Args:
            min_lp_sol: Minimum SOL liquidity required
            sniper_score_threshold: Minimum score to arm sniper
            safe_mode: Enforce strict validation rules
        """
        self.min_lp_sol = min_lp_sol
        self.sniper_score_threshold = sniper_score_threshold
        self.safe_mode = safe_mode
        self._states: Dict[str, TokenStateRecord] = {}
    
    def create_token(self, mint: str, symbol: str = "???") -> TokenStateRecord:
        """
        Create new token record.
        
        Args:
            mint: Token mint address
            symbol: Token symbol (optional)
            
        Returns:
            TokenStateRecord
        """
        if mint in self._states:
            return self._states[mint]
        
        record = TokenStateRecord(mint=mint, symbol=symbol)
        self._states[mint] = record
        
        solana_log(f"[STATE] Token created: {symbol} ({mint[:8]}...)", "DEBUG")
        
        return record
    
    def set_metadata(
        self,
        mint: str,
        name: str,
        symbol: str,
        decimals: int,
        supply: int
    ) -> Optional[TokenStateRecord]:
        """
        Update token with metadata resolution.
        
        Triggers: DETECTED → METADATA_OK
        
        Args:
            mint: Token mint
            name: Token name
            symbol: Token symbol
            decimals: Token decimals
            supply: Token supply
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if not record:
            record = self.create_token(mint, symbol)
        
        record.metadata_resolved = True
        record.symbol = symbol
        record.metadata = {
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "supply": supply
        }
        
        # Transition to METADATA_OK
        self._transition(record, TokenState.METADATA_OK)
        
        return record
    
    def set_lp_detected(
        self,
        mint: str,
        pool_address: str,
        base_liquidity: float,
        quote_liquidity: float,
        quote_liquidity_usd: float,
        lp_mint: str = ""
    ) -> Optional[TokenStateRecord]:
        """
        Update token with LP detection.
        
        Triggers: METADATA_OK → LP_DETECTED
        
        Args:
            mint: Token mint
            pool_address: Raydium pool address
            base_liquidity: Base token liquidity
            quote_liquidity: Quote token liquidity (SOL)
            quote_liquidity_usd: Quote liquidity in USD
            lp_mint: LP token mint
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if not record:
            record = self.create_token(mint)
        
        # Safety check: metadata must be resolved first
        if self.safe_mode and not record.metadata_resolved:
            solana_log(
                f"[STATE][WARN] LP detected before metadata for {record.symbol}",
                "WARN"
            )
            return None
        
        # Check liquidity threshold
        if quote_liquidity < self.min_lp_sol:
            record.lp_detected = True
            record.lp_valid = False
            record.lp_info = {
                "pool": pool_address,
                "quote_liquidity_sol": quote_liquidity,
                "quote_liquidity_usd": quote_liquidity_usd,
                "status": "LOW_LIQUIDITY"
            }
            
            solana_log(
                f"[SOLANA][LP][SKIP] LP detected but liquidity too low "
                f"({quote_liquidity:.2f} SOL < {self.min_lp_sol:.2f} min)",
                "WARN"
            )
            
            return record
        
        # LP is valid
        record.lp_detected = True
        record.lp_valid = True
        record.lp_info = {
            "pool": pool_address,
            "base_liquidity": base_liquidity,
            "quote_liquidity_sol": quote_liquidity,
            "quote_liquidity_usd": quote_liquidity_usd,
            "lp_mint": lp_mint,
            "status": "VALID"
        }
        
        # Transition to LP_DETECTED
        self._transition(record, TokenState.LP_DETECTED)
        
        solana_log(
            f"[SOLANA][LP] Raydium LP detected | {record.symbol} | "
            f"SOL={quote_liquidity:.2f} | LP=OK",
            "INFO"
        )
        
        return record
    
    def update_score(self, mint: str, score: float) -> Optional[TokenStateRecord]:
        """
        Update token score.
        
        Args:
            mint: Token mint
            score: New score value
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if not record:
            return None
        
        record.last_score = record.score
        record.score = score
        
        # Check if ready to arm sniper
        if (record.lp_valid and
            record.metadata_resolved and
            record.score >= self.sniper_score_threshold):
            
            # Transition to SNIPER_ARMED
            self._transition(record, TokenState.SNIPER_ARMED)
            
            solana_log(
                f"[SOLANA][STATE] {record.symbol} upgraded → SNIPER_ARMED "
                f"| score={score:.1f}",
                "INFO"
            )
        
        return record
    
    def can_execute(self, mint: str) -> tuple:
        """
        Check if token is ready for execution.
        
        Args:
            mint: Token mint
            
        Returns:
            (can_execute, reason) tuple
        """
        record = self._states.get(mint)
        if not record:
            return False, "Token not found"
        
        if record.current_state == TokenState.SKIPPED:
            return False, f"Token skipped: {record.reason_skipped}"
        
        if not record.metadata_resolved:
            return False, "Metadata not resolved"
        
        if not record.lp_detected:
            return False, "LP not detected"
        
        if not record.lp_valid:
            return False, f"LP invalid: {record.lp_info.get('status', 'unknown')}"
        
        if record.score < self.sniper_score_threshold:
            return False, f"Score too low: {record.score:.1f} < {self.sniper_score_threshold:.1f}"
        
        if record.current_state != TokenState.SNIPER_ARMED:
            return False, f"Not armed: {record.current_state.value}"
        
        return True, "Ready to execute"
    
    def mark_bought(self, mint: str, amount_sol: float = 0.0) -> Optional[TokenStateRecord]:
        """
        Mark token as bought.
        
        Args:
            mint: Token mint
            amount_sol: Amount bought in SOL
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if not record:
            return None
        
        self._transition(record, TokenState.BOUGHT)
        
        solana_log(
            f"[SOLANA][SNIPER] BUY EXECUTED | {record.symbol} | amount={amount_sol:.2f} SOL",
            "INFO"
        )
        
        return record
    
    def mark_skipped(self, mint: str, reason: str) -> Optional[TokenStateRecord]:
        """
        Mark token as skipped.
        
        Args:
            mint: Token mint
            reason: Reason for skipping
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if not record:
            return None
        
        record.reason_skipped = reason
        self._transition(record, TokenState.SKIPPED)
        
        solana_log(
            f"[STATE] {record.symbol} skipped: {reason}",
            "DEBUG"
        )
        
        return record
    
    def _transition(self, record: TokenStateRecord, new_state: TokenState):
        """
        Record state transition.
        
        Args:
            record: Token record
            new_state: New state to transition to
        """
        old_state = record.current_state
        record.current_state = new_state
        record.last_transition = time.time()
        record.state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": time.time()
        })
    
    def get_token(self, mint: str) -> Optional[TokenStateRecord]:
        """Get token record."""
        return self._states.get(mint)

    def has_token(self, mint: str) -> bool:
        """Check whether a mint is tracked."""
        return mint in self._states
    
    def get_armed_tokens(self) -> list:
        """Get all tokens ready for execution."""
        return [
            record for record in self._states.values()
            if record.current_state == TokenState.SNIPER_ARMED
        ]
    
    def get_by_state(self, state: TokenState) -> list:
        """Get all tokens in a specific state."""
        return [
            record for record in self._states.values()
            if record.current_state == state
        ]
    
    def update_buy_velocity(self, mint: str, velocity: float) -> Optional[TokenStateRecord]:
        """
        Update token buy velocity.
        
        Args:
            mint: Token mint
            velocity: Buy velocity (buys per minute)
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if record:
            record.buy_velocity = velocity
        return record
    
    def set_smart_wallet_detected(self, mint: str, detected: bool = True) -> Optional[TokenStateRecord]:
        """
        Mark smart wallet detection for token.
        
        Args:
            mint: Token mint
            detected: Whether smart wallet was detected
            
        Returns:
            Updated TokenStateRecord
        """
        record = self._states.get(mint)
        if record:
            record.smart_wallet_detected = detected
        return record
    
    def cleanup(self, max_age_hours: int = 24):
        """
        Clean up old token records.
        
        Args:
            max_age_hours: Remove records older than this
        """
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = [
            mint for mint, record in self._states.items()
            if record.created_at < cutoff
        ]
        
        for mint in to_remove:
            del self._states[mint]
    
    def get_stats(self) -> Dict:
        """Get state machine statistics."""
        by_state = {}
        for state in TokenState:
            by_state[state.value] = len(self.get_by_state(state))
        
        return {
            "total_tokens": len(self._states),
            "by_state": by_state,
            "armed_tokens": len(self.get_armed_tokens()),
            "min_lp_sol": self.min_lp_sol,
            "sniper_score_threshold": self.sniper_score_threshold
        }
