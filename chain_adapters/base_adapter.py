"""
Chain adapter base interface for multi-chain support
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class ChainAdapter(ABC):
    """Base interface for all blockchain adapters"""
    
    def __init__(self, config: dict):
        self.config = config
        self.chain_name = ""
        self.last_block = 0
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the blockchain and verify connectivity"""
        pass
    
    @abstractmethod
    def scan_new_pairs(self) -> List[Dict]:
        """
        Scan for new token pairs/launches (Synchronous blocking).
        Returns list of dicts with: token_address, pair_address, block_number, timestamp
        """
        pass

    async def scan_new_pairs_async(self) -> List[Dict]:
        """
        Async version of scan_new_pairs. 
        Default implementation wraps synchronous call in thread to avoid blocking event loop.
        Override this for optimized async implementations.
        """
        import asyncio
        return await asyncio.to_thread(self.scan_new_pairs)
    
    @abstractmethod
    def get_token_metadata(self, token_address: str) -> Optional[Dict]:
        """
        Fetch token name, symbol, decimals.
        Returns: {'name': str, 'symbol': str, 'decimals': int} or None
        """
        pass
    
    @abstractmethod
    def get_liquidity(self, pair_address: str, token_address: str) -> float:
        """
        Get liquidity in USD for the given pair.
        Returns: liquidity in USD (float)
        """
        pass
    
    @abstractmethod
    def check_security(self, token_address: str) -> Dict:
        """
        Check ownership, mintability, blacklist, holder distribution.
        Returns: {'renounced': bool, 'mintable': bool, 'blacklist': bool, 'top10_holders_percent': float}
        """
        pass
    
    def get_chain_prefix(self) -> str:
        """Return chain prefix for alerts"""
        return f"[{self.chain_name.upper()}]"
    
    def analyze_token(self, pair_data: Dict) -> Optional[Dict]:
        """
        Full token analysis combining metadata, liquidity, and security.
        This is a convenience method that chains together the other methods.
        
        Extended to include:
        - Momentum validation fields
        - Transaction pattern analysis
        - Wallet tracking data
        - Market phase classification
        """
        try:
            token_address = pair_data['token_address']
            pair_address = pair_data['pair_address']
            block_number = pair_data.get('block_number', 0)
            
            # Get metadata
            metadata = self.get_token_metadata(token_address)
            if metadata is None:
                metadata = {'name': 'UNKNOWN', 'symbol': '???', 'decimals': 18}
            
            # Get liquidity
            liquidity_usd = self.get_liquidity(pair_address, token_address)
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
                
                # New validation fields - defaults
                # These will be enriched by TokenAnalyzer
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

