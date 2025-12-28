"""
Pump.fun Scanner - Early Meme Token Detection

Monitors the Pump.fun program for:
- New token creation events
- Initial SOL inflow
- Buy velocity (buys/min)
- Creator wallet behavior

Output: Normalized token events for scoring

CRITICAL: READ-ONLY - No execution, no wallets
"""
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .solana_utils import (
    PUMPFUN_PROGRAM_ID,
    parse_lamports_to_sol,
    is_valid_solana_address,
    solana_log,
    sol_to_usd,
    rate_limit_rpc
)
from config import SOLANA_ALCHEMY_SAFE_CONFIG
import asyncio


@dataclass
class PumpfunToken:
    """Represents a token detected from Pump.fun."""
    token_address: str
    creator_wallet: str
    creation_timestamp: float
    name: str = "UNKNOWN"
    symbol: str = "???"
    sol_inflow: float = 0.0
    buy_count: int = 0
    unique_buyers: int = 0
    creator_sold: bool = False
    creator_sell_amount: float = 0.0
    last_updated: float = field(default_factory=time.time)
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.creation_timestamp
    
    @property
    def buy_velocity(self) -> float:
        """Buys per minute."""
        age_min = max(self.age_seconds / 60, 1/60)  # At least 1 second
        return self.buy_count / age_min
    
    def to_dict(self) -> Dict:
        """Convert to normalized output format."""
        return {
            "source": "pumpfun",
            "token_address": self.token_address,
            "creator_wallet": self.creator_wallet,
            "name": self.name,
            "symbol": self.symbol,
            "age_seconds": round(self.age_seconds, 1),
            "sol_inflow": round(self.sol_inflow, 2),
            "sol_inflow_usd": round(sol_to_usd(self.sol_inflow), 2),
            "buy_count": self.buy_count,
            "buy_velocity": round(self.buy_velocity, 1),
            "unique_buyers": self.unique_buyers,
            "creator_sold": self.creator_sold,
            "creator_sell_amount": round(self.creator_sell_amount, 2),
            "last_updated": self.last_updated
        }


class PumpfunScanner:
    """
    Scanner for Pump.fun token launches.
    
    Monitors the Pump.fun program for new token creation and tracks
    early trading activity for sniper detection.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize Pump.fun scanner.
        
        Args:
            config: Solana chain config with rpc_url and programs
        """
        self.config = config or {}
        self.program_id = self.config.get('programs', {}).get(
            'pumpfun', PUMPFUN_PROGRAM_ID
        )
        self.client = None
        self._tokens: Dict[str, PumpfunToken] = {}
        self._processed_signatures: Set[str] = set()
        self._last_scan_slot: int = 0
        self._enabled = True
        
        # Tracking limits
        self._max_tracked_tokens = 100
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
            solana_log("Pump.fun scanner: No client provided", "WARN")
            self._enabled = False
            return False
        
        self.client = client
        solana_log("Pump.fun scanner connected")
        return True

    def scan(self) -> List[Dict]:
        """
        Scan for new Pump.fun token events (Async Wrapper).
        
        Returns:
            List of normalized token dicts
        """
        if not self._enabled or not self.client:
            return []
            
        try:
            # Run async scan in a new event loop
            return asyncio.run(self._scan_async())
        except Exception as e:
            solana_log(f"Pump.fun scan wrapper error: {e}", "ERROR")
            if "Event loop is closed" not in str(e):
                import traceback
                traceback.print_exc()
            return []

    async def _scan_async(self) -> List[Dict]:
        """
        Staged Scan Implementation:
        Phase 1: Signature scan ONLY
        Phase 2: Heuristic pre-filter
        Phase 3: Lazy meta fetch (Top N)
        """
        new_tokens = []
        
        try:
            # Config
            limit = SOLANA_ALCHEMY_SAFE_CONFIG.get("scan_limit_signatures", 25)
            max_meta = SOLANA_ALCHEMY_SAFE_CONFIG.get("max_meta_fetch", 5)
            meta_timeout = SOLANA_ALCHEMY_SAFE_CONFIG.get("meta_timeout_seconds", 6)
            
            # --- Phase 1: Signature Scan ---
            from solders.pubkey import Pubkey
            program_key = Pubkey.from_string(self.program_id)
            
            # Run blocking RPC call in thread
            response = await asyncio.to_thread(
                self.client.get_signatures_for_address,
                program_key,
                limit=limit
            )
            
            if not response.value:
                return []
            
            signatures = response.value
            solana_log(f"Fetched {len(signatures)} signatures from Pump.fun program", "DEBUG")
            
            # New filtered list
            candidates = []
            
            # --- Phase 2: Heuristic Pre-filter ---
            for sig_info in signatures:
                sig = str(sig_info.signature)
                
                # Skip processed
                if sig in self._processed_signatures:
                    continue
                
                # Skip errors
                if sig_info.err:
                    self._processed_signatures.add(sig) # Mark bad ones as processed to skip next time
                    continue
                    
                # Heuristic: Check age (blockTime)
                if sig_info.block_time:
                    age = time.time() - sig_info.block_time
                    if age > 300: # Skip signatures older than 5 mins
                        self._processed_signatures.add(sig)
                        continue
                
                candidates.append(sig_info)
                self._processed_signatures.add(sig)
            
            solana_log(f"Found {len(candidates)} new candidate signatures (processed: {len(self._processed_signatures)})", "DEBUG")
            # They are namedtuple-like, assume order is correct or sort by block_time desc
            
            # --- Phase 3: Lazy Meta Fetch ---
            # Take top N candidates
            targets = candidates[:max_meta]
            
            if not targets:
                return []
                
            solana_log(f"Processing {len(targets)}/{len(candidates)} candidates (Safe Mode)", "DEBUG")
            
            # Fetch metas in parallel
            tasks = []
            for sig_info in targets:
                sig_str = str(sig_info.signature)
                tasks.append(
                    self._process_candidate_async(sig_str, meta_timeout)
                )
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in results:
                if isinstance(res, dict):
                    new_tokens.append(res)
                elif isinstance(res, Exception):
                    # Log but don't crash
                    pass
            
            # Cleanup history
            if len(self._processed_signatures) > self._signature_history_limit:
                excess = len(self._processed_signatures) - self._signature_history_limit
                # Quick set reduction
                self._processed_signatures = set(list(self._processed_signatures)[-self._signature_history_limit:])
                solana_log(f"Cleaned {excess} old signatures from history", "DEBUG")
                
            # Update tracked tokens
            self._update_tracked_tokens()
            
            solana_log(f"Scan cycle complete: {len(new_tokens)} new candidates", "DEBUG")

        except Exception as e:
            solana_log(f"Pump.fun async scan error: {e}", "ERROR")
            
        return new_tokens

    async def _process_candidate_async(self, signature: str, timeout: float) -> Optional[Dict]:
        """Fetch and parse transaction asynchronously with timeout."""
        try:
            # Wrap blocking get_transaction in thread + wait_for
            from solana.rpc.commitment import Confirmed
            from solders.signature import Signature
            
            sig_obj = Signature.from_string(signature)
            
            # Define the blocking call
            def fetch_tx():
                from solana.rpc.commitment import Finalized
                return self.client.get_transaction(
                    sig_obj,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0,
                    commitment=Finalized
                )
            
            try:
                tx_response = await asyncio.wait_for(
                    asyncio.to_thread(fetch_tx),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                solana_log(f"TX Timeout {signature[:8]}...", "DEBUG")
                return None
            except Exception as e:
                solana_log(f"TX Fetch Error {signature[:8]}...: {e}", "DEBUG")
                return None
            
            if not tx_response.value:
                solana_log(f"TX {signature[:8]}... returned None", "DEBUG")
                return None
                
            tx = tx_response.value
            
            # Debug: Check transaction structure
            if tx is None:
                solana_log(f"TX {signature[:8]}... tx object is None", "DEBUG")
                return None
            
            # Check for dict vs object (Alchemy can vary)
            if isinstance(tx, dict):
                meta = tx.get('meta')
                tx_data = tx.get('transaction')
                solana_log(f"TX {signature[:8]}... Dict format, meta keys: {list(meta.keys()) if meta else 'None'}", "DEBUG")
            else:
                meta = tx.meta if hasattr(tx, 'meta') else None
                tx_data = tx.transaction if hasattr(tx, 'transaction') else tx
                solana_log(f"TX {signature[:8]}... Object format, has meta: {meta is not None}", "DEBUG")
            
            # Metadata may be missing on very early transactions; continue with minimal parsing
            metadata_status = 'present' if meta else 'missing'
            
            # Debug: log transaction structure
            is_creation_check = self._is_token_creation(tx_data, meta)
            is_buy_check = self._is_buy_transaction(tx_data, meta)
            
            # Log instruction details
            try:
                instructions = []
                if isinstance(tx_data, dict):
                    msg = tx_data.get('message', {})
                    instructions = msg.get('instructions', [])
                    solana_log(f"TX {signature[:8]}... Has {len(instructions)} instructions (dict)", "DEBUG")
                else:
                    msg = getattr(tx_data, 'message', None)
                    instructions = getattr(msg, 'instructions', []) if msg else []
                    solana_log(f"TX {signature[:8]}... Has {len(instructions)} instructions (object)", "DEBUG")
                
                if instructions:
                    for i, instr in enumerate(instructions[:3]):  # Log first 3
                        if isinstance(instr, dict):
                            prog = instr.get('programId', 'unknown')
                        else:
                            prog = getattr(instr, 'program_id', 'unknown')
                        solana_log(f"  Instr {i}: {prog}", "DEBUG")
            except Exception as e:
                solana_log(f"TX {signature[:8]}... Error logging instructions: {e}", "DEBUG")
            
            solana_log(f"TX {signature[:8]}... | Creation={is_creation_check}, Buy={is_buy_check}, Meta={metadata_status}", "DEBUG")
            
            if is_creation_check or (meta is None):
                res = self._extract_token_creation(tx_data, meta, signature)
                if res: 
                    # annotate tx signature and metadata status
                    res['tx_signature'] = signature
                    res['metadata_status'] = metadata_status
                    solana_log(f"✅ Creation: {res.get('symbol')} ({signature[:8]})", "DEBUG")
                    return res
                else:
                    solana_log(f"❌ Creation extraction failed for {signature[:8]}... (meta={metadata_status})", "DEBUG")
                
            if is_buy_check:
                res = self._extract_buy_event(tx_data, meta, signature)
                if res:
                    res['tx_signature'] = signature
                    res['metadata_status'] = metadata_status
                    solana_log(f"✅ Buy event: {res.get('symbol')} ({signature[:8]})", "DEBUG")
                    return res
                else:
                    solana_log(f"❌ Buy extraction failed for {signature[:8]}...", "DEBUG")

                
        except Exception as e:
            # solana_log(f"Candidate process error: {e}", "DEBUG")
            pass
            
        return None
    
    def _parse_pumpfun_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse a Pump.fun transaction for token creation or buy events.
        
        Args:
            signature: Transaction signature (string)
            
        Returns:
            Token event dict or None
        """
        try:
            rate_limit_rpc()
            
            from solana.rpc.types import TxOpts
            from solders.signature import Signature
            
            # Convert string signature to Signature object
            sig_obj = Signature.from_string(signature)
            
            # Retry logic for fetching transaction
            tx = self._get_transaction_with_retry(sig_obj)
            
            if not tx:
                return None
            
            tx_data = tx.transaction if hasattr(tx, 'transaction') else tx
            
            # Get transaction meta
            meta = tx.meta if hasattr(tx, 'meta') else None
            # Allow processing to continue even if meta missing
            if not meta:
                solana_log(f"No meta for {signature[:8]}... (continuing)", "DEBUG")
            
            # Check if it's a token creation (look for InitializeMint)
            is_creation = self._is_token_creation(tx_data, meta)
            is_buy = self._is_buy_transaction(tx_data, meta)
            
            # --- DEEP DEBUG START ---
            # Print logs for the first transaction in a batch to debug parsing
            if hasattr(meta, 'log_messages') and meta.log_messages:
                logs_str = str(meta.log_messages)
                
                # Sample 5% of transactions to confirm we are reading data correctly
                import random
                if random.random() < 0.05:
                     solana_log(f"🔎 SAMPLE TX {signature[:8]}: {logs_str[:150]}...", "DEBUG")

                if 'Create' in logs_str or 'Mint' in logs_str: 
                    # Only log if it LOOKS relevant but failed detection
                    if not is_creation and not is_buy:
                         solana_log(f"🕵️ DEBUG TX {signature[:8]}: Logs found but not detected as Create/Buy: {logs_str[:200]}...", "DEBUG")
            # --- DEEP DEBUG END ---

            solana_log(f"TX {signature[:8]}: creation={is_creation}, buy={is_buy}", "DEBUG")
            
            if is_creation or (meta is None):
                res = self._extract_token_creation(tx_data, meta, signature)
                if res:
                    res['tx_signature'] = signature
                    res['metadata_status'] = 'present' if meta else 'missing'
                return res
            
            # Check if it's a buy transaction
            if is_buy:
                res = self._extract_buy_event(tx_data, meta, signature)
                if res:
                    res['tx_signature'] = signature
                    res['metadata_status'] = 'present' if meta else 'missing'
                return res
            
        except Exception as e:
            # Log parsing errors with full details for debugging
            error_msg = f"{type(e).__name__}: {str(e)}"
            solana_log(f"Transaction parse error for {signature[:8]}...: {error_msg}", "DEBUG")
            if "cannot be converted" in str(e) or "Signature" in str(e):
                # This is critical, print full traceback
                import traceback
                traceback.print_exc()
        
        return None
    
    def _get_transaction_with_retry(self, sig_obj, max_retries=2, initial_delay=1.0):
        """
        Fetch transaction with retry logic to handle RPC eventual consistency.
        
        Args:
            sig_obj: Signature object
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            
        Returns:
            Transaction object or None
        """
        for i in range(max_retries + 1):
            try:
                from solana.rpc.commitment import Confirmed
                response = self.client.get_transaction(
                    sig_obj,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0,
                    commitment=Confirmed
                )
                
                if response.value:
                    tx = response.value
                    # Return even if meta is missing; downstream will handle gracefully
                    return tx
                    
                # If no value or no meta, wait and retry
                if i < max_retries:
                    time.sleep(initial_delay * (i + 1))  # Increasing backoff
                    
            except Exception as e:
                if i < max_retries:
                    time.sleep(initial_delay * (i + 1))
                else:
                    solana_log(f"Failed to fetch TX {str(sig_obj)[:8]}...: {repr(e)}", "DEBUG")
        
        return None
    
    def _is_token_creation(self, tx_data, meta) -> bool:
        """Check if transaction is a token creation - works with or without metadata."""
        try:
            # Method 1: Check logs if available
            logs = []
            if isinstance(meta, dict):
                logs = meta.get('logMessages', [])
            else:
                logs = getattr(meta, 'log_messages', []) if meta else []
            
            if logs:
                for log in logs:
                    if 'Create' in log and self.program_id in log:
                        return True
                    if 'InitializeMint' in log:
                        return True
            
            # Method 2: Fallback - check if this transaction touches Pump.fun program
            # (if no logs, assume it might be a creation based on program interaction)
            if not logs and meta is None:
                # When no metadata, check tx_data for pumpfun program
                instructions = []
                if isinstance(tx_data, dict):
                    msg = tx_data.get('message', {})
                    instructions = msg.get('instructions', [])
                else:
                    msg = getattr(tx_data, 'message', None)
                    instructions = getattr(msg, 'instructions', []) if msg else []
                
                # If transaction calls pumpfun program, assume it could be creation
                # (more aggressive detection without metadata)
                for instr in instructions:
                    if isinstance(instr, dict):
                        program_id = instr.get('programId')
                    else:
                        program_id = getattr(instr, 'program_id', None)
                    
                    if program_id and str(program_id) == self.program_id:
                        return True  # Pumpfun program called - likely creation
                
        except Exception:
            pass
        return False
    
    def _is_buy_transaction(self, tx_data, meta) -> bool:
        """Check if transaction is a buy (SOL in, tokens out)."""
        try:
            pre, post = [], []
            if isinstance(meta, dict):
                pre = meta.get('preBalances', [])
                post = meta.get('postBalances', [])
            else:
                pre = getattr(meta, 'pre_balances', [])
                post = getattr(meta, 'post_balances', [])
                
            if pre and post:
                # Basic heuristic: if user spent SOL and it's a pumpfun interaction
                # (Refining this would require deeper parsing of inner instructions)
                if post[0] < pre[0]:
                    return True
        except Exception:
            pass
        return False

    
    def _extract_token_creation(self, tx_data, meta, signature: str) -> Optional[Dict]:
        """Extract token creation details."""
        try:
            # Handle both object and dict formats for tx_data
            if isinstance(tx_data, dict):
                block_time = tx_data.get('blockTime') or time.time()
                message = tx_data.get('message', {})
                account_keys = message.get('accountKeys', [])
            else:
                block_time = getattr(tx_data, 'block_time', None) or time.time()
                message = getattr(tx_data, 'message', None)
                account_keys = getattr(message, 'account_keys', []) if message else []
            
            if not account_keys:
                return None
            
            # Creator is usually the first account
            creator = str(account_keys[0])
            
            # Get Mint from token balances (more reliable than account order)
            token_address = None
            post_token_balances = []
            if isinstance(meta, dict):
                post_token_balances = meta.get('postTokenBalances', [])
            else:
                post_token_balances = getattr(meta, 'post_token_balances', [])

            if post_token_balances:
                for balance in post_token_balances:
                    mint = balance.get('mint') if isinstance(balance, dict) else getattr(balance, 'mint', None)
                    if mint:
                        token_address = str(mint)
                        break
            
            if not token_address:
                # Fallback to account index 1 if balances empty
                if len(account_keys) > 1:
                    token_address = str(account_keys[1])
                else:
                    return None

            
            # Calculate initial SOL inflow (may be 0 if meta missing)
            sol_inflow = 0.0
            pre, post = [], []
            if isinstance(meta, dict):
                pre = meta.get('preBalances', [])
                post = meta.get('postBalances', [])
            else:
                pre = getattr(meta, 'pre_balances', [])
                post = getattr(meta, 'post_balances', [])

            if pre and post:
                for i in range(min(len(pre), len(post))):
                    diff = pre[i] - post[i]
                    if diff > 0:
                        sol_inflow += parse_lamports_to_sol(diff)

            
            # Create token record
            token = PumpfunToken(
                token_address=token_address,
                creator_wallet=creator,
                creation_timestamp=block_time,
                sol_inflow=sol_inflow,
                buy_count=1
            )
            
            self._tokens[token_address] = token
            
            solana_log(f"🧪 New Pump.fun token: {token_address[:8]}... (SOL: {sol_inflow:.2f})")
            
            out = token.to_dict()
            out['tx_signature'] = signature
            out['metadata_status'] = 'present' if meta else 'missing'
            return out
            
        except Exception as e:
            solana_log(f"Token creation parse error: {e}", "WARN")
        
        return None
    
    def _extract_buy_event(self, tx_data, meta, signature: str) -> Optional[Dict]:
        """Extract buy event and update token tracking."""
        try:
            # Handle both object and dict formats
            if isinstance(tx_data, dict):
                message = tx_data.get('message', {})
                account_keys = message.get('accountKeys', [])
            else:
                message = getattr(tx_data, 'message', None)
                account_keys = getattr(message, 'account_keys', []) if message else []

            # Find buyer (first account usually)
            buyer = str(account_keys[0]) if account_keys else None
            
            # Calculate SOL spent
            sol_spent = 0.0
            pre, post = [], []
            if isinstance(meta, dict):
                pre = meta.get('preBalances', [])
                post = meta.get('postBalances', [])
            else:
                pre = getattr(meta, 'pre_balances', [])
                post = getattr(meta, 'post_balances', [])

            if pre and post:
                sol_spent = parse_lamports_to_sol(pre[0] - post[0])


            
            # Try to identify which token was bought
            token_address = None
            post_token = []
            if isinstance(meta, dict):
                post_token = meta.get('postTokenBalances', [])
            else:
                post_token = getattr(meta, 'post_token_balances', [])

            if post_token:
                for balance in post_token:
                    mint = balance.get('mint') if isinstance(balance, dict) else getattr(balance, 'mint', None)
                    mint_str = str(mint) if mint else None
                    if mint_str and mint_str in self._tokens:
                        token_address = mint_str
                        break

            
            if token_address and token_address in self._tokens:
                token = self._tokens[token_address]
                token.sol_inflow += sol_spent
                token.buy_count += 1
                token.last_updated = time.time()
                
                # Check if creator sold
                if buyer == token.creator_wallet and sol_spent < 0:
                    token.creator_sold = True
                    token.creator_sell_amount += abs(sol_spent)
                
                out = token.to_dict()
                out['tx_signature'] = signature
                out['metadata_status'] = 'present' if meta else 'missing'
                return out
            
        except Exception:
            pass
        
        return None
    
    def _update_tracked_tokens(self):
        """Clean up old tokens and update stats."""
        now = time.time()
        cutoff = now - 3600  # Remove tokens older than 1 hour
        
        to_remove = []
        for addr, token in self._tokens.items():
            if token.creation_timestamp < cutoff:
                to_remove.append(addr)
        
        for addr in to_remove:
            del self._tokens[addr]
        
        # Also limit total tracked
        if len(self._tokens) > self._max_tracked_tokens:
            # Remove oldest
            sorted_tokens = sorted(
                self._tokens.items(),
                key=lambda x: x[1].creation_timestamp
            )
            for addr, _ in sorted_tokens[:len(self._tokens) - self._max_tracked_tokens]:
                del self._tokens[addr]
    
    def get_token(self, token_address: str) -> Optional[Dict]:
        """Get tracked token by address."""
        token = self._tokens.get(token_address)
        return token.to_dict() if token else None
    
    def get_all_tokens(self) -> List[Dict]:
        """Get all tracked tokens."""
        return [t.to_dict() for t in self._tokens.values()]
    
    def get_sniper_candidates(self, max_age_seconds: int = 120) -> List[Dict]:
        """
        Get tokens eligible for sniper alerts.
        
        Args:
            max_age_seconds: Maximum token age
            
        Returns:
            List of token dicts meeting sniper criteria
        """
        candidates = []
        for token in self._tokens.values():
            if token.age_seconds <= max_age_seconds and not token.creator_sold:
                candidates.append(token.to_dict())
        return candidates
    
    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            "enabled": self._enabled,
            "tracked_tokens": len(self._tokens),
            "processed_signatures": len(self._processed_signatures),
            "program_id": self.program_id
        }
