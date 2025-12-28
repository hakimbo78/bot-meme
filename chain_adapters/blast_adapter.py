"""Blast chain adapter"""
from .evm_adapter import EVMAdapter


class BlastAdapter(EVMAdapter):
    """Adapter for Blast network (Uniswap V2 fork)"""
    
    def __init__(self, config):
        super().__init__(config)
        self.chain_name = "BLAST"
