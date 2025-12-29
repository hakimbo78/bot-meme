"""
Raw JSON-RPC Solana Parser - Sniper-Grade Transaction Parser

Implements fully RAW JSON-RPC based parsing for Pump.fun + Raydium events.
No SDK abstractions, direct RPC calls with deterministic parsing.

KEY FEATURES:
- Raw getTransaction JSON-RPC calls
- Instruction flattening from message + innerInstructions
- Hardcoded program ID filtering
- Metadata-less safe mode
- Deterministic state machine transitions

CRITICAL: READ-ONLY - No execution, no wallets
"""
import asyncio
import json
import time
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .solana_utils import (
    solana_log,
    parse_lamports_to_sol,
    sol_to_usd,
    PUMPFUN_PROGRAM_ID,
    RAYDIUM_AMM_PROGRAM_ID,
    TOKEN_PROGRAM_ID
)
from .token_state import TokenStateMachine, TokenState, TokenStateRecord
from .token_state import TokenStateMachine, TokenState


# =============================================================================
# HARDCODED PROGRAM IDS (NO DYNAMIC RESOLUTION)
# =============================================================================

PROGRAM_IDS = {
    'pumpfun': PUMPFUN_PROGRAM_ID,
    'raydium_amm': RAYDIUM_AMM_PROGRAM_ID,
    'spl_token': TOKEN_PROGRAM_ID
}


# =============================================================================
# RAW TRANSACTION FETCHER
# =============================================================================

@dataclass
class RawTransactionResponse:
    """Raw transaction response from JSON-RPC."""
    transaction: Dict[str, Any]
    meta: Optional[Dict[str, Any]]
    slot: int
    block_time: Optional[int]


class RawSolanaFetcher:
    """
    Raw JSON-RPC transaction fetcher.

    Uses direct POST calls to Helius RPC with proper params.
    """

    def __init__(self, rpc_url: str, timeout: float = 10.0):
        self.rpc_url = rpc_url
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_transaction(self, signature: str) -> Optional[RawTransactionResponse]:
        """
        Fetch transaction using raw JSON-RPC getTransaction.

        Args:
            signature: Transaction signature

        Returns:
            RawTransactionResponse or None if failed/null
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }

        try:
            async with self.session.post(
                self.rpc_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status != 200:
                    solana_log(f"RPC error {response.status} for {signature[:8]}", "ERROR")
                    return None

                data = await response.json()
                result = data.get('result')

                if result is None:
                    solana_log(f"[SOLANA][RAW] fetched tx {signature[:8]}... result=null (skip)", "DEBUG")
                    return None

                # Parse response
                tx_data = result.get('transaction', {})
                meta = result.get('meta')
                slot = result.get('slot', 0)
                block_time = result.get('blockTime')

                solana_log(f"[SOLANA][RAW] fetched tx {signature[:8]}... OK", "DEBUG")

                return RawTransactionResponse(
                    transaction=tx_data,
                    meta=meta,
                    slot=slot,
                    block_time=block_time
                )

        except asyncio.TimeoutError:
            solana_log(f"[SOLANA][RAW] timeout fetching {signature[:8]}", "DEBUG")
            return None
        except Exception as e:
            solana_log(f"[SOLANA][RAW] error fetching {signature[:8]}: {e}", "ERROR")
            return None


# =============================================================================
# INSTRUCTION FLATTENING
# =============================================================================

@dataclass
class FlatInstruction:
    """Flattened instruction with all context."""
    program_id: str
    accounts: List[str]
    data: Any
    instruction_type: Optional[str] = None
    parsed: Optional[Dict] = None


class InstructionFlattener:
    """
    Flattens instructions from transaction.message.instructions + meta.innerInstructions.

    Critical for Pump.fun and Raydium parsing.
    """

    @staticmethod
    def flatten_instructions(tx_response: RawTransactionResponse) -> List[FlatInstruction]:
        """
        Extract and flatten all instructions from transaction.

        Args:
            tx_response: Raw transaction response

        Returns:
            List of flattened instructions
        """
        instructions = []

        # Get account keys for resolving indices
        message = tx_response.transaction.get('message', {})
        account_keys = message.get('accountKeys', [])
        
        solana_log(f"[SOLANA][RAW] message keys: {list(message.keys())}", "DEBUG")
        solana_log(f"[SOLANA][RAW] account keys count: {len(account_keys)}", "DEBUG")
        
        # Check if account keys are in the right format
        if account_keys and isinstance(account_keys[0], dict):
            # Handle new format where accountKeys is array of objects
            account_keys = [acc.get('pubkey', '') for acc in account_keys]
            solana_log(f"[SOLANA][RAW] converted account keys to strings: {len(account_keys)}", "DEBUG")

        # 1. Top-level instructions
        top_level = message.get('instructions', [])
        solana_log(f"[SOLANA][RAW] top-level instructions: {len(top_level)}", "DEBUG")
        
        # Debug first instruction if exists
        if top_level:
            first_instr = top_level[0]
            solana_log(f"[SOLANA][RAW] first instruction keys: {list(first_instr.keys())}", "DEBUG")
            if 'programIdIndex' in first_instr:
                solana_log(f"[SOLANA][RAW] programIdIndex: {first_instr['programIdIndex']}", "DEBUG")
        
        for instr in top_level:
            flat = InstructionFlattener._parse_instruction(instr, account_keys)
            if flat:
                instructions.append(flat)

        # 2. Inner instructions (CRITICAL for Pump.fun + Raydium)
        if tx_response.meta:
            inner_instructions = tx_response.meta.get('innerInstructions', [])
            solana_log(f"[SOLANA][RAW] inner instruction groups: {len(inner_instructions)}", "DEBUG")
            for inner_group in inner_instructions:
                inner_instrs = inner_group.get('instructions', [])
                solana_log(f"[SOLANA][RAW] inner instructions in group: {len(inner_instrs)}", "DEBUG")
                for instr in inner_instrs:
                    flat = InstructionFlattener._parse_instruction(instr, account_keys)
                    if flat:
                        instructions.append(flat)

        solana_log(f"[SOLANA][RAW] total instructions: {len(instructions)}", "DEBUG")
        return instructions

    @staticmethod
    def _parse_instruction(instr: Dict, account_keys: List[str]) -> Optional[FlatInstruction]:
        """Parse single instruction into FlatInstruction."""
        try:
            # Debug: log instruction structure
            solana_log(f"[SOLANA][RAW] parsing instruction: keys={list(instr.keys())}", "DEBUG")
            
            # Handle both old and new instruction formats
            program_id = None
            
            # Format 1: New format with direct programId
            if 'programId' in instr:
                program_id = instr['programId']
                solana_log(f"[SOLANA][RAW] using direct programId: {program_id[:8]}...", "DEBUG")
            # Format 2: Old format with programIdIndex
            elif 'programIdIndex' in instr:
                program_id_index = instr.get('programIdIndex')
                if program_id_index is None:
                    solana_log(f"[SOLANA][RAW] no programIdIndex in instruction", "DEBUG")
                    return None
                    
                if program_id_index >= len(account_keys):
                    solana_log(f"[SOLANA][RAW] programIdIndex {program_id_index} >= account_keys {len(account_keys)}", "DEBUG")
                    return None

                program_id = account_keys[program_id_index]
                solana_log(f"[SOLANA][RAW] resolved programId from index: {program_id[:8]}...", "DEBUG")
            else:
                solana_log(f"[SOLANA][RAW] no programId or programIdIndex in instruction", "DEBUG")
                return None

            # Resolve accounts
            accounts = []
            instr_accounts = instr.get('accounts', [])
            solana_log(f"[SOLANA][RAW] instruction accounts: {len(instr_accounts)}", "DEBUG")
            
            for acc_idx in instr_accounts:
                # Handle both formats:
                # 1. Integer indices (old format or non-versioned tx)
                # 2. Already-resolved string addresses (versioned tx with lookup tables)
                if isinstance(acc_idx, int):
                    # Integer index - resolve from account_keys
                    if acc_idx < len(account_keys):
                        accounts.append(account_keys[acc_idx])
                    else:
                        solana_log(f"[SOLANA][RAW] account index {acc_idx} out of range (max: {len(account_keys)-1})", "DEBUG")
                elif isinstance(acc_idx, str):
                    # Already resolved address (versioned tx)
                    accounts.append(acc_idx)
                else:
                    solana_log(f"[SOLANA][RAW] unknown account format: {type(acc_idx)}", "DEBUG")

            # Get data and parsed info
            data = instr.get('data', '')
            parsed = instr.get('parsed')

            # Extract instruction type if available
            instruction_type = None
            if parsed and isinstance(parsed, dict):
                instruction_type = parsed.get('type')
                solana_log(f"[SOLANA][RAW] instruction type: {instruction_type}", "DEBUG")

            flat = FlatInstruction(
                program_id=program_id,
                accounts=accounts,
                data=data,
                instruction_type=instruction_type,
                parsed=parsed
            )
            
            solana_log(f"[SOLANA][RAW] ✓ parsed instruction: {program_id[:8]}... ({instruction_type})", "DEBUG")
            return flat

        except Exception as e:
            solana_log(f"[SOLANA][RAW] Error parsing instruction: {e}", "ERROR")
            return None


# =============================================================================
# PROGRAM ID FILTERING
# =============================================================================

class ProgramFilter:
    """
    Hardcoded program ID filtering.

    Only processes instructions from known programs.
    """

    @staticmethod
    def filter_instructions(instructions: List[FlatInstruction]) -> List[FlatInstruction]:
        """
        Filter instructions to only include known programs.

        Args:
            instructions: All flattened instructions

        Returns:
            Filtered instructions from known programs
        """
        known_programs = set(PROGRAM_IDS.values())
        filtered = []

        solana_log(f"[SOLANA][RAW] filtering {len(instructions)} instructions", "DEBUG")
        
        for instr in instructions:
            if instr.program_id in known_programs:
                filtered.append(instr)
                solana_log(f"[SOLANA][RAW] ✓ kept {instr.program_id[:8]}... ({instr.instruction_type})", "DEBUG")
            else:
                solana_log(f"[SOLANA][RAW] ✗ filtered {instr.program_id[:8]}...", "DEBUG")

        solana_log(f"[SOLANA][RAW] filtered to {len(filtered)} known program instructions", "DEBUG")
        return filtered


# =============================================================================
# PUMP.FUN CREATE DETECTOR
# =============================================================================

class PumpfunCreateDetector:
    """
    Detects Pump.fun token creation events.

    Does NOT require Metaplex metadata.
    """

    @staticmethod
    def detect_creation(instructions: List[FlatInstruction]) -> Optional[Dict]:
        """
        Detect token creation from Pump.fun instructions.

        Args:
            instructions: Filtered instructions

        Returns:
            Token creation info or None
        """
        for instr in instructions:
            if instr.program_id == PROGRAM_IDS['pumpfun']:
                solana_log(f"[SOLANA][PUMP] found Pump.fun instruction: {instr.instruction_type}", "DEBUG")
                
                # Check for various Pump.fun instructions that indicate token creation
                if instr.instruction_type in ['initializeMint', 'create', 'initializeMint2']:
                    # Extract from parsed data
                    parsed = instr.parsed
                    if parsed and isinstance(parsed, dict):
                        info = parsed.get('info', {})

                        mint = info.get('mint')
                        mint_authority = info.get('mintAuthority') 
                        creator = info.get('creator')

                        if mint:
                            solana_log(f"[SOLANA][PUMP] new token detected: {mint[:8]}...", "INFO")

                            return {
                                'token_address': mint,
                                'creator_wallet': creator or mint_authority or '',
                                'source': 'pumpfun',
                                'name': 'UNKNOWN',  # Will be filled by metadata resolver if available
                                'symbol': '???',
                                'creation_timestamp': time.time(),
                                'age_seconds': 0,
                                'sol_inflow': 0.0,
                                'buy_count': 0,
                                'unique_buyers': 0,
                                'creator_sold': False,
                                'metadata_status': 'missing'  # Will be updated if metadata found
                            }
                
                # Also check for other Pump.fun instructions that might indicate creation
                elif instr.instruction_type and 'mint' in instr.instruction_type.lower():
                    solana_log(f"[SOLANA][PUMP] potential mint instruction: {instr.instruction_type}", "DEBUG")

        return None


# =============================================================================
# RAYDIUM LP DETECTOR
# =============================================================================

class RaydiumLPDetector:
    """
    Detects Raydium AMM v4 LP creation events via instruction parsing.

    Extracts base mint from instruction.accounts[8] for Pump.fun token matching.
    """

    @staticmethod
    def detect_lp_creation(instructions: List[FlatInstruction]) -> Optional[Dict]:
        """
        Detect LP creation from Raydium AMM v4 instructions.

        For initialize2 instruction (pool creation):
        - accounts[12]: amm_coin_mint (one token)
        - accounts[13]: amm_pc_mint (other token, usually the new token)

        We want the token that is likely the new Pump.fun token.

        Args:
            instructions: Filtered instructions

        Returns:
            LP creation info or None
        """
        for instr in instructions:
            if instr.program_id == PROGRAM_IDS['raydium_amm']:
                # Raydium AMM v4 initialize2 instruction for pool creation
                if instr.instruction_type == 'initialize2' or len(instr.accounts) >= 14:
                    # Extract both mints
                    if len(instr.accounts) >= 14:
                        coin_mint = instr.accounts[12]  # amm_coin_mint
                        pc_mint = instr.accounts[13]    # amm_pc_mint (usually the new token)
                        
                        # Determine which one is likely the new token
                        # Usually pc_mint is the token being listed (new Pump.fun token)
                        base_mint = pc_mint
                        
                        # Validate it's a valid mint address
                        if base_mint and len(base_mint) == 44:  # Solana addresses are 44 chars base58
                            solana_log(f"[SOLANA][RAYDIUM][LP] detected pool creation for token: {base_mint[:8]}...", "INFO")
                            solana_log(f"[SOLANA][RAYDIUM][LP] coin_mint: {coin_mint[:8]}, pc_mint: {pc_mint[:8]}", "DEBUG")

                            return {
                                'base_mint': base_mint,
                                'coin_mint': coin_mint,
                                'pc_mint': pc_mint,
                                'lp_event': 'RAYDIUM_LP_CREATED',
                                'program_id': instr.program_id,
                                'instruction_accounts': len(instr.accounts),
                                'detection_method': 'initialize2_parsing'
                            }

        return None


# =============================================================================
# METADATA-LESS SAFE MODE
# =============================================================================

class MetadataLessScorer:
    """
    Handles scoring for tokens without metadata.

    Assigns base score and risk flags.
    """

    @staticmethod
    def score_without_metadata(token_data: Dict) -> Dict:
        """
        Score token without metadata.

        Args:
            token_data: Token data dict

        Returns:
            Updated token data with score and flags
        """
        # Base score for metadata-less tokens
        base_score = 30

        # Add risk flag
        risk_flags = token_data.get('risk_flags', [])
        risk_flags.append('NO_METADATA')

        token_data.update({
            'score': base_score,
            'risk_flags': risk_flags,
            'metadata_resolved': False
        })

        return token_data


# =============================================================================
# MAIN RAW PARSER
# =============================================================================

class RawSolanaParser:
    """
    Main raw JSON-RPC based Solana parser.

    Orchestrates all components for sniper-grade parsing.
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.state_machine = TokenStateMachine()
        self._last_health_log = 0

    async def parse_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse single transaction for token events.

        Args:
            signature: Transaction signature

        Returns:
            Token event dict or None
        """
        async with RawSolanaFetcher(self.rpc_url) as fetcher:
            # STEP 1: RAW TRANSACTION FETCH
            tx_response = await fetcher.fetch_transaction(signature)
            if not tx_response:
                return None

            # STEP 2: META VALIDATION FIX
            meta_ok = tx_response.meta is not None and tx_response.meta.get('err') is None
            solana_log(f"[SOLANA][RAW] meta ok: {meta_ok}", "DEBUG")

            if not meta_ok:
                # Skip silently if meta validation fails
                return None

            # STEP 3: INSTRUCTION FLATTENING
            all_instructions = InstructionFlattener.flatten_instructions(tx_response)

            # STEP 4: PROGRAM ID FILTERING
            filtered_instructions = ProgramFilter.filter_instructions(all_instructions)

            # STEP 5: PUMP.FUN CREATE DETECTOR
            token_creation = PumpfunCreateDetector.detect_creation(filtered_instructions)
            if token_creation:
                # Create state record
                state_record = self.state_machine.create_token(
                    token_creation['token_address'],
                    token_creation['symbol']
                )

                # STEP 6: METADATA-LESS SAFE MODE
                if not meta_ok or not tx_response.meta.get('logMessages'):
                    # Metadata missing, use safe mode
                    token_creation = MetadataLessScorer.score_without_metadata(token_creation)
                    state_record.update_metadata(name='UNKNOWN', symbol='???', decimals=9)
                    solana_log(f"[SOLANA][STATE] {token_creation['symbol']} → DETECTED (metadata-less)", "DEBUG")
                else:
                    # Metadata available, would resolve here
                    state_record.update_metadata(name=token_creation['name'], symbol=token_creation['symbol'], decimals=9)
                    solana_log(f"[SOLANA][STATE] {token_creation['symbol']} → DETECTED", "DEBUG")

                return token_creation

            # STEP 7: RAYDIUM LP DETECTOR
            lp_creation = RaydiumLPDetector.detect_lp_creation(filtered_instructions)
            if lp_creation:
                base_mint = lp_creation['base_mint']

                # Check if we have this token in state machine (tracked Pump.fun mint)
                if self.state_machine.has_token(base_mint):
                    state_record = self.state_machine.get_token(base_mint)
                    if state_record:
                        # STEP 8: AUTO SCORE BOOST CALCULATION
                        boost_score = self._calculate_lp_score_boost(state_record)
                        new_score = min(state_record.score + boost_score, 100.0)

                        # Update score
                        state_record.last_score = state_record.score
                        state_record.score = new_score
                        state_record.lp_detected = True
                        state_record.lp_info.update(lp_creation)

                        solana_log(f"[SOLANA][SCORE] LP boost: +{boost_score} → {new_score}", "INFO")

                        # STEP 9: STATE TRANSITION
                        old_state = state_record.current_state
                        if old_state in [TokenState.DETECTED, TokenState.METADATA_PENDING, TokenState.METADATA_OK]:
                            state_record.current_state = TokenState.LP_DETECTED
                            solana_log(f"[SOLANA][STATE] {base_mint[:8]} → LP_DETECTED", "DEBUG")

                            # Check for SNIPER_ARMED transition
                            if new_score >= 85:
                                state_record.current_state = TokenState.SNIPER_ARMED
                                solana_log(f"[SOLANA][SNIPER] ARMED: {base_mint[:8]} (score: {new_score})", "INFO")

                        # Emit event
                        solana_log(f"[SOLANA][RAYDIUM][LP] {base_mint[:8]}", "INFO")

                return lp_creation

        # STEP 9: TIMEOUT & HANG FIX - Add watchdog logging
        now = time.time()
        if now - self._last_health_log > 30:  # Every 30 seconds
            solana_log("[SOLANA][HEALTH] scanner alive", "DEBUG")
            self._last_health_log = now

        return None

    def _calculate_lp_score_boost(self, state_record: TokenStateRecord) -> float:
        """
        Calculate score boost for LP detection.

        Scoring rules:
        - +30 base LP detection
        - +15 if LP within 5 minutes of token creation
        - +10 if buy velocity > 10
        - +10 if smart wallet detected

        Args:
            state_record: Token state record

        Returns:
            Score boost amount
        """
        boost = 30.0  # Base LP detection

        # +15 if LP within 5 minutes of token creation
        lp_age_minutes = (time.time() - state_record.created_at) / 60.0
        if lp_age_minutes <= 5.0:
            boost += 15.0
            solana_log(f"[SOLANA][SCORE] +15 early LP bonus ({lp_age_minutes:.1f}min)", "DEBUG")

        # +10 if buy velocity > 10
        if state_record.buy_velocity > 10.0:
            boost += 10.0
            solana_log(f"[SOLANA][SCORE] +10 velocity bonus ({state_record.buy_velocity:.1f})", "DEBUG")

        # +10 if smart wallet detected
        if state_record.smart_wallet_detected:
            boost += 10.0
            solana_log("[SOLANA][SCORE] +10 smart wallet bonus", "DEBUG")

        return boost


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

async def parse_single_transaction(rpc_url: str, signature: str) -> Optional[Dict]:
    """
    Convenience function to parse a single transaction.

    Args:
        rpc_url: RPC endpoint URL
        signature: Transaction signature

    Returns:
        Token event dict or None
    """
    parser = RawSolanaParser(rpc_url)
    return await parser.parse_transaction(signature)


def get_program_ids() -> Dict[str, str]:
    """Get hardcoded program IDs."""
    return PROGRAM_IDS.copy()