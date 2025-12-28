"""
Solana Scanner - Raw JSON-RPC Parser

Fully RAW JSON-RPC based parser for Pump.fun + Raydium events.
No SDK abstractions, direct RPC calls with deterministic parsing.

KEY FEATURES:
- Raw getTransaction JSON-RPC calls
- Instruction flattening from message + innerInstructions
- Hardcoded program ID filtering
- Metadata-less safe mode
- Sniper-grade deterministic state machine

EXPECTED LOG FLOW:
[SOLANA][RAW] meta ok
[SOLANA][PUMP] new token detected
[SOLANA][STATE] DETECTED
[SOLANA][RAYDIUM] LP detected
[SOLANA][SCORE] boosted
[SOLANA][SNIPER] ARMED

CRITICAL: READ-ONLY - No execution, no wallets
"""
import time
import asyncio
from typing import Dict, List, Optional

from .solana_utils import solana_log
from .raw_solana_parser import RawSolanaParser
from .token_state import TokenStateMachine


class SolanaScanner:
    """
    Raw JSON-RPC based Solana scanner.

    Uses fully RAW parsing for sniper-grade detection of Pump.fun + Raydium events.
    No SDK abstractions, deterministic state machine.
    """

    def __init__(self, config: Dict = None):
        """
        Initialize raw Solana scanner.

        Args:
            config: Solana chain config from chains.yaml
        """
        self.config = config or {}
        self.chain_name = "solana"
        self.chain_prefix = "[SOL]"

        # Raw RPC URL
        self.rpc_url = self.config.get('rpc_url', 'https://api.mainnet-beta.solana.com')

        # Raw parser
        self.raw_parser = RawSolanaParser(self.rpc_url)

        # State
        self._connected = True  # Always connected for raw RPC
        self._last_scan_time = 0
        self._scan_interval = 5  # seconds between scans

        # Token cache for unified events
        self._token_cache: Dict[str, Dict] = {}
        self._cache_ttl = 3600  # 1 hour cache
        
    def connect(self) -> bool:
        """
        Connect all sub-scanners to Solana RPC.
        
        Returns:
            True if at least Pump.fun scanner connected
        """
        if not self.client:
            solana_log("No Solana client available", "ERROR")
            return False
        
        # Connect sub-scanners
        pumpfun_ok = self.pumpfun.connect(self.client)
        raydium_ok = self.raydium.connect(self.client)
        jupiter_ok = self.jupiter.connect(self.client)
        
        # Connect metadata resolver and LP detector
        self.metadata_resolver.set_client(self.client)
        self.lp_detector.set_client(self.client)
        
        self._connected = pumpfun_ok  # Pump.fun is required
        
        if self._connected:
            solana_log(f"✅ Connected to Solana (Pump.fun: {pumpfun_ok}, Raydium: {raydium_ok}, Jupiter: {jupiter_ok}, Metadata: OK, LP Detector: OK)")
        else:
            solana_log("Failed to connect Pump.fun scanner", "ERROR")
        
        return self._connected
    
    def scan_new_pairs(self) -> List[Dict]:
        """
        Scan for new tokens and return unified events WITH METADATA RESOLUTION.
        
        Handles both sync and async calling contexts properly.
        
        Returns:
            List of unified token dicts with all available data
        """
        if not self._connected:
            return []
        
        # Rate limit scans
        now = time.time()
        if now - self._last_scan_time < self._scan_interval:
            return []
        self._last_scan_time = now
        
        unified_events = []
        
        try:
            # Scan all sources
            pumpfun_tokens = self.pumpfun.scan()
            raydium_pools = self.raydium.scan()
            jupiter_data = self.jupiter.scan()
            
            # DEBUG: Log scan results
            if pumpfun_tokens or raydium_pools or jupiter_data:
                solana_log(f"Scan results: Pumpfun={len(pumpfun_tokens)}, Raydium={len(raydium_pools)}, Jupiter={len(jupiter_data)}")
            else:
                solana_log("Scan cycle complete: 0 new candidates", "DEBUG")
            
            # Process Pump.fun tokens with metadata resolution
            for token in pumpfun_tokens:
                try:
                    # Try to get event loop for async metadata resolution
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # In async context, use executor
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(asyncio.run, self._create_unified_event_async_wrapper(token))
                                unified = future.result(timeout=10)
                        else:
                            # Not running, use asyncio.run
                            unified = asyncio.run(self._create_unified_event_async_wrapper(token))
                    except RuntimeError:
                        # No event loop, create one
                        unified = asyncio.run(self._create_unified_event_async_wrapper(token))
                    
                    if unified:
                        unified_events.append(unified)
                        name = unified.get('name', 'UNKNOWN')
                        symbol = unified.get('symbol', '???')
                        state = unified.get('state', 'UNKNOWN')
                        solana_log(f"New token detected: {name} ({symbol}) | State: {state}")
                except Exception as e:
                    solana_log(f"Error processing token {token.get('token_address', '???')}: {e}", "ERROR")
                    continue
            
            # Check for Raydium pools for cached tokens
            for pool in raydium_pools:
                token_mint = pool.get('token_mint')
                if token_mint and token_mint in self._token_cache:
                    # Update cached token with Raydium data
                    self._token_cache[token_mint].update({
                        'has_raydium_pool': True,
                        'raydium_pool': pool.get('pool_address'),
                        'liquidity_usd': pool.get('liquidity_usd', 0),
                        'liquidity_trend': pool.get('liquidity_trend', 'stable')
                    })
            
            # Update Jupiter data for cached tokens
            for jup_token in jupiter_data:
                token_mint = jup_token.get('token_mint')
                if token_mint and token_mint in self._token_cache:
                    self._token_cache[token_mint].update({
                        'jupiter_listed': True,
                        'jupiter_volume_24h': jup_token.get('volume_24h_usd', 0),
                        'routing_trend': jup_token.get('routing_trend', 'stable')
                    })
            
            # Cleanup old cache entries
            self._cleanup_cache()
            
        except Exception as e:
            solana_log(f"Scan error: {e}", "ERROR")
            import traceback
            traceback.print_exc()
        
        return unified_events
    
    async def _create_unified_event_async_wrapper(self, token: Dict) -> Optional[Dict]:
        """Wrapper for async metadata resolution."""
        return await self._create_unified_event_async(token)
    
    def _create_unified_event(self, pumpfun_token: Dict) -> Optional[Dict]:
        """
        Create unified token event from Pump.fun data.
        
        NOW WITH METADATA RESOLUTION + STATE MACHINE!
        
        Args:
            pumpfun_token: Token data from Pump.fun scanner
            
        Returns:
            Unified token dict with all available data
        """
        token_address = pumpfun_token.get('token_address')
        if not token_address:
            return None
        
        # Get additional data from other scanners
        raydium_data = self.raydium.get_liquidity_data(token_address)
        jupiter_data = self.jupiter.get_momentum_data(token_address)
        
        # Get or create state record
        symbol = pumpfun_token.get('symbol', '???')
        state_record = self.state_machine.create_token(token_address, symbol)
        
        # Build unified event
        unified = {
            # Core identity
            'chain': 'solana',
            'chain_prefix': self.chain_prefix,
            'address': token_address,
            'token_address': token_address,
            'tx_signature': pumpfun_token.get('tx_signature'),
            
            # Pump.fun data
            'source': 'pumpfun',
            'name': pumpfun_token.get('name', 'UNKNOWN'),
            'symbol': pumpfun_token.get('symbol', '???'),
            'creator_wallet': pumpfun_token.get('creator_wallet', ''),
            'age_seconds': pumpfun_token.get('age_seconds', 0),
            'age_minutes': pumpfun_token.get('age_seconds', 0) / 60,
            'sol_inflow': pumpfun_token.get('sol_inflow', 0),
            'sol_inflow_usd': pumpfun_token.get('sol_inflow_usd', 0),
            'buy_count': pumpfun_token.get('buy_count', 0),
            'buy_velocity': pumpfun_token.get('buy_velocity', 0),
            'unique_buyers': pumpfun_token.get('unique_buyers', 0),
            'creator_sold': pumpfun_token.get('creator_sold', False),
            'metadata_status': pumpfun_token.get('metadata_status', 'missing'),
            
            # Raydium data
            'has_raydium_pool': raydium_data.get('has_raydium_pool', False),
            'liquidity_usd': raydium_data.get('liquidity_usd', 0),
            'liquidity_sol': raydium_data.get('liquidity_sol', 0),
            'liquidity_trend': raydium_data.get('liquidity_trend', 'unknown'),
            
            # Jupiter data
            'jupiter_listed': jupiter_data.get('jupiter_listed', False),
            'jupiter_volume_24h': jupiter_data.get('volume_24h_usd', 0),
            'routing_trend': jupiter_data.get('routing_trend', 'unknown'),
            'jupiter_active': jupiter_data.get('is_active', False),
            
            # ====== NEW: Metadata + State Machine ======
            'state': state_record.current_state.value,
            'metadata_resolved': state_record.metadata_resolved,
            'lp_detected': state_record.lp_detected,
            'lp_valid': state_record.lp_valid,
            'token_state_record': state_record.to_dict(),
            
            # Computed fields
            'timestamp': time.time()
        }
        
        # Cache for later updates
        self._token_cache[token_address] = unified
        
        return unified
    
    async def _create_unified_event_async(self, pumpfun_token: Dict) -> Optional[Dict]:
        """
        Create unified token event with METADATA RESOLUTION.
        
        This is the NEW async version that:
        1. Resolves metadata from Metaplex
        2. Detects Raydium LP
        3. Updates state machine
        
        Args:
            pumpfun_token: Token data from Pump.fun scanner
            
        Returns:
            Unified token dict with resolved metadata and state
        """
        token_address = pumpfun_token.get('token_address')
        if not token_address:
            return None
        
        # Ensure token_address is a string (not a dict)
        if isinstance(token_address, dict):
            token_address = token_address.get('pubkey', '')
        
        token_address = str(token_address).strip()
        if not token_address:
            return None
        
        # ====== STEP 1: RESOLVE METADATA ======
        metadata = await self.metadata_resolver.resolve(token_address)
        name = metadata.get('name', 'UNKNOWN') if metadata else 'UNKNOWN'
        symbol = metadata.get('symbol', '???') if metadata else '???'
        decimals = metadata.get('decimals', 0) if metadata else 0
        
        if metadata:
            solana_log(f"[META] ✅ Resolved {token_address[:8]}... | {name} ({symbol}) | decimals={decimals}", "DEBUG")
        else:
            solana_log(f"[META] ⚠️  Cannot resolve {token_address[:8]}... | Skipping...", "DEBUG")
        
        # Get or create state record
        state_record = self.state_machine.create_token(token_address, symbol)
        
        # If metadata resolved, update state machine
        if metadata:
            state_record.update_metadata(
                name=name,
                symbol=symbol,
                decimals=decimals
            )
            solana_log(f"[STATE] {symbol} → METADATA_OK", "DEBUG")
        
        # ====== STEP 2: DETECT RAYDIUM LP ======
        lp_info = None
        if metadata:  # Only check LP if metadata is available
            tx_sig = pumpfun_token.get('tx_signature')
            if tx_sig:
                lp_info = await self.lp_detector.detect_from_transaction(tx_sig, token_address)
                if lp_info:
                    solana_log(f"[LP] ✅ Raydium LP detected | SOL={lp_info.get('liquidity_sol', 0):.2f} | Pool={lp_info.get('pool_address', '???')[:8]}...", "DEBUG")
                    state_record.update_lp(
                        pool_address=lp_info.get('pool_address'),
                        liquidity_sol=lp_info.get('liquidity_sol', 0)
                    )
                    solana_log(f"[STATE] {symbol} → LP_DETECTED", "DEBUG")
        
        # Get additional data from other scanners
        raydium_data = self.raydium.get_liquidity_data(token_address)
        jupiter_data = self.jupiter.get_momentum_data(token_address)
        
        # Build unified event
        unified = {
            # Core identity
            'chain': 'solana',
            'chain_prefix': self.chain_prefix,
            'address': token_address,
            'token_address': token_address,
            'tx_signature': pumpfun_token.get('tx_signature'),
            
            # Pump.fun data
            'source': 'pumpfun',
            'name': name,
            'symbol': symbol,
            'creator_wallet': pumpfun_token.get('creator_wallet', ''),
            'age_seconds': pumpfun_token.get('age_seconds', 0),
            'age_minutes': pumpfun_token.get('age_seconds', 0) / 60,
            'sol_inflow': pumpfun_token.get('sol_inflow', 0),
            'sol_inflow_usd': pumpfun_token.get('sol_inflow_usd', 0),
            'buy_count': pumpfun_token.get('buy_count', 0),
            'buy_velocity': pumpfun_token.get('buy_velocity', 0),
            'unique_buyers': pumpfun_token.get('unique_buyers', 0),
            'creator_sold': pumpfun_token.get('creator_sold', False),
            'metadata_status': 'resolved' if metadata else 'missing',
            
            # Metadata (NEW)
            'metadata': metadata if metadata else {},
            'decimals': decimals,
            
            # Raydium data
            'has_raydium_pool': raydium_data.get('has_raydium_pool', False) or bool(lp_info),
            'liquidity_usd': raydium_data.get('liquidity_usd', 0),
            'liquidity_sol': raydium_data.get('liquidity_sol', 0),
            'liquidity_trend': raydium_data.get('liquidity_trend', 'unknown'),
            'lp_info': lp_info if lp_info else {},
            
            # Jupiter data
            'jupiter_listed': jupiter_data.get('jupiter_listed', False),
            'jupiter_volume_24h': jupiter_data.get('volume_24h_usd', 0),
            'routing_trend': jupiter_data.get('routing_trend', 'unknown'),
            'jupiter_active': jupiter_data.get('is_active', False),
            
            # ====== State Machine ======
            'state': state_record.current_state.value,
            'metadata_resolved': state_record.metadata_resolved,
            'lp_detected': state_record.lp_detected,
            'lp_valid': state_record.lp_valid,
            'token_state_record': state_record.to_dict(),
            
            # Computed fields
            'timestamp': time.time()
        }
        
        # Cache for later updates
        self._token_cache[token_address] = unified
        
        return unified
    
    def _cleanup_cache(self):
        """Remove old cache entries."""
        now = time.time()
        cutoff = now - self._cache_ttl
        
        to_remove = [
            addr for addr, data in self._token_cache.items()
            if data.get('timestamp', 0) < cutoff
        ]
        
        for addr in to_remove:
            del self._token_cache[addr]
    
    def get_token(self, token_address: str) -> Optional[Dict]:
        """Get cached token data."""
        return self._token_cache.get(token_address)
    
    def enrich_token(self, token_address: str) -> Optional[Dict]:
        """
        Get fresh data for a token from all sources.
        
        Args:
            token_address: Solana token mint address
            
        Returns:
            Enriched token dict or None
        """
        if not is_valid_solana_address(token_address):
            return None
        
        # Get from each scanner
        pumpfun_data = self.pumpfun.get_token(token_address)
        raydium_data = self.raydium.get_liquidity_data(token_address)
        jupiter_data = self.jupiter.get_momentum_data(token_address)
        
        if not pumpfun_data:
            # Token not from Pump.fun, create minimal record
            return {
                'chain': 'solana',
                'chain_prefix': self.chain_prefix,
                'address': token_address,
                'token_address': token_address,
                'source': 'unknown',
                **raydium_data,
                **jupiter_data
            }
        
        return self._create_unified_event(pumpfun_data)
    
    def get_sniper_candidates(self, max_age_seconds: int = 120) -> List[Dict]:
        """
        Get tokens eligible for sniper alerts.
        
        Args:
            max_age_seconds: Maximum token age
            
        Returns:
            List of enriched token dicts
        """
        candidates = []
        
        for token in self.pumpfun.get_sniper_candidates(max_age_seconds):
            enriched = self._create_unified_event(token)
            if enriched:
                candidates.append(enriched)
        
        return candidates
    
    def get_chain_prefix(self) -> str:
        """Get chain prefix for logging."""
        return self.chain_prefix
    
    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            "connected": self._connected,
            "cached_tokens": len(self._token_cache),
            "pumpfun": self.pumpfun.get_stats(),
            "raydium": self.raydium.get_stats(),
            "jupiter": self.jupiter.get_stats(),
            "metadata_resolver": self.metadata_resolver.get_cache_stats(),
            "lp_detector": self.lp_detector.get_cache_stats(),
            "state_machine": self.state_machine.get_stats()
        }
    
    async def resolve_token_metadata(self, token_mint: str) -> Optional[Dict]:
        """
        Resolve token metadata via Metaplex.
        
        ASYNC method for resolving metadata.
        Automatically updates state machine.
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Metadata dict or None
        """
        if not is_valid_solana_address(token_mint):
            return None
        
        # Resolve metadata
        metadata = await self.metadata_resolver.resolve(token_mint)
        
        if metadata:
            # Update state machine
            state_record = self.state_machine.set_metadata(
                mint=token_mint,
                name=metadata.name,
                symbol=metadata.symbol,
                decimals=metadata.decimals,
                supply=metadata.supply
            )
            return metadata.to_dict()
        
        return None
    
    async def detect_token_lp(
        self,
        token_mint: str,
        txid: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Detect Raydium LP for a token.
        
        ASYNC method for LP detection.
        Automatically updates state machine.
        
        Args:
            token_mint: Token mint address
            txid: Optional transaction to scan for LP
            
        Returns:
            LP info dict or None if not found/valid
        """
        if not is_valid_solana_address(token_mint):
            return None
        
        # Detect LP
        if txid:
            lp_info = await self.lp_detector.detect_from_transaction(txid, token_mint)
        else:
            lp_info = await self.lp_detector.detect_for_token(token_mint)
        
        if lp_info:
            # Update state machine
            state_record = self.state_machine.set_lp_detected(
                mint=token_mint,
                pool_address=lp_info.pool_address,
                base_liquidity=lp_info.base_liquidity,
                quote_liquidity=lp_info.quote_liquidity,
                quote_liquidity_usd=lp_info.quote_liquidity_usd,
                lp_mint=lp_info.lp_mint
            )
            
            return lp_info.to_dict() if state_record and state_record.lp_valid else None
        
        return None
    
    async def parse_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse a single transaction for token events via instruction parsing.
        
        Fully async, no polling. Detects Pump.fun creation and Raydium LP events.
        
        Args:
            signature: Transaction signature
            
        Returns:
            Token event dict or None
        """
        return await self.raw_parser.parse_transaction(signature)
    
    def update_token_score(self, token_mint: str, score: float) -> Optional[Dict]:
        """
        Update token score and check if ready for sniper.
        
        Args:
            token_mint: Token mint address
            score: New score
            
        Returns:
            Updated state record or None
        """
        state_record = self.state_machine.update_score(token_mint, score)
        
        if state_record:
            return state_record.to_dict()
        
        return None
    
    def can_execute_sniper(self, token_mint: str) -> tuple:
        """
        Check if token is ready for sniper execution.
        
        Args:
            token_mint: Token mint address
            
        Returns:
            (can_execute, reason) tuple
        """
        return self.state_machine.can_execute(token_mint)
    
    def get_armed_tokens(self) -> List[Dict]:
        """
        Get all tokens ready for sniper execution.
        
        Returns:
            List of armed token state records
        """
        return [
            record.to_dict()
            for record in self.state_machine.get_armed_tokens()
        ]
