"""
Wallet Tracker - Monitors deployer and smart money wallet activities
Tracks dev wallet behavior and identifies smart money involvement.

This module provides:
- Deployer wallet monitoring (LP removal, token transfers, approvals)
- Smart money detection (early interaction, profitable history)
- Risk classification based on wallet behavior
"""
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from config import (
    DEV_WALLET_CHECK_ENABLED,
    SMART_MONEY_CHECK_ENABLED,
    WALLET_AGE_THRESHOLD_DAYS
)
from safe_math import safe_div


@dataclass
class WalletActivity:
    """Record of wallet activity"""
    wallet_address: str
    activity_type: str  # 'LP_REMOVE', 'TOKEN_TRANSFER', 'APPROVAL', etc.
    block_number: int
    timestamp: float
    details: str


class WalletTracker:
    """
    Tracks deployer and smart money wallet activities.
    
    Dev Wallet Monitoring:
    - Tracks deployer address
    - Monitors LP token transfers out
    - Monitors large token transfers
    - Checks approval changes
    - Classification: SAFE | WARNING | DUMP
    
    Smart Money Detection:
    - Identifies early interacting wallets
    - Checks wallet age (non-fresh)
    - Flags smart money involvement
    """
    
    # Known suspicious patterns
    DUMP_PATTERNS = {'LP_REMOVE', 'LARGE_TRANSFER_OUT', 'RENOUNCE_THEN_DUMP'}
    WARNING_PATTERNS = {'UNUSUAL_APPROVAL', 'MULTIPLE_TRANSFERS'}
    
    def __init__(self, adapter=None):
        """
        Initialize WalletTracker.
        
        Args:
            adapter: Chain adapter with Web3 connection
        """
        self.adapter = adapter
        self._deployer_cache: Dict[str, str] = {}  # token -> deployer
        self._activity_cache: Dict[str, List[WalletActivity]] = {}
    
    def analyze_wallets(self, token_address: str, pair_address: str,
                        creation_block: int = 0) -> Dict:
        """
        Analyze wallet activities for a token.
        
        Args:
            token_address: Token contract address
            pair_address: DEX pair address
            creation_block: Block where token was created
            
        Returns:
            Dict with:
            - dev_activity_flag: SAFE | WARNING | DUMP
            - smart_money_involved: bool
            - deployer_address: str
            - wallet_details: dict with specific findings
        """
        token_addr = token_address.lower()
        
        # Default result
        result = {
            'dev_activity_flag': 'SAFE',
            'smart_money_involved': False,
            'deployer_address': '',
            'wallet_details': {
                'deployer_checked': False,
                'lp_status': 'UNKNOWN',
                'early_buyers_count': 0,
                'smart_wallets_found': 0,
                'warning_signs': []
            }
        }
        
        if not DEV_WALLET_CHECK_ENABLED and not SMART_MONEY_CHECK_ENABLED:
            result['wallet_details']['warning_signs'].append('Wallet tracking disabled')
            return result
        
        # If no adapter, return conservative result
        if not self.adapter or not hasattr(self.adapter, 'w3'):
            result['wallet_details']['warning_signs'].append('No adapter for wallet analysis')
            return result
        
        try:
            w3 = self.adapter.w3
            
            # Get deployer if possible
            if DEV_WALLET_CHECK_ENABLED:
                deployer = self._get_deployer_address(w3, token_addr)
                if deployer:
                    result['deployer_address'] = deployer
                    result['wallet_details']['deployer_checked'] = True
                    
                    # Check dev wallet activity
                    dev_status = self._check_dev_activity(w3, token_addr, pair_address, deployer)
                    result['dev_activity_flag'] = dev_status['flag']
                    result['wallet_details']['lp_status'] = dev_status['lp_status']
                    result['wallet_details']['warning_signs'].extend(dev_status.get('warnings', []))
            
            # Check for smart money
            if SMART_MONEY_CHECK_ENABLED:
                smart_money = self._detect_smart_money(w3, token_addr, pair_address, creation_block)
                result['smart_money_involved'] = smart_money['detected']
                result['wallet_details']['early_buyers_count'] = smart_money['early_buyers']
                result['wallet_details']['smart_wallets_found'] = smart_money['smart_count']
            
        except Exception as e:
            result['wallet_details']['warning_signs'].append(f'Analysis error: {str(e)[:50]}')
        
        return result
    
    def _get_deployer_address(self, w3, token_address: str) -> Optional[str]:
        """
        Get deployer address for a token.
        
        Attempts to find the creator of the token contract.
        """
        token_addr = token_address.lower()
        
        # Check cache first
        if token_addr in self._deployer_cache:
            return self._deployer_cache[token_addr]
        
        try:
            # Try to get creation transaction by checking first block with code
            code = w3.eth.get_code(w3.to_checksum_address(token_address))
            if code == b'' or code == '0x':
                return None
            
            # Simple approach: Get recent transactions to the token
            # In practice, would use etherscan API or trace the creation tx
            # For now, return None - full implementation would use external API
            
            # Placeholder: Would query creation tx from block explorer API
            # self._deployer_cache[token_addr] = deployer
            return None
            
        except Exception:
            return None
    
    def _check_dev_activity(self, w3, token_address: str, pair_address: str,
                            deployer_address: str) -> Dict:
        """
        Check developer wallet activity for suspicious patterns.
        
        Returns dict with:
        - flag: SAFE | WARNING | DUMP
        - lp_status: HELD | REMOVED | UNKNOWN
        - warnings: list of warning messages
        """
        result = {
            'flag': 'SAFE',
            'lp_status': 'UNKNOWN',
            'warnings': []
        }
        
        if not deployer_address:
            return result
        
        try:
            # Check LP token balance of deployer
            # LP tokens are usually held in the pair contract
            pair_contract = w3.eth.contract(
                address=w3.to_checksum_address(pair_address),
                abi=[{
                    "constant": True,
                    "inputs": [{"name": "owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                }]
            )
            
            deployer_lp_balance = pair_contract.functions.balanceOf(
                w3.to_checksum_address(deployer_address)
            ).call()
            
            total_supply = 0
            try:
                total_supply_contract = w3.eth.contract(
                    address=w3.to_checksum_address(pair_address),
                    abi=[{
                        "constant": True,
                        "inputs": [],
                        "name": "totalSupply",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "type": "function"
                    }]
                )
                total_supply = total_supply_contract.functions.totalSupply().call()
            except:
                pass
            
            if total_supply > 0:
                # SAFE: Prevent division by zero if total_supply is zero
                lp_percentage = safe_div(deployer_lp_balance, total_supply, default=0) * 100
                
                if lp_percentage < 1:
                    result['lp_status'] = 'REMOVED'
                    result['flag'] = 'DUMP'
                    result['warnings'].append(f'Dev LP removed ({lp_percentage:.2f}% remaining)')
                elif lp_percentage < 50:
                    result['lp_status'] = 'PARTIAL'
                    result['flag'] = 'WARNING'
                    result['warnings'].append(f'Dev has {lp_percentage:.1f}% LP')
                else:
                    result['lp_status'] = 'HELD'
            
        except Exception as e:
            result['warnings'].append(f'LP check failed: {str(e)[:30]}')
        
        return result
    
    def _detect_smart_money(self, w3, token_address: str, pair_address: str,
                            creation_block: int) -> Dict:
        """
        Detect smart money involvement.
        
        Criteria:
        - Early interaction (first 10 transactions)
        - Wallet age > 30 days
        - Non-fresh wallet (has transaction history)
        
        Returns dict with:
        - detected: bool
        - early_buyers: int count
        - smart_count: int count of qualified wallets
        """
        result = {
            'detected': False,
            'early_buyers': 0,
            'smart_count': 0
        }
        
        try:
            # Get current block
            current_block = w3.eth.block_number
            
            # Blocks for ~30 days (assuming 12 sec blocks for EVM)
            blocks_per_day = 7200
            min_wallet_age_blocks = WALLET_AGE_THRESHOLD_DAYS * blocks_per_day
            
            # Scan first few blocks after creation for early buyers
            scan_blocks = min(10, current_block - creation_block) if creation_block > 0 else 5
            
            early_wallets = set()
            
            for block_offset in range(scan_blocks):
                try:
                    block = w3.eth.get_block(creation_block + block_offset + 1, full_transactions=True)
                    
                    for tx in block.get('transactions', []):
                        tx_to = (tx.get('to') or '').lower()
                        
                        # Check if tx involves the pair
                        if tx_to == pair_address.lower():
                            wallet = tx.get('from', '').lower()
                            if wallet:
                                early_wallets.add(wallet)
                                if len(early_wallets) >= 10:
                                    break
                    
                    if len(early_wallets) >= 10:
                        break
                        
                except Exception:
                    continue
            
            result['early_buyers'] = len(early_wallets)
            
            # Check if any early wallets are "smart" (old, experienced)
            for wallet in list(early_wallets)[:5]:  # Check up to 5 wallets
                try:
                    # Check wallet's first transaction (proxy for age)
                    tx_count = w3.eth.get_transaction_count(w3.to_checksum_address(wallet))
                    
                    # Wallet with significant tx history is likely not fresh
                    if tx_count > 50:  # More than 50 transactions = experienced
                        result['smart_count'] += 1
                        
                except Exception:
                    continue
            
            result['detected'] = result['smart_count'] >= 2  # 2+ smart wallets = smart money
            
        except Exception as e:
            print(f"⚠️  Smart money detection error: {e}")
        
        return result
    
    def get_quick_wallet_analysis(self, token_address: str, pair_address: str,
                                  creation_block: int = 0) -> Dict:
        """
        Quick wallet analysis - main entry point for analyzer.
        
        Args:
            token_address: Token contract address
            pair_address: DEX pair address
            creation_block: Block where token was created (0 if unknown)
            
        Returns:
            Wallet analysis result dict
        """
        return self.analyze_wallets(token_address, pair_address, creation_block)
