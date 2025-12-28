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
    
    def connect(self) -> bool:
        """Connect to EVM chain via RPC"""
        try:
            # Add timeout to HTTP provider
            self.w3 = Web3(Web3.HTTPProvider(self.config['rpc_url'], request_kwargs={'timeout': 10}))
            
            if not self.w3.is_connected():
                print(f"❌ {self.get_chain_prefix()} Could not connect to RPC")
                return False
            
            self.factory = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.config['factory_address']),
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
        Async scan with block slicing (max 5 blocks) to prevent RPC load/blocking.
        """
        new_pairs = []
        
        if not self.w3 or not self.factory:
            return new_pairs
        
        try:
            # 1. Get current block (Async + Timeout)
            current_block = await self._run_with_timeout(self._get_current_block)
            
            if not current_block:
                return new_pairs
            
            # If fast forwarding or startup, scan more blocks to catch up
            if self.last_block == 0:
                self.last_block = max(0, current_block - 100)  # Scan last 100 blocks on startup
            
            # 2. Slice blocks (Max 5 blocks per scan)
            # We want to scan forward from last_block
            start_block = self.last_block + 1
            if start_block > current_block:
                return new_pairs
                
            # Limit range to 10 blocks per scan (more aggressive)
            end_block = min(current_block, start_block + 9) # Inclusive range [start, start+9] = 10 blocks
            
            # Yield to event loop
            await asyncio.sleep(0)
            
            # 3. Get Logs (Async + Timeout)
            # Wrapping the specific get_logs call
            def fetch_logs():
                return self.factory.events.PairCreated.get_logs(
                    from_block=start_block,
                    to_block=end_block
                )
            
            logs = await self._run_with_timeout(fetch_logs) # Uses default timeout (15s)
            
            if logs:
                for log in logs:
                    await asyncio.sleep(0) # Yield per log processing
                    try:
                        token0 = log['args']['token0']
                        token1 = log['args']['token1']
                        pair_address = log['args']['pair']
                        block_number = log['blockNumber']
                        
                        token_address = token0 if token0.lower() != self.weth.lower() else token1
                        
                        # Get timestamp (Optional optimization: batch this or cache)
                        block_data = await self._run_with_timeout(self._get_block_data, block_number)
                        timestamp = block_data['timestamp'] if block_data else int(time.time())
                        
                        new_pairs.append({
                            'token_address': token_address,
                            'pair_address': pair_address,
                            'block_number': block_number,
                            'timestamp': timestamp,
                            'chain': self.chain_name,
                            'chain_prefix': self.get_chain_prefix()
                        })
                    except Exception as e:
                        print(f"⚠️  {self.get_chain_prefix()} Log error: {e}")
                        continue
            
            # Update last block only if successful
            self.last_block = end_block
            
        except Exception as e:
            print(f"⚠️  {self.get_chain_prefix()} Async scan error: {e}")
        
        return new_pairs
    
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
