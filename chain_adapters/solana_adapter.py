"""Solana chain adapter with Raydium and Pump.fun monitoring"""
import time
import asyncio
from typing import List, Dict, Optional
from .base_adapter import ChainAdapter

# Solana imports (optional - will gracefully degrade if not installed)
try:
    from solana.rpc.api import Client
    from solana.rpc.commitment import Confirmed
    from solders.pubkey import Pubkey
    from solders.signature import Signature
    import base58
    SOLANA_AVAILABLE = True
except ImportError as e:
    SOLANA_AVAILABLE = False
    # Print what failed to import
    import sys
    print(f"⚠️  Solana import failed: {e}", file=sys.stderr)


class SolanaAdapter(ChainAdapter):
    """Adapter for Solana (Raydium / Pump.fun)"""
    
    def __init__(self, config):
        super().__init__(config)
        self.chain_name = "solana"
        self.client = None
        self.raydium_program = config.get('raydium_program')
        self.pumpfun_program = config.get('pumpfun_program')
        self.last_signature = None
        self.processed_signatures = set()  # Track processed transactions
        
        # Debug: show availability status
        print(f"🔍 {self.get_chain_prefix()} SOLANA_AVAILABLE = {SOLANA_AVAILABLE}")
        
        if not SOLANA_AVAILABLE:
            print(f"❌ {self.get_chain_prefix()} Solana dependencies not available")
    
    def connect(self) -> bool:
        """Connect to Solana RPC"""
        if not SOLANA_AVAILABLE:
            return False
        
        try:
            self.client = Client(self.config['rpc_url'])
            # Test connection by getting slot (block height)
            response = self.client.get_slot()
            if response.value is not None:
                print(f"✅ {self.get_chain_prefix()} Connected! Slot: {response.value}")
                return True
            else:
                print(f"❌ {self.get_chain_prefix()} Connection failed: No response")
                return False
        except Exception as e:
            print(f"❌ {self.get_chain_prefix()} Connection error: {e}")
            return False
    
    def scan_new_pairs(self) -> List[Dict]:
        """
        Scan for new token launches on Solana.
        Monitors Raydium and Pump.fun for new pools/tokens.
        """
        if not self.client:
            return []
        
        new_pairs = []
        
        try:
            # Scan Raydium pools
            raydium_pairs = self._scan_raydium()
            new_pairs.extend(raydium_pairs)
            
            # Scan Pump.fun tokens
            pumpfun_pairs = self._scan_pumpfun()
            new_pairs.extend(pumpfun_pairs)
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Scan error: {e}")
        
        return new_pairs

    async def _run_with_timeout(self, func, *args, timeout=15.0):
        """Run blocking call in thread with timeout"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func, *args),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print(f"⚠️  {self.get_chain_prefix()} RPC Timeout ({timeout}s)")
            return None
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} RPC Error: {e}")
            return None

    async def scan_new_pairs_async(self) -> List[Dict]:
        """
        Async scan for new token launches on Solana.
        Non-blocking with yield points and timeouts.
        """
        if not self.client:
            return []
        
        new_pairs = []
        
        try:
            # Yield to event loop immediately
            await asyncio.sleep(0)
            
            # Scan Raydium pools (Async)
            raydium_pairs = await self._scan_raydium_async()
            new_pairs.extend(raydium_pairs)
            
            # Yield between sources
            await asyncio.sleep(0.1)
            
            # Scan Pump.fun tokens (Async)
            pumpfun_pairs = await self._scan_pumpfun_async()
            new_pairs.extend(pumpfun_pairs)
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Async scan error: {e}")
        
        return new_pairs

    async def _scan_raydium_async(self) -> List[Dict]:
        """Async scan Raydium program"""
        if not self.raydium_program:
            return []
        
        try:
            raydium_pubkey = Pubkey.from_string(self.raydium_program)
            
            # Async RPC call with timeout
            response = await self._run_with_timeout(
                self.client.get_signatures_for_address,
                raydium_pubkey,
                limit=5,
                commitment=Confirmed
            )
            
            if not response or not response.value:
                return []
            
            new_pools = []
            current_time = int(time.time())
            
            # Identify new signatures
            new_sigs = []
            for sig_info in response.value:
                sig_str = str(sig_info.signature)
                if sig_str not in self.processed_signatures:
                    new_sigs.append(sig_str)
                    self.processed_signatures.add(sig_str)
            
            if not new_sigs:
                return []
                
            # Fetch transactions in parallel
            tasks = [
                self._run_with_timeout(
                    self.client.get_transaction,
                    Signature.from_string(sig),
                    max_supported_transaction_version=0
                ) for sig in new_sigs
            ]
            
            tx_responses = await asyncio.gather(*tasks)
            
            new_pools = []
            current_time = int(time.time())
            
            for tx_response in tx_responses:
                if tx_response and tx_response.value:
                    pool_info = self._parse_raydium_transaction(tx_response.value)
                    
                    if pool_info:
                        new_pools.append({
                            'token_address': pool_info.get('token_address', 'unknown'),
                            'pair_address': pool_info.get('pool_address', 'unknown'),
                            'block_number': 0,
                            'timestamp': current_time,
                            'chain': self.chain_name,
                            'chain_prefix': self.get_chain_prefix()
                        })
            
            if len(self.processed_signatures) > 1000:
                self.processed_signatures = set(list(self.processed_signatures)[-500:])
            
            return new_pools
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Raydium async scan error: {e}")
            return []

    async def _scan_pumpfun_async(self) -> List[Dict]:
        """Async scan Pump.fun program"""
        if not self.pumpfun_program:
            return []
        
        try:
            pumpfun_pubkey = Pubkey.from_string(self.pumpfun_program)
            
            response = await self._run_with_timeout(
                self.client.get_signatures_for_address,
                pumpfun_pubkey,
                limit=5,
                commitment=Confirmed
            )
            
            if not response or not response.value:
                return []
            
            new_tokens = []
            current_time = int(time.time())
            
            for sig_info in response.value:
                await asyncio.sleep(0) # Yield
                
                sig_str = str(sig_info.signature)
                
                if sig_str in self.processed_signatures:
                    continue
                
                self.processed_signatures.add(sig_str)
                
                # Fetching TX details might be needed for real parsing, 
                # but following existing logic which just appends placeholder
                new_tokens.append({
                    'token_address': 'placeholder', 
                    'pair_address': 'placeholder',
                    'block_number': 0,
                    'timestamp': current_time,
                    'chain': self.chain_name,
                    'chain_prefix': self.get_chain_prefix()
                })
            
            return new_tokens
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Pump.fun async scan error: {e}")
            return []
        """Scan Raydium program for new liquidity pools"""
        if not self.raydium_program:
            return []
        
        try:
            # Get recent transactions for Raydium program
            raydium_pubkey = Pubkey.from_string(self.raydium_program)
            
            # Get signatures for address
            response = self.client.get_signatures_for_address(
                raydium_pubkey,
                limit=10,
                commitment=Confirmed
            )
            
            if not response.value:
                return []
            
            new_pools = []
            current_time = int(time.time())
            
            for sig_info in response.value:
                sig_str = str(sig_info.signature)
                
                # Skip if already processed
                if sig_str in self.processed_signatures:
                    continue
                
                self.processed_signatures.add(sig_str)
                
                # Get transaction details
                tx_response = self.client.get_transaction(
                    Signature.from_string(sig_str),
                    max_supported_transaction_version=0
                )
                
                if tx_response.value:
                    # Parse transaction for pool initialization
                    # This is simplified - real implementation needs to parse instruction data
                    pool_info = self._parse_raydium_transaction(tx_response.value)
                    
                    if pool_info:
                        new_pools.append({
                            'token_address': pool_info.get('token_address', 'unknown'),
                            'pair_address': pool_info.get('pool_address', 'unknown'),
                            'block_number': 0,  # Solana uses slots, not blocks
                            'timestamp': current_time,
                            'chain': self.chain_name,
                            'chain_prefix': self.get_chain_prefix()
                        })
            
            # Limit processed signatures set size
            if len(self.processed_signatures) > 1000:
                self.processed_signatures = set(list(self.processed_signatures)[-500:])
            
            return new_pools
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Raydium scan error: {e}")
            return []
    
    def _scan_pumpfun(self) -> List[Dict]:
        """Scan Pump.fun program for new token deployments"""
        if not self.pumpfun_program:
            return []
        
        try:
            # Similar logic to Raydium but for Pump.fun
            pumpfun_pubkey = Pubkey.from_string(self.pumpfun_program)
            
            response = self.client.get_signatures_for_address(
                pumpfun_pubkey,
                limit=10,
                commitment=Confirmed
            )
            
            if not response.value:
                return []
            
            new_tokens = []
            current_time = int(time.time())
            
            for sig_info in response.value:
                sig_str = str(sig_info.signature)
                
                if sig_str in self.processed_signatures:
                    continue
                
                self.processed_signatures.add(sig_str)
                
                # Parse for new token creation
                # This is simplified
                new_tokens.append({
                    'token_address': 'placeholder',  # Need to parse from transaction
                    'pair_address': 'placeholder',
                    'block_number': 0,
                    'timestamp': current_time,
                    'chain': self.chain_name,
                    'chain_prefix': self.get_chain_prefix()
                })
            
            return new_tokens
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Pump.fun scan error: {e}")
            return []
    
    def _parse_raydium_transaction(self, transaction) -> Optional[Dict]:
        """Parse Raydium transaction data to extract pool info"""
        try:
            # This is a simplified parser
            # Real implementation needs to decode instruction data properly
            
            # For now, return None to avoid false positives
            # Full implementation would:
            # 1. Check instruction discriminator for "initialize" 
            # 2. Decode pool account addresses
            # 3. Extract token mint addresses
            
            return None
            
        except Exception as e:
            return None
    
    def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """Get Solana token metadata from Metaplex"""
        if not self.client:
            return None
        
        try:
            # Get token account info
            token_pubkey = Pubkey.from_string(token_address)
            account_info = self.client.get_account_info(token_pubkey)
            
            if account_info.value:
                # Parse metadata - simplified version
                # Real implementation would query Metaplex metadata PDA
                return {
                    'name': 'Solana Token',  # Placeholder
                    'symbol': 'SOL-TOKEN',
                    'decimals': 9
                }
            
            return {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 9}
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Metadata error: {e}")
            return {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 9}
    
    def get_liquidity(self, pair_address: str, token_address: str) -> float:
        """Get liquidity from Raydium pool"""
        if not self.client:
            return 0
        
        try:
            # Query pool account and calculate liquidity
            # This is simplified - real implementation needs:
            # 1. Parse pool state from account data
            # 2. Get token reserves
            # 3. Calculate USD value using price oracles
            
            # Return placeholder value
            return 10000  # Placeholder
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Liquidity error: {e}")
            return 0
    
    def check_security(self, token_address: str) -> Dict:
        """Check Solana token security"""
        if not self.client:
            return {
                'renounced': False,
                'mintable': True,
                'blacklist': False,
                'top10_holders_percent': 100
            }
        
        try:
            # Check mint authority
            token_pubkey = Pubkey.from_string(token_address)
            account_info = self.client.get_account_info(token_pubkey)
            
            # Simplified security check
            # Real implementation would:
            # 1. Parse mint account data for mint authority
            # 2. Check freeze authority
            # 3. Query top token holders
            # 4. Calculate distribution
            
            return {
                'renounced': False,  # Check if mint authority is None
                'mintable': True,    # Check freeze authority
                'blacklist': False,
                'top10_holders_percent': 50  # Placeholder
            }
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Security check error: {e}")
            return {
                'renounced': False,
                'mintable': True,
                'blacklist': False,
                'top10_holders_percent': 100
            }
