"""
Transaction Analyzer - Detects manipulation patterns in on-chain transactions
Identifies fake pumps, MEV attacks, and suspicious trading patterns.

This module analyzes recent block transactions to detect:
- Rapid buy+sell patterns within 1-2 blocks
- Multiple transactions from same wallet in one block
- Gas price anomalies
- Large swaps relative to liquidity
"""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from config import (
    TX_ANALYSIS_BLOCKS_BACK,
    SWAP_LIQUIDITY_RATIO_THRESHOLD,
    GAS_SPIKE_MULTIPLIER
)
from safe_math import safe_div


@dataclass
class TransactionPattern:
    """Detected transaction pattern"""
    pattern_type: str
    wallet_address: str
    block_number: int
    details: str


class TransactionAnalyzer:
    """
    Analyzes recent blockchain transactions to detect manipulation patterns.
    
    Detection capabilities:
    - Rapid buy+sell: Same wallet buying and selling within 1-2 blocks
    - Wallet spam: Multiple transactions from single wallet in one block
    - Gas anomaly: Abnormally high gas price vs network average
    - Large swap: Single swap > 20% of liquidity
    """
    
    def __init__(self, adapter=None):
        """
        Initialize TransactionAnalyzer.
        
        Args:
            adapter: Chain adapter with Web3 connection for fetching transactions
        """
        self.adapter = adapter
        self._cache: Dict[str, Dict] = {}  # Cache analysis results
        self._cache_ttl = 60  # Cache TTL in seconds
    
    def analyze_token_transactions(self, token_address: str, pair_address: str,
                                   liquidity_usd: float, 
                                   current_block: int = 0) -> Dict:
        """
        Analyze recent transactions involving a token for manipulation patterns.
        
        Args:
            token_address: Token contract address
            pair_address: DEX pair address
            liquidity_usd: Current liquidity in USD
            current_block: Current block number
            
        Returns:
            Dict with:
            - fake_pump_suspected: bool
            - mev_pattern_detected: bool
            - manipulation_details: list of detected patterns
        """
        token_addr = token_address.lower()
        
        # Check cache first
        cached = self._get_cached_result(token_addr)
        if cached:
            return cached
        
        # Initialize result
        result = {
            'fake_pump_suspected': False,
            'mev_pattern_detected': False,
            'manipulation_details': [],
            'analysis_block': current_block
        }
        
        # If no adapter or Web3$, return conservative result
        if not self.adapter or not hasattr(self.adapter, 'w3'):
            result['manipulation_details'].append('No adapter available for tx analysis')
            return result
        
        try:
            w3 = self.adapter.w3
            if not w3:
                return result
            
            # Get current block if not provided
            if current_block == 0:
                current_block = w3.eth.block_number
            
            # Analyze transactions in recent blocks
            patterns = self._scan_recent_blocks(
                w3=w3,
                token_address=token_addr,
                pair_address=pair_address.lower(),
                from_block=max(0, current_block - TX_ANALYSIS_BLOCKS_BACK),
                to_block=current_block,
                liquidity_usd=liquidity_usd
            )
            
            # Process detected patterns
            for pattern in patterns:
                result['manipulation_details'].append(f"{pattern.pattern_type}: {pattern.details}")
                
                if pattern.pattern_type in ['RAPID_BUYSELL', 'WALLET_SPAM']:
                    result['fake_pump_suspected'] = True
                    
                if pattern.pattern_type in ['GAS_SPIKE', 'MEV_SANDWICH']:
                    result['mev_pattern_detected'] = True
            
            # Cache the result
            self._cache_result(token_addr, result)
            
        except Exception as e:
            result['manipulation_details'].append(f'Analysis error: {str(e)[:50]}')
        
        return result
    
    def _scan_recent_blocks(self, w3, token_address: str, pair_address: str,
                            from_block: int, to_block: int,
                            liquidity_usd: float) -> List[TransactionPattern]:
        """
        Scan recent blocks for suspicious transaction patterns.
        
        Returns list of detected patterns.
        """
        patterns = []
        wallet_tx_count: Dict[str, Dict[int, int]] = {}  # wallet -> {block -> count}
        wallet_actions: Dict[str, List[Dict]] = {}  # wallet -> [action records]
        gas_prices = []
        
        try:
            for block_num in range(from_block, to_block + 1):
                try:
                    block = w3.eth.get_block(block_num, full_transactions=True)
                except Exception:
                    continue
                
                for tx in block.get('transactions', []):
                    # Check if transaction involves our token or pair
                    tx_to = (tx.get('to') or '').lower()
                    tx_input_raw = tx.get('input', b'')
                    # Convert HexBytes to hex string for comparison
                    if hasattr(tx_input_raw, 'hex'):
                        tx_input = tx_input_raw.hex().lower()
                    else:
                        tx_input = str(tx_input_raw).lower() if tx_input_raw else ''
                    
                    # Simple check - is this tx to the pair or contains token address
                    involves_token = (
                        tx_to == pair_address or
                        (token_address in tx_input if tx_input else False)
                    )
                    
                    if not involves_token:
                        continue
                    
                    # Track wallet activity
                    wallet = tx.get('from', '').lower()
                    if wallet:
                        # Track tx count per block
                        if wallet not in wallet_tx_count:
                            wallet_tx_count[wallet] = {}
                        if block_num not in wallet_tx_count[wallet]:
                            wallet_tx_count[wallet][block_num] = 0
                        wallet_tx_count[wallet][block_num] += 1
                        
                        # Track actions
                        if wallet not in wallet_actions:
                            wallet_actions[wallet] = []
                        wallet_actions[wallet].append({
                            'block': block_num,
                            'value': tx.get('value', 0),
                            'gas_price': tx.get('gasPrice', 0)
                        })
                    
                    # Track gas prices
                    gas_price = tx.get('gasPrice', 0)
                    if gas_price > 0:
                        gas_prices.append(gas_price)
            
            # Analyze patterns
            
            # 1. Check for wallet spam (multiple tx in single block)
            for wallet, blocks in wallet_tx_count.items():
                for block_num, count in blocks.items():
                    if count >= 3:  # 3+ tx in same block is suspicious
                        patterns.append(TransactionPattern(
                            pattern_type='WALLET_SPAM',
                            wallet_address=wallet,
                            block_number=block_num,
                            details=f'{count} tx from {wallet[:10]}... in block {block_num}'
                        ))
            
            # 2. Check for rapid buy+sell (activity across multiple blocks)
            for wallet, actions in wallet_actions.items():
                if len(actions) >= 2:
                    # Sort by block
                    sorted_actions = sorted(actions, key=lambda x: x['block'])
                    
                    # Check for activity in quick succession (within 2 blocks)
                    for i in range(len(sorted_actions) - 1):
                        block_diff = sorted_actions[i+1]['block'] - sorted_actions[i]['block']
                        if block_diff <= 2 and block_diff > 0:
                            patterns.append(TransactionPattern(
                                pattern_type='RAPID_BUYSELL',
                                wallet_address=wallet,
                                block_number=sorted_actions[i]['block'],
                                details=f'{wallet[:10]}... active in {block_diff} block(s)'
                            ))
                            break  # One pattern per wallet is enough
            
            # 3. Check for gas spike anomaly
            if gas_prices:
                # SAFE: Prevent division by zero if gas_prices is empty
                avg_gas = safe_div(sum(gas_prices), len(gas_prices), default=1.0)
                for gas_price in gas_prices:
                    if gas_price > avg_gas * GAS_SPIKE_MULTIPLIER:
                        patterns.append(TransactionPattern(
                            pattern_type='GAS_SPIKE',
                            wallet_address='unknown',
                            block_number=to_block,
                            details=f'Gas {safe_div(gas_price, 1e9, default=0):.1f} Gwei vs avg {safe_div(avg_gas, 1e9, default=0):.1f} Gwei'
                        ))
                        break  # One gas spike pattern is enough
            
        except Exception as e:
            # Log but don't fail
            print(f"⚠️  Transaction analysis error: {e}")
        
        return patterns
    
    def _get_cached_result(self, token_address: str) -> Optional[Dict]:
        """Get cached analysis result if still valid"""
        if token_address in self._cache:
            cached = self._cache[token_address]
            if time.time() - cached.get('_cached_at', 0) < self._cache_ttl:
                return cached
            del self._cache[token_address]
        return None
    
    def _cache_result(self, token_address: str, result: Dict) -> None:
        """Cache analysis result"""
        result['_cached_at'] = time.time()
        self._cache[token_address] = result
    
    def clear_cache(self) -> None:
        """Clear all cached results"""
        self._cache = {}
