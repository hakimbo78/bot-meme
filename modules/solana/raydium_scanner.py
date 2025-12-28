"""
Raydium Scanner - Liquidity Confirmation Module

Monitors Raydium AMM for:
- New pool creation events
- Liquidity additions
- Liquidity trend tracking
- Pool depth analysis

Output: Liquidity confirmation data for scoring

CRITICAL: READ-ONLY - No execution, no wallets
"""
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .solana_utils import (
    RAYDIUM_AMM_PROGRAM_ID,
    WRAPPED_SOL_MINT,
    parse_lamports_to_sol,
    is_valid_solana_address,
    solana_log,
    rate_limit_rpc,
    sol_to_usd
)
from config import SOLANA_ALCHEMY_SAFE_CONFIG
import asyncio


@dataclass
class RaydiumPool:
    """Represents a Raydium liquidity pool."""
    pool_address: str
    token_mint: str
    quote_mint: str  # Usually SOL or USDC
    creation_timestamp: float
    initial_liquidity_sol: float = 0.0
    current_liquidity_sol: float = 0.0
    liquidity_history: List[tuple] = field(default_factory=list)  # (timestamp, amount)
    last_updated: float = field(default_factory=time.time)
    
    @property
    def liquidity_usd(self) -> float:
        return sol_to_usd(self.current_liquidity_sol)
    
    @property
    def liquidity_trend(self) -> str:
        """Determine liquidity trend: growing, stable, declining."""
        if len(self.liquidity_history) < 2:
            return "stable"
        
        recent = self.liquidity_history[-3:]  # Last 3 data points
        if len(recent) < 2:
            return "stable"
        
        first_val = recent[0][1]
        last_val = recent[-1][1]
        
        if first_val == 0:
            return "growing" if last_val > 0 else "stable"
        
        change_pct = (last_val - first_val) / first_val
        
        if change_pct > 0.1:
            return "growing"
        elif change_pct < -0.1:
            return "declining"
        return "stable"
    
    def to_dict(self) -> Dict:
        """Convert to normalized output format."""
        return {
            "source": "raydium",
            "pool_address": self.pool_address,
            "token_mint": self.token_mint,
            "quote_mint": self.quote_mint,
            "has_raydium_pool": True,
            "liquidity_sol": round(self.current_liquidity_sol, 2),
            "liquidity_usd": round(self.liquidity_usd, 2),
            "initial_liquidity_sol": round(self.initial_liquidity_sol, 2),
            "liquidity_trend": self.liquidity_trend,
            "created_at": self.creation_timestamp,
            "last_updated": self.last_updated
        }


class RaydiumScanner:
    """
    Scanner for Raydium AMM liquidity pools.
    
    Monitors for new pool creation and tracks liquidity changes
    to confirm token viability.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize Raydium scanner.
        
        Args:
            config: Solana chain config
        """
        self.config = config or {}
        self.program_id = self.config.get('programs', {}).get(
            'raydium', RAYDIUM_AMM_PROGRAM_ID
        )
        self.client = None
        self._pools: Dict[str, RaydiumPool] = {}
        self._token_to_pool: Dict[str, str] = {}  # token_mint -> pool_address
        self._processed_signatures: Set[str] = set()
        self._enabled = True
        
        # Tracking limits
        self._max_tracked_pools = 200
        self._signature_history_limit = 1000
        
    def connect(self, client) -> bool:
        """
        Set the Solana RPC client.
        
        Args:
            client: Solana RPC client instance
            
        Returns:
            True if client is valid
        """
        if client is None:
            solana_log("Raydium scanner: No client provided", "WARN")
            self._enabled = False
            return False
        
        self.client = client
        solana_log("Raydium scanner connected")
        return True
    
    def scan(self) -> List[Dict]:
        """
        Scan for new Raydium pool events (Async Wrapper).
        
        Returns:
            List of normalized pool dicts
        """
        if not self._enabled or not self.client:
            return []
        
        try:
            return asyncio.run(self._scan_async())
        except Exception as e:
            solana_log(f"Raydium scan wrapper error: {e}", "ERROR")
            if "Event loop is closed" not in str(e):
                import traceback
                traceback.print_exc()
            return []

    async def _scan_async(self) -> List[Dict]:
        """Async Staged Scan Implementation"""
        new_pools = []
        
        try:
            # Config
            limit = SOLANA_ALCHEMY_SAFE_CONFIG.get("scan_limit_signatures", 25)
            max_meta = SOLANA_ALCHEMY_SAFE_CONFIG.get("max_meta_fetch", 5)
            meta_timeout = SOLANA_ALCHEMY_SAFE_CONFIG.get("meta_timeout_seconds", 6)
            
            from solders.pubkey import Pubkey
            program_key = Pubkey.from_string(self.program_id)
            
            # --- Phase 1: Signature Scan ---
            response = await asyncio.to_thread(
                self.client.get_signatures_for_address,
                program_key,
                limit=limit
            )
            
            if not response.value:
                return []
            
            candidates = []
            
            # --- Phase 2: Heuristic Pre-filter ---
            for sig_info in response.value:
                sig = str(sig_info.signature)
                if sig in self._processed_signatures:
                    continue
                    
                if sig_info.err:
                    self._processed_signatures.add(sig)
                    continue
                
                # Check age
                if sig_info.block_time:
                    age = time.time() - sig_info.block_time
                    if age > 300: 
                        self._processed_signatures.add(sig)
                        continue
                        
                candidates.append(sig_info)
                self._processed_signatures.add(sig)

            # --- Phase 3: Lazy Meta Fetch ---
            targets = candidates[:max_meta]
            
            if not targets:
                return []
            
            tasks = []
            for sig_info in targets:
                sig_str = str(sig_info.signature)
                tasks.append(self._process_candidate_async(sig_str, meta_timeout))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, dict):
                    new_pools.append(res)
            
            # Keep bounded
            if len(self._processed_signatures) > self._signature_history_limit:
                 self._processed_signatures = set(list(self._processed_signatures)[-self._signature_history_limit:])
            
            # Update liquidity for tracked pools
            # Ensure this is also async friendly? It iterates existing pools
            # self._update_pool_liquidity() is currently sync/blocking RPC calls... 
            # We should wrap it in to_thread or optimize it too.
            # ideally separate task, but for now wrap it.
            await asyncio.to_thread(self._update_pool_liquidity)
            
        except Exception as e:
            solana_log(f"Raydium async scan error: {e}", "ERROR")
        
        return new_pools

    async def _process_candidate_async(self, signature: str, timeout: float) -> Optional[Dict]:
        """Fetch and parse pool creation asynchronous."""
        try:
             # Wrap blocking get_transaction
            from solana.rpc.commitment import Confirmed
            
            def fetch_tx():
                return self.client.get_transaction(
                    signature,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0
                )
            
            try:
                tx_response = await asyncio.wait_for(
                    asyncio.to_thread(fetch_tx),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                if SOLANA_ALCHEMY_SAFE_CONFIG.get("downgrade_on_timeout"):
                    return None
                raise

            if not tx_response.value:
                return None
            
            tx = tx_response.value
            meta = tx.meta if hasattr(tx, 'meta') else None
            
            if not meta and SOLANA_ALCHEMY_SAFE_CONFIG.get("skip_on_no_meta"):
                return None

            # Check logs
            if hasattr(meta, 'log_messages') and meta.log_messages:
                logs = meta.log_messages
                is_pool_init = any('Initialize' in log or 'InitPool' in log for log in logs)
                if is_pool_init:
                    return self._extract_pool_creation(tx, meta, signature)
                    
        except Exception:
            pass
        return None
    
    def _parse_raydium_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse a Raydium transaction for pool creation.
        
        Args:
            signature: Transaction signature
            
        Returns:
            Pool dict or None
        """
        try:
            rate_limit_rpc()
            
            response = self.client.get_transaction(
                signature,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not response.value:
                return None
            
            tx = response.value
            meta = tx.meta if hasattr(tx, 'meta') else None
            
            if not meta:
                return None
            
            # Check logs for pool initialization
            if hasattr(meta, 'log_messages') and meta.log_messages:
                logs = meta.log_messages
                is_pool_init = any(
                    'Initialize' in log or 'InitPool' in log 
                    for log in logs
                )
                
                if is_pool_init:
                    return self._extract_pool_creation(tx, meta, signature)
            
        except Exception:
            pass
        
        return None
    
    def _extract_pool_creation(self, tx, meta, signature: str) -> Optional[Dict]:
        """Extract pool creation details from transaction."""
        try:
            tx_data = tx.transaction if hasattr(tx, 'transaction') else tx
            block_time = getattr(tx, 'block_time', None) or time.time()
            
            message = tx_data.message if hasattr(tx_data, 'message') else None
            if not message:
                return None
            
            account_keys = message.account_keys if hasattr(message, 'account_keys') else []
            
            if len(account_keys) < 3:
                return None
            
            # Pool address is usually one of the first accounts
            pool_address = str(account_keys[1]) if len(account_keys) > 1 else None
            
            # Find token mints from post token balances
            token_mint = None
            quote_mint = WRAPPED_SOL_MINT
            initial_liquidity = 0.0
            
            if hasattr(meta, 'post_token_balances') and meta.post_token_balances:
                for balance in meta.post_token_balances:
                    mint = str(balance.mint) if hasattr(balance, 'mint') else None
                    if mint and mint != WRAPPED_SOL_MINT:
                        token_mint = mint
                        break
            
            # Calculate initial liquidity from SOL balance changes
            if hasattr(meta, 'pre_balances') and hasattr(meta, 'post_balances'):
                pre = list(meta.pre_balances)
                post = list(meta.post_balances)
                for i in range(min(len(pre), len(post))):
                    diff = post[i] - pre[i]
                    if diff > 0:
                        initial_liquidity += parse_lamports_to_sol(diff)
            
            if not pool_address or not token_mint:
                return None
            
            # Create pool record
            pool = RaydiumPool(
                pool_address=pool_address,
                token_mint=token_mint,
                quote_mint=quote_mint,
                creation_timestamp=block_time,
                initial_liquidity_sol=initial_liquidity,
                current_liquidity_sol=initial_liquidity
            )
            pool.liquidity_history.append((block_time, initial_liquidity))
            
            self._pools[pool_address] = pool
            self._token_to_pool[token_mint] = pool_address
            
            solana_log(f"💧 New Raydium pool: {pool_address[:8]}... Token: {token_mint[:8]}... Liq: {initial_liquidity:.2f} SOL")
            
            return pool.to_dict()
            
        except Exception as e:
            solana_log(f"Pool creation parse error: {e}", "WARN")
        
        return None
    
    def _update_pool_liquidity(self):
        """Update liquidity for tracked pools."""
        if not self.client:
            return
        
        now = time.time()
        update_interval = 60  # Update every 60 seconds
        
        for pool in self._pools.values():
            if now - pool.last_updated < update_interval:
                continue
            
            try:
                rate_limit_rpc()
                
                from solders.pubkey import Pubkey
                
                pool_key = Pubkey.from_string(pool.pool_address)
                
                # Get account info
                response = self.client.get_account_info(pool_key)
                
                if response.value:
                    # Parse lamports as liquidity proxy
                    lamports = response.value.lamports
                    new_liquidity = parse_lamports_to_sol(lamports)
                    
                    pool.current_liquidity_sol = new_liquidity
                    pool.liquidity_history.append((now, new_liquidity))
                    pool.last_updated = now
                    
                    # Keep history bounded
                    if len(pool.liquidity_history) > 100:
                        pool.liquidity_history = pool.liquidity_history[-50:]
                        
            except Exception:
                pass
        
        # Clean old pools
        self._cleanup_old_pools()
    
    def _cleanup_old_pools(self):
        """Remove pools older than 24 hours."""
        now = time.time()
        cutoff = now - 86400  # 24 hours
        
        to_remove = [
            addr for addr, pool in self._pools.items()
            if pool.creation_timestamp < cutoff
        ]
        
        for addr in to_remove:
            pool = self._pools[addr]
            if pool.token_mint in self._token_to_pool:
                del self._token_to_pool[pool.token_mint]
            del self._pools[addr]
    
    def has_pool(self, token_mint: str) -> bool:
        """Check if token has a Raydium pool."""
        return token_mint in self._token_to_pool
    
    def get_pool_for_token(self, token_mint: str) -> Optional[Dict]:
        """Get pool data for a token."""
        pool_addr = self._token_to_pool.get(token_mint)
        if pool_addr and pool_addr in self._pools:
            return self._pools[pool_addr].to_dict()
        return None
    
    def get_liquidity_data(self, token_mint: str) -> Dict:
        """
        Get liquidity data for a token.
        
        Returns standardized dict for scoring.
        """
        pool_data = self.get_pool_for_token(token_mint)
        
        if not pool_data:
            return {
                "has_raydium_pool": False,
                "liquidity_usd": 0,
                "liquidity_trend": "unknown"
            }
        
        return {
            "has_raydium_pool": True,
            "liquidity_usd": pool_data.get("liquidity_usd", 0),
            "liquidity_sol": pool_data.get("liquidity_sol", 0),
            "liquidity_trend": pool_data.get("liquidity_trend", "stable")
        }
    
    def get_all_pools(self) -> List[Dict]:
        """Get all tracked pools."""
        return [p.to_dict() for p in self._pools.values()]
    
    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            "enabled": self._enabled,
            "tracked_pools": len(self._pools),
            "token_mappings": len(self._token_to_pool),
            "processed_signatures": len(self._processed_signatures),
            "program_id": self.program_id
        }
