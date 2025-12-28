"""
Chain adapter factory and exports
"""
from .base_adapter import ChainAdapter
from .evm_adapter import EVMAdapter
from .base_adapter_impl import BaseChainAdapter
from .ethereum_adapter import EthereumAdapter
from .blast_adapter import BlastAdapter
from .solana_adapter import SolanaAdapter


def get_adapter_for_chain(chain_name: str, config: dict) -> ChainAdapter:
    """
    Factory function to get the appropriate adapter for a chain.
    
    Args:
        chain_name: Name of the chain ('base', 'ethereum', 'blast', 'solana')
        config: Chain configuration dict
    
    Returns:
        ChainAdapter instance or None
    """
    adapters = {
        'base': BaseChainAdapter,
        'ethereum': EthereumAdapter,
        'blast': BlastAdapter,
        'solana': SolanaAdapter
    }
    
    adapter_class = adapters.get(chain_name.lower())
    if adapter_class:
        return adapter_class(config)
    
    print(f"❌ Unknown chain: {chain_name}")
    return None


__all__ = [
    'ChainAdapter',
    'EVMAdapter',
    'BaseChainAdapter',
    'EthereumAdapter',
    'BlastAdapter',
    'SolanaAdapter',
    'get_adapter_for_chain'
]
