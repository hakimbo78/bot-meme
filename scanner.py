import time
from web3 import Web3
from datetime import datetime
from functools import wraps
import requests.exceptions

# Uniswap V2 Factory ABI (minimal - just PairCreated event)
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

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator to retry functions with exponential backoff on network errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, requests.exceptions.ConnectionError, 
                        requests.exceptions.Timeout, OSError) as e:
                    if attempt == max_retries - 1:
                        print(f"❌ Max retries reached for {func.__name__}: {e}")
                        raise
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️  Network error in {func.__name__}, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class BaseScanner:
    def __init__(self, web3_provider, factory_address):
        self.w3 = web3_provider
        
        # Only initialize contract if we have a valid provider (live mode)
        if self.w3 is not None:
            self.factory = self.w3.eth.contract(address=factory_address, abi=FACTORY_ABI)
            self.last_block = self.w3.eth.block_number
            self.weth = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
        else:
            # Simulation mode
            self.factory = None
            self.last_block = 0
            self.weth = None
        
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_current_block(self):
        """Get current block number with retry logic"""
        return self.w3.eth.block_number
    
    @retry_with_backoff(max_retries=3, base_delay=2)
    def _get_block_data(self, block_number):
        """Get block data with retry logic"""
        return self.w3.eth.get_block(block_number)
    
    def scan_new_pairs(self):
        """Poll for new PairCreated events and return token addresses"""
        new_pairs = []
        
        try:
            current_block = self._get_current_block()
        except Exception as e:
            print(f"⚠️  Failed to get current block: {e}")
            return new_pairs  # Return empty list, don't crash
        
        if current_block > self.last_block:
            try:
                # Get logs for PairCreated events (use snake_case for web3.py v6+)
                logs = self.factory.events.PairCreated.get_logs(
                    from_block=self.last_block + 1,
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
                        
                        # Get block timestamp with retry
                        block_data = self._get_block_data(block_number)
                        
                        new_pairs.append({
                            'token_address': token_address,
                            'pair_address': pair_address,
                            'block_number': block_number,
                            'timestamp': block_data['timestamp']
                        })
                    except Exception as e:
                        print(f"⚠️  Error processing log: {e}")
                        continue  # Skip this pair, process others
                
                self.last_block = current_block
            except Exception as e:
                print(f"⚠️  Error fetching pair events: {e}")
                # Don't update last_block, will retry next iteration
        
        return new_pairs

    def get_mock_data(self):
        return [
            {
                "name": "Based Pepe",
                "symbol": "BPEPE",
                "address": "0x123...abc",
                "age_minutes": 5,
                "liquidity_usd": 25000,
                "renounced": True,
                "mintable": False,
                "blacklist": False,
                "top10_holders_percent": 35
            },
            {
                "name": "Rug Pull Inu",
                "symbol": "RUG",
                "address": "0x456...def",
                "age_minutes": 12,
                "liquidity_usd": 5000,
                "renounced": False,
                "mintable": True,
                "blacklist": False,
                "top10_holders_percent": 80
            },
            {
                "name": "SafeMoon Base",
                "symbol": "SMB",
                "address": "0x789...ghi",
                "age_minutes": 2,
                "liquidity_usd": 55000,
                "renounced": True,
                "mintable": False,
                "blacklist": False,
                "top10_holders_percent": 25
            }
        ]
