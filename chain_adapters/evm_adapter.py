"""
EVM-based chain adapter with shared logic for Base, Ethereum, and Blast
"""
import time
import time
import asyncio
import requests
from web3 import Web3
from functools import wraps
from typing import List, Dict, Optional
from .base_adapter import ChainAdapter

# Import V3 modules
try:
    from dex.uniswap_v3 import UniswapV3PoolScanner, V3LiquidityCalculator, V3RiskEngine
    V3_AVAILABLE = True
except ImportError:
    V3_AVAILABLE = False
    UniswapV3PoolScanner = None
    V3LiquidityCalculator = None
    V3RiskEngine = None


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


def retry_with_backoff(max_retries=3, base_delay=1):
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
    """Shared EVM chain adapter for Ethereum-compatible chains"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.w3 = None
        self.factory = None
        self.weth = None
        self.eth_price_usd = config.get('eth_price_usd', 3500)
        self.goplus_api_url = f"https://api.gopluslabs.io/api/v1/token_security/{config.get('goplus_chain_id', '1')}"
        
        # DEX Configuration
        self.enabled_dexes = config.get('dexes', ['uniswap_v2'])
        self.factory_addresses = config.get('factories', {})
        
        # V3 Components
        self.v3_scanner = None
        self.v3_liquidity_calc = None
        self.v3_risk_engine = None
        
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
        self._static_scan_interval = config.get('scan_interval', self._get_scan_interval())
        self.max_block_range = config.get('max_block_range', self._get_max_block_range())
        self.shortlist_limit = config.get('shortlist_limit', self._get_shortlist_limit())
    
    @property
    def scan_interval(self) -> int:
        """Get adaptive scan interval based on market heat"""
        if self.heat_engine:
            return self.heat_engine.get_adaptive_scan_interval()
        else:
            return self._static_scan_interval
    
    def connect(self) -> bool:
        """Connect to EVM chain via RPC"""
        try:
            # Add timeout to HTTP provider
            self.w3 = Web3(Web3.HTTPProvider(self.config['rpc_url'], request_kwargs={'timeout': 10}))
            
            if not self.w3.is_connected():
                print(f"❌ {self.get_chain_prefix()} Could not connect to RPC")
                return False
            
            # Initialize V2 factory (backward compatibility)
            if 'uniswap_v2' in self.enabled_dexes and self.factory_addresses.get('uniswap_v2'):
                self.factory = self.w3.eth.contract(
                    address=self.factory_addresses['uniswap_v2'],
                    abi=FACTORY_ABI
                )
            
            # Initialize V3 components
            if V3_AVAILABLE and 'uniswap_v3' in self.enabled_dexes and self.factory_addresses.get('uniswap_v3'):
                self.v3_scanner = UniswapV3PoolScanner(
                    self.w3,
                    self.factory_addresses['uniswap_v3'],
                    self.config['weth_address'],
                    self.chain_name
                )
                self.v3_liquidity_calc = V3LiquidityCalculator(self.w3, self.eth_price_usd)
                self.v3_risk_engine = V3RiskEngine()
                print(f"🔄 {self.get_chain_prefix()} Uniswap V3 support enabled")
            
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
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_current_block(self):
        """Get current block number with retry logic"""
        return self.w3.eth.block_number
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_block_data(self, block_number):
        """Get block data with retry logic"""
        return self.w3.eth.get_block(block_number)
    
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
    
    def scan_new_pairs(self) -> List[Dict]:
        """Scan for new pairs from all enabled DEXes"""
        new_pairs = []
        
        if not self.w3:
            return new_pairs
        
        try:
            current_block = self._get_current_block()
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Failed to get current block: {e}")
            return new_pairs
        
        if current_block > self.last_block:
            # Scan V2 pairs
            if self.factory and 'uniswap_v2' in self.enabled_dexes:
                v2_pairs = self._scan_v2_pairs(current_block)
                new_pairs.extend(v2_pairs)
            
            # Scan V3 pools
            if self.v3_scanner and 'uniswap_v3' in self.enabled_dexes:
                v3_pools = self.v3_scanner.scan_new_pools()
                new_pairs.extend(v3_pools)
            
            self.last_block = current_block
        
        return new_pairs
    
    def _scan_v2_pairs(self, current_block: int) -> List[Dict]:
        """Scan Uniswap V2 PairCreated events"""
        new_pairs = []
        
        try:
            # NUCLEAR FIX: Always scan minimal range to avoid RPC errors
            from_block = current_block - 10  # Only last 10 blocks
            
            logs = self.factory.events.PairCreated.get_logs(
                from_block=from_block,
                to_block=current_block
            )
            
            # Record factory logs for heat calculation
            if self.heat_engine and logs:
                for _ in logs:
                    self.heat_engine.record_factory_log()
            
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
                        'chain_prefix': self.get_chain_prefix(),
                        'dex_type': 'uniswap_v2'
                    })
                except Exception as e:
                    print(f"⚠️  {self.get_chain_prefix()} Error processing V2 log: {e}")
                    continue
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error fetching V2 pair events: {e}")
        
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
        print(f"🔍 [{self.chain_name.upper()}] CU-optimized scan starting...")

        # CU CHECK: Emergency slow mode if budget exceeded
        if not self._check_cu_budget():
            print(f"🚨 [{self.chain_name.upper()}] CU BUDGET EXCEEDED - Entering slow mode")
            await asyncio.sleep(300)  # 5min cooldown
            return []

        candidates = []

        try:
            # ===== STAGE 1: BLOCK TICK =====
            current_block = await self._run_with_timeout(self._get_current_block)
            if not current_block:
                print(f"❌ [{self.chain_name.upper()}] Failed to get current block")
                return []

            # Check if we need to scan
            if current_block <= self.last_block:
                print(f"⏸️  [{self.chain_name.upper()}] No new blocks (current: {current_block}, last: {self.last_block})")
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
                print(f"📭 [{self.chain_name.upper()}] No factory logs found in blocks {from_block}-{to_block}")
                return []

            self._increment_cu(len(logs) * 5)  # eth_getLogs cost estimate
            print(f"📋 [{self.chain_name.upper()}] Found {len(logs)} factory logs")

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

            print(f"🎯 [{self.chain_name.upper()}] Shortlisted {len(shortlist)}/{len(candidates)} candidates")

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

            print(f"✅ [{self.chain_name.upper()}] Scan complete - {len(final_pairs)} final pairs")
            return final_pairs

        except Exception as e:
            print(f"⚠️  [{self.chain_name.upper()}] CU-optimized scan error: {e}")
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
            print(f"⚠️  [{self.chain_name.upper()}] Error getting token metadata: {e}")
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
            print(f"⚠️  [{self.chain_name.upper()}] Error getting liquidity: {e}")
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
    
    def analyze_token(self, pair_data: Dict) -> Optional[Dict]:
        """
        Enhanced analyze_token with V3 support.
        """
        try:
            token_address = pair_data['token_address']
            pair_address = pair_data['pair_address']
            block_number = pair_data.get('block_number', 0)
            dex_type = pair_data.get('dex_type', 'uniswap_v2')
            
            # Get metadata
            metadata = self.get_token_metadata(token_address)
            if metadata is None:
                metadata = {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 18}
            
            # Get liquidity (V3-aware)
            if dex_type == 'uniswap_v3' and self.v3_liquidity_calc:
                # V3 liquidity calculation
                pool_data = self.v3_liquidity_calc.calculate_pool_liquidity(
                    pair_address,
                    pair_data.get('token0', token_address),
                    pair_data.get('token1', self.weth),
                    self.weth
                )
                liquidity_usd = pool_data.get('liquidity_usd', 0)
                
                # Add V3-specific fields
                v3_risks = {}
                if self.v3_risk_engine:
                    v3_risks = self.v3_risk_engine.assess_pool_risks(pool_data)
            else:
                # V2 liquidity calculation
                liquidity_usd = self.get_liquidity(pair_address, token_address)
                v3_risks = {}
            
            if liquidity_usd is None:
                liquidity_usd = 0
            
            # Get security data
            security = self.check_security(token_address)
            if security is None:
                security = {
                    'renounced': False,
                    'mintable': True,
                    'blacklist': False,
                    'top10_holders_percent': 100
                }
            
            # Calculate age
            import time
            age_minutes = (int(time.time()) - pair_data['timestamp']) / 60
            
            # Build base result
            result = {
                'name': metadata['name'],
                'symbol': metadata['symbol'],
                'address': token_address,
                'pair_address': pair_address,
                'block_number': block_number,
                'age_minutes': age_minutes,
                'liquidity_usd': liquidity_usd,
                'renounced': security.get('renounced', False),
                'mintable': security.get('mintable', False),
                'blacklist': security.get('blacklist', False),
                'top10_holders_percent': security.get('top10_holders_percent', 100),
                'chain': self.chain_name,
                'chain_prefix': self.get_chain_prefix(),
                'dex_type': dex_type,
                
                # V3-specific fields
                'fee_tier': pair_data.get('fee_tier'),
                'v3_risks': v3_risks,
                
                # New validation fields - defaults
                'momentum_confirmed': False,
                'momentum_score': 0,
                'momentum_details': {},
                'fake_pump_suspected': False,
                'mev_pattern_detected': False,
                'manipulation_details': [],
                'dev_activity_flag': 'UNKNOWN',
                'smart_money_involved': False,
                'deployer_address': '',
                'wallet_details': {},
                'market_phase': 'launch' if age_minutes < 15 else ('growth' if age_minutes < 120 else 'mature')
            }
            
            return result
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Error analyzing token: {e}")
            return None
