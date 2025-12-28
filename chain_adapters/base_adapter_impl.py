"""Base chain adapter"""
from .evm_adapter import EVMAdapter


class BaseChainAdapter(EVMAdapter):
    """Adapter for Base network (Uniswap V2)"""
    
    def __init__(self, config):
        super().__init__(config)
        self.chain_name = "BASE"
