"""
Sniper Detector - Early token detection for high-risk opportunities

This module:
- Listens to newly detected pairs (reuses scanner output)
- Filters by age (≤ max_age_minutes) and liquidity (≥ min_liquidity_usd)
- Analyzes recent transactions for buy activity
- Performs basic honeypot check only
- Does NOT check ownership, holder distribution, or deployer wallets

CRITICAL: This is HIGH RISK detection - tokens are NOT fully validated.
"""
import time
import requests
from typing import Dict, Optional, List
from .sniper_config import get_sniper_config, is_chain_allowed


class SniperDetector:
    """
    Detects early-stage tokens suitable for sniper alerts.
    
    Detection criteria:
    - Token age ≤ max_age_minutes
    - Liquidity ≥ min_liquidity_usd
    - Not a honeypot (if detectable)
    - Sufficient buy activity in last 30 seconds
    """
    
    def __init__(self, adapter=None):
        """
        Initialize sniper detector.
        
        Args:
            adapter: Chain adapter with Web3 connection
        """
        self.adapter = adapter
        self.config = get_sniper_config()
        self._processed_tokens = set()  # Track processed tokens to avoid duplicates
    
    def is_eligible(self, token_data: Dict) -> Dict:
        """
        Check if token is eligible for sniper detection.
        
        Args:
            token_data: Token analysis data from scanner
            
        Returns:
            Dict with:
            - eligible: bool
            - skip_reason: str if not eligible
            - token_age_minutes: float
        """
        result = {
            'eligible': False,
            'skip_reason': None,
            'token_age_minutes': 0
        }
        
        # Check chain
        chain = token_data.get('chain', '')
        if not is_chain_allowed(chain):
            result['skip_reason'] = f'Chain {chain} not allowed for sniper mode'
            return result
        
        # Check if already processed
        token_address = token_data.get('address', token_data.get('token_address', '')).lower()
        if token_address in self._processed_tokens:
            result['skip_reason'] = 'Already processed'
            return result
        
        # Calculate age
        token_age = token_data.get('age_minutes', 999)
        result['token_age_minutes'] = token_age
        
        # Age filter
        max_age = self.config.get('max_age_minutes', 3)
        min_age = self.config.get('min_age_minutes', 0)
        if token_age > max_age:
            result['skip_reason'] = f'Too old ({token_age:.1f} min > {max_age} min)'
            return result
        if token_age < min_age:
            result['skip_reason'] = f'Too young ({token_age:.1f} min < {min_age} min)'
            return result
        
        # Liquidity filter
        liquidity = token_data.get('liquidity_usd', 0)
        min_liquidity = self.config.get('min_liquidity_usd', 2000)
        if liquidity < min_liquidity:
            result['skip_reason'] = f'Low liquidity (${liquidity:,.0f} < ${min_liquidity:,})'
            return result
        
        # Honeypot check (basic)
        if self._is_honeypot(token_data):
            result['skip_reason'] = 'Honeypot detected'
            return result
        
        result['eligible'] = True
        return result
    
    def _is_honeypot(self, token_data: Dict) -> bool:
        """
        Basic honeypot detection.
        
        Checks GoPlus data if available, otherwise returns False (pass).
        """
        # Check if honeypot data is already in token_data
        if token_data.get('is_honeypot'):
            return True
        
        # Check GoPlus data if we have adapter
        if self.adapter and hasattr(self.adapter, '_get_goplus_data'):
            token_address = token_data.get('address', token_data.get('token_address', ''))
            try:
                goplus_data = self.adapter._get_goplus_data(token_address)
                if goplus_data:
                    # GoPlus returns '1' for true, '0' for false
                    is_honeypot = goplus_data.get('is_honeypot', '0') == '1'
                    return is_honeypot
            except Exception:
                pass  # Fail open - don't block on API errors
        
        return False
    
    def analyze_recent_activity(self, token_data: Dict) -> Dict:
        """
        Analyze recent transaction activity for sniper signals.
        
        Counts:
        - Buy transactions in last 30 seconds
        - Unique buyer wallets
        
        Args:
            token_data: Token data with address info
            
        Returns:
            Dict with:
            - buys_30s: int
            - unique_wallets: int
            - gas_spike_detected: bool
            - activity_analysis_success: bool
        """
        result = {
            'buys_30s': 0,
            'unique_wallets': 0,
            'gas_spike_detected': False,
            'activity_analysis_success': False
        }
        
        if not self.adapter or not hasattr(self.adapter, 'w3'):
            return result
        
        try:
            w3 = self.adapter.w3
            if not w3:
                return result
            
            pair_address = token_data.get('pair_address', '').lower()
            token_address = token_data.get('address', token_data.get('token_address', '')).lower()
            
            if not pair_address:
                return result
            
            current_block = w3.eth.block_number
            current_time = time.time()
            
            # Estimate blocks in last 30 seconds (assume ~2-3 sec/block for most EVM chains)
            blocks_to_scan = 15  # ~30 seconds of blocks
            from_block = max(0, current_block - blocks_to_scan)
            
            wallets = set()
            buy_count = 0
            gas_prices = []
            
            for block_num in range(from_block, current_block + 1):
                try:
                    block = w3.eth.get_block(block_num, full_transactions=True)
                    block_time = block.get('timestamp', 0)
                    
                    # Only consider transactions in last 30 seconds
                    if current_time - block_time > 30:
                        continue
                    
                    for tx in block.get('transactions', []):
                        tx_to = (tx.get('to') or '').lower()
                        
                        # Check if transaction is to the pair (potential swap)
                        if tx_to == pair_address:
                            wallet = tx.get('from', '').lower()
                            if wallet:
                                wallets.add(wallet)
                                buy_count += 1
                            
                            gas_price = tx.get('gasPrice', 0)
                            if gas_price > 0:
                                gas_prices.append(gas_price)
                                
                except Exception:
                    continue
            
            result['buys_30s'] = buy_count
            result['unique_wallets'] = len(wallets)
            result['activity_analysis_success'] = True
            
            # Check for gas spike
            if gas_prices and len(gas_prices) >= 2:
                avg_gas = sum(gas_prices) / len(gas_prices)
                max_gas = max(gas_prices)
                result['gas_spike_detected'] = max_gas > avg_gas * 2
            
        except Exception as e:
            # Log but don't fail
            print(f"⚠️  Sniper activity analysis error: {e}")
        
        return result
    
    def mark_processed(self, token_address: str):
        """Mark token as processed to prevent duplicate alerts."""
        self._processed_tokens.add(token_address.lower())
    
    def get_processed_count(self) -> int:
        """Get count of processed tokens."""
        return len(self._processed_tokens)
    
    def clear_processed(self):
        """Clear processed tokens (for testing or reset)."""
        self._processed_tokens = set()
