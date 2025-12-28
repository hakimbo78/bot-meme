"""Ethereum chain adapter"""
from .evm_adapter import EVMAdapter


class EthereumAdapter(EVMAdapter):
    """Adapter for Ethereum mainnet (Uniswap V2/V3)"""
    
    def __init__(self, config):
        super().__init__(config)
        self.chain_name = "ETH"
