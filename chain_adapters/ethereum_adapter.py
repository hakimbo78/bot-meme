"""Ethereum chain adapter"""
from .evm_adapter import EVMAdapter

# Import Market Heat Engine
try:
    from intelligence import MarketHeatEngine
    MARKET_HEAT_AVAILABLE = True
except ImportError:
    MARKET_HEAT_AVAILABLE = False
    MarketHeatEngine = None


class EthereumAdapter(EVMAdapter):
    """Adapter for Ethereum mainnet (Uniswap V2/V3)"""
    
    def __init__(self, config):
        super().__init__(config)
        self.chain_name = "ethereum"
        
        # Init heat engine for ETH
        if MARKET_HEAT_AVAILABLE and not hasattr(self, 'heat_engine'):
            self.heat_engine = MarketHeatEngine(self.chain_name)
            print(f"🔥 {self.get_chain_prefix()} Market Heat Engine initialized")
