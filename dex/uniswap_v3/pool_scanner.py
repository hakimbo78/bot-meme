"""
Uniswap V3 Pool Scanner

Listens to PoolCreated events on Uniswap V3 factory contracts.
Converts V3 pools to standard PairEvent format for compatibility.
"""

import time
from typing import List, Dict, Optional
from web3 import Web3
from web3.contract import Contract

# Uniswap V3 Factory ABI (minimal - just PoolCreated event)
UNISWAP_V3_FACTORY_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "token0", "type": "address"},
            {"indexed": True, "name": "token1", "type": "address"},
            {"indexed": False, "name": "pool", "type": "address"},
            {"indexed": False, "name": "fee", "type": "uint24"},
            {"indexed": False, "name": "tickSpacing", "type": "int24"}
        ],
        "name": "PoolCreated",
        "type": "event"
    }
]

# Uniswap V3 Pool ABI (for liquidity calculation)
UNISWAP_V3_POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class UniswapV3PoolScanner:
    """
    Scans Uniswap V3 factories for new pool creation events.
    Converts V3 pools to standard PairEvent format.
    """

    def __init__(self, web3_provider: Web3, factory_address: str, weth_address: str, chain_name: str):
        self.w3 = web3_provider
        self.factory_address = Web3.to_checksum_address(factory_address)
        self.weth_address = Web3.to_checksum_address(weth_address)
        self.chain_name = chain_name
        self.chain_prefix = f"[{chain_name.upper()}]"

        # Initialize factory contract
        self.factory: Optional[Contract] = None
        if self.w3:
            self.factory = self.w3.eth.contract(
                address=self.factory_address,
                abi=UNISWAP_V3_FACTORY_ABI
            )

        self.last_block = 0
        if self.w3:
            try:
                self.last_block = self.w3.eth.block_number
            except Exception:
                self.last_block = 0

    def connect(self) -> bool:
        """Verify connection to blockchain"""
        if not self.w3 or not self.factory:
            return False
        try:
            # Test connection by getting current block
            self.w3.eth.block_number
            return True
        except Exception:
            return False

    def scan_new_pools(self) -> List[Dict]:
        """
        Scan for new PoolCreated events.
        Returns list of dicts in standard PairEvent format.
        """
        new_pools = []

        if not self.w3 or not self.factory:
            return new_pools

        try:
            current_block = self.w3.eth.block_number
        except Exception as e:
            print(f"⚠️  {self.chain_prefix}[V3] Failed to get current block: {e}")
            return new_pools

        if current_block <= self.last_block:
            return new_pools

        try:
            # Scan last 10 blocks for new pools (same as V2)
            from_block = max(current_block - 10, self.last_block + 1)

            logs = self.factory.events.PoolCreated.get_logs(
                from_block=from_block,
                to_block=current_block
            )

            for log in logs:
                try:
                    token0 = log['args']['token0']
                    token1 = log['args']['token1']
                    pool_address = log['args']['pool']
                    fee_tier = log['args']['fee']  # 500, 3000, 10000
                    tick_spacing = log['args']['tickSpacing']
                    block_number = log['blockNumber']

                    # Identify the meme token (not WETH)
                    token_address = token0 if token0.lower() != self.weth_address.lower() else token1

                    # Get block timestamp
                    block_data = self._get_block_data(block_number)

                    # Convert to standard PairEvent format
                    pair_event = {
                        'token_address': token_address,
                        'pair_address': pool_address,  # V3 pool address
                        'block_number': block_number,
                        'timestamp': block_data['timestamp'],
                        'chain': self.chain_name,
                        'chain_prefix': self.chain_prefix,
                        # V3-specific fields
                        'dex_type': 'uniswap_v3',
                        'fee_tier': fee_tier,
                        'tick_spacing': tick_spacing,
                        'token0': token0,
                        'token1': token1
                    }

                    new_pools.append(pair_event)

                except Exception as e:
                    print(f"⚠️  {self.chain_prefix}[V3] Error processing pool log: {e}")
                    continue

            self.last_block = current_block

        except Exception as e:
            print(f"⚠️  {self.chain_prefix}[V3] Error fetching pool events: {e}")

        return new_pools

    def _get_block_data(self, block_number: int) -> Dict:
        """Get block timestamp"""
        try:
            block = self.w3.eth.get_block(block_number)
            return {
                'timestamp': block['timestamp'],
                'number': block_number
            }
        except Exception as e:
            print(f"⚠️  {self.chain_prefix}[V3] Error getting block data: {e}")
            return {
                'timestamp': int(time.time()),
                'number': block_number
            }