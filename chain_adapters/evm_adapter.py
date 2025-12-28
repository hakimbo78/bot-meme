"""
EVM-based chain adapter with shared logic for Base, Ethereum, and Blast
CU-OPTIMIZED VERSION - Alchemy CU-first thinking
"""
import time
import asyncio
import requests
from web3 import Web3
from functools import wraps
from typing import List, Dict, Optional
from .base_adapter import ChainAdapter


# Minimal ABIs (reused from existing scanner/analyzer)
FACTORY_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token0", "type": "address"},
            {"indexed": True, "name": "token1", "type": "address"},
            {"indexed": False, "name": "pair", "type": "address"},
            {"indexed": False, "name": "", "type": "uint256"}
        ],
        "name": "PairCreated",
        "type": "event"
    }
]

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}], "type": "function"}
]

PAIR_ABI = [
    {"constant": True, "inputs": [], "name": "getReserves", "outputs": [
        {"name": "reserve0", "type": "uint112"},
        {"name": "reserve1", "type": "uint112"},
        {"name": "blockTimestampLast", "type": "uint32"}
    ], "type": "function"},
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"}
]


def retry_with_backoff(max_retries=1, base_delay=1):  # REDUCED retries for CU savings
    """Decorator to retry functions with exponential backoff on network errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout, requests.exceptions.RequestException,
                        OSError) as e:
                    if attempt == max_retries - 1:
                        print(f"⚠️  Max retries reached for {func.__name__}")
                        return None
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️  Network error in {func.__name__}, retrying in {delay}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


class EVMAdapter(ChainAdapter):
    """Shared EVM chain adapter for Ethereum-compatible chains - CU OPTIMIZED"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.w3 = None
        self.factory = None
        self.weth = None
        self.eth_price_usd = config.get('eth_price_usd', 3500)
        self.goplus_api_url = f"https://api.gopluslabs.io/api/v1/token_security/{config.get('goplus_chain_id', '1')}"
        
        # CU OPTIMIZATION: Separate clients per chain
        self.session = requests.Session()  # HTTP keep-alive
        
        # CU GUARDRAILS
        self.daily_cu_budget = config.get('daily_cu_budget', 50000)  # Base: 50k, ETH: 25k
        self.cu_used_today = 0
        self.cu_reset_time = time.time() + 86400  # Reset daily
        
        # METADATA CACHE - Cache forever as per requirements
        self.metadata_cache = {}
        self.lp_cache = {}  # LP detection cache
        
        # SCANNING CONFIG - Chain-specific from config
        self.scan_interval = config.get('scan_interval', self._get_scan_interval())
        self.max_block_range = config.get('max_block_range', self._get_max_block_range())
        self.shortlist_limit = config.get('shortlist_limit', self._get_shortlist_limit())
    
    def _get_scan_interval(self) -> int:
        """Get chain-specific scan interval for CU optimization"""
        chain_name = self.config.get('chain_name', '').lower()
        if chain_name == 'base':
            return 25  # 20-30s average
        elif chain_name == 'ethereum':
            return 52  # 45-60s average
        else:
            return 30
    
    def _get_max_block_range(self) -> int:
        """Get max block range for eth_getLogs"""
        chain_name = self.config.get('chain_name', '').lower()
        if chain_name == 'base':
            return 2  # 1-2 blocks
        elif chain_name == 'ethereum':
            return 1  # 1 block
        else:
            return 1
    
    def _get_shortlist_limit(self) -> int:
        """Get max candidates per cycle"""
        chain_name = self.config.get('chain_name', '').lower()
        if chain_name == 'base':
            return 3
        elif chain_name == 'ethereum':
            return 1
        else:
            return 2
    
    def _check_cu_budget(self) -> bool:
        """Check if we have CU budget remaining"""
        now = time.time()
        if now > self.cu_reset_time:
            self.cu_used_today = 0
            self.cu_reset_time = now + 86400
        
        return self.cu_used_today < self.daily_cu_budget
    
    def _increment_cu(self, cost: int):
        """Track CU usage"""
        self.cu_used_today += cost
    
    def connect(self) -> bool:
        """Connect to EVM chain via RPC"""
        try:
            # Add timeout to HTTP provider
            self.w3 = Web3(Web3.HTTPProvider(self.config['rpc_url'], request_kwargs={'timeout': 10}))
            
            if not self.w3.is_connected():
                print(f"❌ {self.get_chain_prefix()} Could not connect to RPC")
                return False
            
            self.factory = self.w3.eth.contract(
                address=self.config['factory_address'],
                abi=FACTORY_ABI
            )
            self.weth = Web3.to_checksum_address(self.config['weth_address'])
            
            # Add timeout for block number retrieval
            import time
            start_time = time.time()
            self.last_block = self.w3.eth.block_number
            connection_time = time.time() - start_time
            
            if connection_time > 5:
                print(f"⚠️  {self.get_chain_prefix()} Slow RPC response ({connection_time:.1f}s)")
            
            print(f"✅ {self.get_chain_prefix()} Connected! Block: {self.last_block}")
            return True
        except Exception as e:
            print(f"❌ {self.get_chain_prefix()} Connection error: {e}")
            return False
            
            if connection_time > 5:
                print(f"⚠️  {self.get_chain_prefix()} Slow RPC response ({connection_time:.1f}s)")
            
            print(f"✅ {self.get_chain_prefix()} Connected! Block: {self.last_block}")
            return True
        except Exception as e:
            print(f"❌ {self.get_chain_prefix()} Connection error: {e}")
            return False
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_current_block(self):
        """Get current block number with retry logic"""
        return self.w3.eth.block_number
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_block_data(self, block_number):
        """Get block data with retry logic"""
        return self.w3.eth.get_block(block_number)
    
    def scan_new_pairs(self) -> List[Dict]:
        """Scan for new PairCreated events"""
        new_pairs = []
        
        if not self.w3 or not self.factory:
            return new_pairs
        
        try:
            current_block = self._get_current_block()
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Failed to get current block: {e}")
            return new_pairs
        
        if current_block > self.last_block:
            try:
                # NUCLEAR FIX: Always scan minimal range to avoid RPC errors
                # This sacrifices some scanning completeness but ensures stability
                from_block = current_block - 10  # Only last 10 blocks
                
                logs = self.factory.events.PairCreated.get_logs(
                    from_block=from_block,
                    to_block=current_block
                )
                
                for log in logs:
                    try:
                        token0 = log['args']['token0']
                        token1 = log['args']['token1']
                        pair_address = log['args']['pair']
                        block_number = log['blockNumber']
                        
                        # Identify the meme token (not WETH)
                        token_address = token0 if token0.lower() != self.weth.lower() else token1
                        
                        # Get block timestamp
                        block_data = self._get_block_data(block_number)
                        
                        new_pairs.append({
                            'token_address': token_address,
                            'pair_address': pair_address,
                            'block_number': block_number,
                            'timestamp': block_data['timestamp'],
                            'chain': self.chain_name,
                            'chain_prefix': self.get_chain_prefix()
                        })
                    except Exception as e:
                        print(f"⚠️  {self.get_chain_prefix()} Error processing log: {e}")
                        continue
                
                self.last_block = current_block
            except Exception as e:
                print(f"⚠️  {self.get_chain_prefix()} Error fetching pair events: {e}")
        
        return new_pairs

    async def _run_with_timeout(self, func, *args, timeout=10.0):
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
        CU-OPTIMIZED STAGED SCANNER PIPELINE
        
        Stage 1: Block Tick (cheap)
        Stage 2: Factory Logs (address-filtered, limited range)
        Stage 3: Cheap Heuristics (NO eth_call)
        Stage 4: Shortlist (HARD LIMIT)
        Stage 5: Expensive RPC (STRICT - only for shortlist)
        """
        # CU CHECK: Emergency slow mode if budget exceeded
        if not self._check_cu_budget():
            print(f"🚨 {self.get_chain_prefix()} CU BUDGET EXCEEDED - Entering slow mode")
            await asyncio.sleep(300)  # 5min cooldown
            return []
        
        candidates = []
        
        try:
            # ===== STAGE 1: BLOCK TICK =====
            current_block = await self._run_with_timeout(self._get_current_block)
            if not current_block:
                return []
            
            # Check if we need to scan
            if current_block <= self.last_block:
                return []
            
            self._increment_cu(1)  # eth_blockNumber cost
            
            # ===== STAGE 2: FACTORY LOGS =====
            # Limited block range per chain
            from_block = max(self.last_block + 1, current_block - self.max_block_range)
            to_block = current_block
            
            def fetch_factory_logs():
                return self.factory.events.PairCreated.get_logs(
                    from_block=from_block,
                    to_block=to_block
                )
            
            logs = await self._run_with_timeout(fetch_factory_logs, timeout=5.0)
            if not logs:
                self.last_block = current_block
                return []
            
            self._increment_cu(len(logs) * 5)  # eth_getLogs cost estimate
            
            # ===== STAGE 3: CHEAP HEURISTICS =====
            # Raw log parsing - NO eth_call
            for log in logs:
                try:
                    await asyncio.sleep(0)  # Yield
                    
                    token0 = log['args']['token0'].lower()
                    token1 = log['args']['token1'].lower()
                    pair_addr = log['args']['pair'].lower()
                    block_num = log['blockNumber']
                    
                    # Identify meme token (not WETH)
                    if token0 == self.weth.lower():
                        token_addr = token1
                    elif token1 == self.weth.lower():
                        token_addr = token0
                    else:
                        continue  # Skip non-WETH pairs
                    
                    # Get deploy tx hash from log (raw parsing)
                    tx_hash = log['transactionHash'].hex()
                    
                    # CHEAP HEURISTICS (no RPC calls):
                    # - Skip if both tokens are WETH (already did)
                    # - Check deploy tx value (need raw tx data)
                    
                    # Get raw transaction data (CHEAP - single eth_getTransactionByHash)
                    tx_data = await self._run_with_timeout(
                        lambda: self.w3.eth.get_transaction(tx_hash),
                        timeout=3.0
                    )
                    
                    if not tx_data:
                        continue
                    
                    deploy_value = tx_data['value']  # Wei
                    
                    # Heuristic: deploy tx value > threshold
                    min_deploy_value = 10**16  # 0.01 ETH in wei
                    if deploy_value < min_deploy_value:
                        continue
                    
                    # Heuristic: tx.from not blacklisted (basic check)
                    deployer = tx_data['from'].lower()
                    blacklist = ['0x0000000000000000000000000000000000000000']  # Add more if needed
                    if deployer in blacklist:
                        continue
                    
                    candidates.append({
                        'token_address': token_addr,
                        'pair_address': pair_addr,
                        'block_number': block_num,
                        'deploy_tx_hash': tx_hash,
                        'deploy_value': deploy_value,
                        'deployer': deployer,
                        'chain': self.chain_name,
                        'chain_prefix': self.get_chain_prefix()
                    })
                    
                except Exception as e:
                    continue
            
            # ===== STAGE 4: SHORTLIST =====
            # Sort by deploy value (proxy for seriousness)
            candidates.sort(key=lambda x: x['deploy_value'], reverse=True)
            shortlist = candidates[:self.shortlist_limit]
            
            # ===== STAGE 5: EXPENSIVE RPC =====
            # ONLY for shortlist - get metadata and liquidity
            final_pairs = []
            
            for candidate in shortlist:
                try:
                    await asyncio.sleep(0)  # Yield
                    
                    token_addr = candidate['token_address']
                    
                    # Check metadata cache first
                    if token_addr in self.metadata_cache:
                        metadata = self.metadata_cache[token_addr]
                    else:
                        # EXPENSIVE: eth_call for name, symbol, decimals (ONCE per token)
                        metadata = await self._run_with_timeout(
                            self._get_token_metadata_cached,
                            token_addr,
                            timeout=5.0
                        )
                        if metadata:
                            self.metadata_cache[token_addr] = metadata
                            self._increment_cu(15)  # 3 eth_calls
                    
                    # EXPENSIVE: Get liquidity (eth_call to pair contract)
                    liquidity = await self._run_with_timeout(
                        self._get_liquidity_cached,
                        candidate['pair_address'],
                        token_addr,
                        timeout=5.0
                    )
                    
                    if liquidity is not None:
                        self._increment_cu(10)  # eth_calls for reserves
                    
                    # Build final pair data
                    pair_data = {
                        **candidate,
                        'name': metadata.get('name', 'UNKNOWN') if metadata else 'UNKNOWN',
                        'symbol': metadata.get('symbol', '???') if metadata else '???',
                        'decimals': metadata.get('decimals', 18) if metadata else 18,
                        'liquidity_usd': liquidity or 0,
                        'timestamp': int(time.time())  # Approximate
                    }
                    
                    final_pairs.append(pair_data)
                    
                except Exception as e:
                    continue
            
            # Update last scanned block
            self.last_block = current_block
            
            return final_pairs
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} CU-optimized scan error: {e}")
            return []
    
    def _get_token_metadata_cached(self, token_address: str) -> Optional[Dict]:
        """Get token metadata with caching - called ONCE per token forever"""
        if token_address in self.metadata_cache:
            return self.metadata_cache[token_address]
        
        try:
            token_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            metadata = {'name': name, 'symbol': symbol, 'decimals': decimals}
            self.metadata_cache[token_address] = metadata
            return metadata
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error getting token metadata: {e}")
            # Cache failed metadata too to avoid retries
            self.metadata_cache[token_address] = {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 18}
            return self.metadata_cache[token_address]
    
    def _get_liquidity_cached(self, pair_address: str, token_address: str) -> Optional[float]:
        """Get liquidity with LP cache - cache LP detection forever"""
        cache_key = f"{pair_address}:{token_address}"
        if cache_key in self.lp_cache:
            return self.lp_cache[cache_key]
        
        try:
            pair_address = Web3.to_checksum_address(pair_address)
            pair_contract = self.w3.eth.contract(address=pair_address, abi=PAIR_ABI)
            
            token0 = pair_contract.functions.token0().call()
            reserves = pair_contract.functions.getReserves().call()
            
            # Determine which reserve is WETH
            if token0.lower() == self.weth.lower():
                weth_reserve = reserves[0]
            else:
                weth_reserve = reserves[1]
            
            # Convert WETH to USD (WETH has 18 decimals)
            liquidity_usd = (weth_reserve / 1e18) * self.eth_price_usd
            self.lp_cache[cache_key] = liquidity_usd
            return liquidity_usd
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error getting liquidity: {e}")
            self.lp_cache[cache_key] = 0
            return 0
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """Get token name, symbol, decimals"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            return {'name': name, 'symbol': symbol, 'decimals': decimals}
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error getting token metadata: {e}")
            return {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 18}
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def get_liquidity(self, pair_address: str, token_address: str) -> float:
        """Calculate liquidity in USD from pair reserves"""
        try:
            pair_address = Web3.to_checksum_address(pair_address)
            pair_contract = self.w3.eth.contract(address=pair_address, abi=PAIR_ABI)
            
            token0 = pair_contract.functions.token0().call()
            reserves = pair_contract.functions.getReserves().call()
            
            # Determine which reserve is WETH
            if token0.lower() == self.weth.lower():
                weth_reserve = reserves[0]
            else:
                weth_reserve = reserves[1]
            
            # Convert WETH to USD (WETH has 18 decimals)
            liquidity_usd = (weth_reserve / 1e18) * self.eth_price_usd
            return liquidity_usd
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error getting liquidity: {e}")
            return 0
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _check_renounced(self, token_address: str) -> bool:
        """Check if ownership is renounced"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            owner = token_contract.functions.owner().call()
            
            zero_address = "0x0000000000000000000000000000000000000000"
            dead_address = "0x000000000000000000000000000000000000dEaD"
            
            return owner.lower() in [zero_address.lower(), dead_address.lower()]
        except:
            return False
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _get_goplus_data(self, token_address: str) -> Optional[Dict]:
        """Fetch security data from GoPlus API"""
        try:
            url = f"{self.goplus_api_url}?contract_addresses={token_address}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'result' in data and token_address.lower() in data['result']:
                return data['result'][token_address.lower()]
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} GoPlus API error: {e}")
        
        return None
    
    def check_security(self, token_address: str) -> Dict:
        """Check ownership, mintability, blacklist, holder distribution"""
        renounced = self._check_renounced(token_address)
        
        # Get GoPlus data
        goplus_data = self._get_goplus_data(token_address)
        
        if goplus_data:
            is_mintable = goplus_data.get('is_mintable', '0') == '1'
            is_blacklisted = goplus_data.get('is_blacklisted', '0') == '1'
            
            # Calculate top 10 holder percentage
            holders = goplus_data.get('holders', [])
            if holders and len(holders) >= 10:
                top10_percent = sum(float(h.get('percent', 0)) for h in holders[:10])
            else:
                top10_percent = 100
        else:
            # Default to risky values if API fails
            is_mintable = True
            is_blacklisted = False
            top10_percent = 100
        
        return {
            'renounced': renounced,
            'mintable': is_mintable,
            'blacklist': is_blacklisted,
            'top10_holders_percent': top10_percent
        }
