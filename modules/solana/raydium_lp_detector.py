"""
Raydium Liquidity Pool Detector

Real-time detection of Raydium LP creation for tokens.

Monitors:
- InitializePool
- Initialize2
- Pool creation on Raydium AMM

Tracks:
- Pool address
- Base mint
- Quote mint (SOL / USDC)
- Initial liquidity amounts
- LP mint

Used for determining when tokens are safe to trade (LP validation).
"""
import time
import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .solana_utils import (
    RAYDIUM_AMM_PROGRAM_ID,
    WRAPPED_SOL_MINT,
    solana_log,
    rate_limit_rpc,
    is_valid_solana_address
)

# =============================================================================
# RAYDIUM LP DETECTION CONSTANTS
# =============================================================================

# Raydium pool initialization instructions
RAYDIUM_INIT_POOL = "initialize"
RAYDIUM_INIT_POOL2 = "initialize2"

# Pool events to monitor
RAYDIUM_POOL_EVENTS = [RAYDIUM_INIT_POOL, RAYDIUM_INIT_POOL2]


@dataclass
class RaydiumLPInfo:
    """Detected Raydium liquidity pool."""
    pool_address: str
    base_mint: str  # The token mint
    quote_mint: str  # SOL or USDC
    lp_mint: str
    base_liquidity: float  # Amount in native units
    quote_liquidity: float  # SOL amount
    quote_liquidity_usd: float  # SOL converted to USD
    detected_timestamp: float = field(default_factory=time.time)
    txid: str = ""
    status: str = "VALID"  # VALID, LOW_LIQUIDITY, ERROR
    
    def to_dict(self) -> Dict:
        """Convert to dict output."""
        return {
            "pool_address": self.pool_address,
            "base_mint": self.base_mint,
            "quote_mint": self.quote_mint,
            "lp_mint": self.lp_mint,
            "base_liquidity": self.base_liquidity,
            "quote_liquidity": self.quote_liquidity,
            "quote_liquidity_usd": self.quote_liquidity_usd,
            "detected_timestamp": self.detected_timestamp,
            "txid": self.txid,
            "status": self.status
        }
    
    @property
    def age_seconds(self) -> float:
        """Age of LP detection in seconds."""
        return time.time() - self.detected_timestamp


class RaydiumLPDetector:
    """
    Detects Raydium Liquidity Pool creation in real-time.
    
    Monitors:
    - New LP initialization events
    - Extracts pool and liquidity information
    - Validates liquidity thresholds
    
    Caches detected pools with TTL.
    """
    
    def __init__(
        self,
        client=None,
        min_liquidity_sol: float = 10.0,
        cache_ttl: int = 3600
    ):
        """
        Initialize Raydium LP detector.
        
        Args:
            client: Solana RPC client
            min_liquidity_sol: Minimum SOL liquidity threshold
            cache_ttl: Cache TTL in seconds (default 1 hour)
        """
        self.client = client
        self.min_liquidity_sol = min_liquidity_sol
        self.cache_ttl = cache_ttl
        self._detected_pools: Dict[str, RaydiumLPInfo] = {}
        self._detected_tokens: Set[str] = set()  # Tokens with detected LPs
        self._processed_txids: Set[str] = set()  # Avoid reprocessing
        self._last_slot_checked: int = 0
    
    def set_client(self, client):
        """Update Solana RPC client."""
        self.client = client
    
    async def detect_from_transaction(
        self,
        txid: str,
        token_mint: Optional[str] = None
    ) -> Optional[RaydiumLPInfo]:
        """
        Detect LP from a specific transaction.
        
        Args:
            txid: Transaction signature
            token_mint: Optional filter for specific token
            
        Returns:
            RaydiumLPInfo if LP detected, None otherwise
        """
        if not self.client or txid in self._processed_txids:
            return None
        
        try:
            rate_limit_rpc()
            tx = self.client.get_transaction(txid)
            
            if not tx.value:
                return None
            
            # Parse transaction for LP initialization
            lp_info = self._parse_transaction_for_lp(tx.value, txid, token_mint)
            
            if lp_info:
                self._processed_txids.add(txid)
                self._detected_pools[lp_info.pool_address] = lp_info
                self._detected_tokens.add(lp_info.base_mint)
                
                solana_log(
                    f"[SOLANA][LP] Raydium LP detected for token {lp_info.base_mint[:8]}... "
                    f"| SOL={lp_info.quote_liquidity:.2f} | LP={lp_info.status}",
                    "INFO"
                )
                
                return lp_info
            
            return None
        
        except Exception as e:
            solana_log(f"[LP] Transaction parse error: {e}", "DEBUG")
            return None
    
    async def detect_for_token(
        self,
        token_mint: str,
        max_age_minutes: int = 5
    ) -> Optional[RaydiumLPInfo]:
        """
        Detect LP for a specific token from recent transactions.
        
        Searches recent signatures for the token mint in LP creation.
        
        Args:
            token_mint: Token to search for
            max_age_minutes: How far back to search
            
        Returns:
            RaydiumLPInfo if found, None otherwise
        """
        if not is_valid_solana_address(token_mint):
            return None
        
        # Check cache first
        for pool_info in self._detected_pools.values():
            if pool_info.base_mint == token_mint:
                if pool_info.age_seconds < max_age_minutes * 60:
                    return pool_info
        
        # Not found in cache, would need to scan recent blocks
        # This is a more intensive operation, so we focus on callback-based detection
        return None
    
    def _parse_transaction_for_lp(
        self,
        tx,
        txid: str,
        token_filter: Optional[str] = None
    ) -> Optional[RaydiumLPInfo]:
        """
        Parse transaction to detect Raydium LP creation.
        
        Looks for:
        - Program ID = RAYDIUM_AMM_PROGRAM_ID
        - Instruction = initialize or initialize2
        - Accounts = pool, base_mint, quote_mint, lp_mint
        
        Args:
            tx: Parsed transaction object
            txid: Transaction ID
            token_filter: Optional token mint to filter
            
        Returns:
            RaydiumLPInfo or None
        """
        try:
            if not hasattr(tx, 'transaction') or not tx.transaction:
                return None
            
            transaction = tx.transaction
            if not hasattr(transaction, 'message'):
                return None
            
            message = transaction.message
            if not hasattr(message, 'instructions'):
                return None
            
            # Scan instructions for Raydium LP initialization
            for instr in message.instructions:
                lp_info = self._parse_instruction_for_lp(instr, txid, token_filter)
                if lp_info:
                    return lp_info
            
            return None
        
        except Exception as e:
            solana_log(f"[LP] Parse error: {e}", "DEBUG")
            return None
    
    def _parse_instruction_for_lp(
        self,
        instr,
        txid: str,
        token_filter: Optional[str] = None
    ) -> Optional[RaydiumLPInfo]:
        """
        Parse single instruction for LP creation.
        
        Args:
            instr: Instruction object
            txid: Transaction ID
            token_filter: Optional token filter
            
        Returns:
            RaydiumLPInfo or None
        """
        try:
            # Check if this is a Raydium instruction
            if not hasattr(instr, 'program_id'):
                return None
            
            program_id = str(instr.program_id)
            if program_id != RAYDIUM_AMM_PROGRAM_ID:
                return None
            
            # Check instruction type (initialize or initialize2)
            if not hasattr(instr, 'data') or not instr.data:
                return None
            
            # Instruction discriminator (first 8 bytes)
            # This is program-specific, for Raydium AMM:
            # initialize = 0, initialize2 = 1
            instr_type = instr.data[0] if len(instr.data) > 0 else None
            
            if instr_type not in [0, 1]:  # initialize or initialize2
                return None
            
            # Get accounts
            if not hasattr(instr, 'accounts') or not instr.accounts:
                return None
            
            accounts = instr.accounts
            
            # Raydium AMM V4 pool initialization accounts:
            # [0] = ammId (pool)
            # [1] = ammAuthority
            # [2] = ammOpenOrders
            # [3] = lpMint
            # [4] = coinMint (base token)
            # [5] = pcMint (quote token - SOL/USDC)
            # [6+] = various vault and fee accounts
            
            if len(accounts) < 6:
                return None
            
            try:
                pool_address = str(accounts[0])
                lp_mint = str(accounts[3])
                base_mint = str(accounts[4])
                quote_mint = str(accounts[5])
                
                # Apply token filter if provided
                if token_filter and base_mint != token_filter:
                    return None
                
                # Validate mints
                if not all(is_valid_solana_address(m) for m in [base_mint, quote_mint]):
                    return None
                
                # Only care about SOL or USDC pairs for now
                if quote_mint != WRAPPED_SOL_MINT:
                    # Could be USDC, but we focus on SOL for simplicity
                    return None
                
                # Extract liquidity amounts from instruction data
                # This requires parsing the instruction data, which is complex
                # For now, we mark as detected but need to verify via account state
                
                lp_info = RaydiumLPInfo(
                    pool_address=pool_address,
                    base_mint=base_mint,
                    quote_mint=quote_mint,
                    lp_mint=lp_mint,
                    base_liquidity=0.0,  # Would need to fetch from state
                    quote_liquidity=0.0,  # Would need to fetch from state
                    quote_liquidity_usd=0.0,
                    txid=txid,
                    status="DETECTED"  # Status pending liquidity verification
                )
                
                return lp_info
            
            except (IndexError, ValueError):
                return None
        
        except Exception as e:
            solana_log(f"[LP] Instruction parse error: {e}", "DEBUG")
            return None
    
    async def verify_liquidity(self, pool_address: str) -> Optional[RaydiumLPInfo]:
        """
        Verify pool liquidity by fetching pool state.
        
        Args:
            pool_address: Raydium pool address
            
        Returns:
            Updated RaydiumLPInfo with verified liquidity, or None
        """
        if not pool_address in self._detected_pools:
            return None
        
        lp_info = self._detected_pools[pool_address]
        
        try:
            # TODO: Fetch pool state and extract liquidity amounts
            # This requires decoding Raydium pool account structure
            # For now, mark as requiring verification
            
            if lp_info.quote_liquidity >= self.min_liquidity_sol:
                lp_info.status = "VALID"
                return lp_info
            else:
                lp_info.status = "LOW_LIQUIDITY"
                solana_log(
                    f"[SOLANA][LP][SKIP] LP detected but liquidity too low "
                    f"({lp_info.quote_liquidity:.2f} SOL)",
                    "WARN"
                )
                return None
        
        except Exception as e:
            solana_log(f"[LP] Liquidity verification error: {e}", "ERROR")
            lp_info.status = "ERROR"
            return None
    
    def has_lp(self, token_mint: str) -> bool:
        """
        Check if token has a detected Raydium LP.
        
        Args:
            token_mint: Token to check
            
        Returns:
            True if LP detected and valid
        """
        if token_mint not in self._detected_tokens:
            return False
        
        # Check if any pool for this token is valid
        for pool_info in self._detected_pools.values():
            if pool_info.base_mint == token_mint and pool_info.status == "VALID":
                return True
        
        return False
    
    def get_lp(self, token_mint: str) -> Optional[RaydiumLPInfo]:
        """Get detected LP for a token."""
        for pool_info in self._detected_pools.values():
            if pool_info.base_mint == token_mint and pool_info.status == "VALID":
                return pool_info
        return None
    
    def clear_cache(self):
        """Clear all cached LPs."""
        self._detected_pools.clear()
        self._detected_tokens.clear()
        self._processed_txids.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get detector statistics."""
        return {
            "detected_pools": len(self._detected_pools),
            "tokens_with_lp": len(self._detected_tokens),
            "processed_txids": len(self._processed_txids),
            "min_liquidity_sol": self.min_liquidity_sol
        }
