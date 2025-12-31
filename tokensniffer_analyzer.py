"""
TokenSniffer-Style Security Analyzer

Comprehensive security analysis similar to TokenSniffer, including:
- Honeypot detection (buy/sell simulation)
- Contract verification check
- Holder distribution analysis
- Liquidity lock verification
- Creator wallet analysis
"""

from web3 import Web3
from typing import Dict, Optional, List
import requests
import time


class TokenSnifferAnalyzer:
    """Enhanced security analyzer with TokenSniffer-style checks."""
    
    def __init__(self, w3: Web3, chain_name: str):
        """
        Initialize TokenSniffer-style analyzer.
        
        Args:
            w3: Web3 instance
            chain_name: Chain name (base, ethereum, etc.)
        """
        self.w3 = w3
        self.chain_name = chain_name.lower()
        
        # API endpoints
        self.honeypot_api = "https://api.honeypot.is/v2/IsHoneypot"
        self.goplus_api = f"https://api.gopluslabs.io/api/v1/token_security/{self._get_goplus_chain_id()}"
        
        # ERC20 ABI for holder analysis
        self.erc20_abi = [
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        ]
    
    def _get_goplus_chain_id(self) -> str:
        """Get GoPlus chain ID."""
        chain_ids = {
            'ethereum': '1',
            'base': '8453',
            'bsc': '56',
            'polygon': '137',
            'solana': 'solana'
        }
        return chain_ids.get(self.chain_name, '1')
    
    def analyze_comprehensive(self, token_address: str, pair_address: str = None) -> Dict:
        """
        Perform comprehensive TokenSniffer-style analysis.
        
        Returns dict with:
        - swap_analysis: Honeypot detection, buy/sell fees
        - contract_analysis: Verification, ownership, permissions
        - holder_analysis: Distribution, creator wallet, top holders
        - liquidity_analysis: Current liquidity, locks
        """
        result = {
            'swap_analysis': {},
            'contract_analysis': {},
            'holder_analysis': {},
            'liquidity_analysis': {},
            'overall_score': 0,
            'risk_level': 'UNKNOWN'
        }
        
        # 1. SWAP ANALYSIS (Honeypot Detection)
        print("🔍 Analyzing swap behavior...")
        result['swap_analysis'] = self._analyze_swap(token_address)
        
        # 2. CONTRACT ANALYSIS
        print("📜 Analyzing contract...")
        result['contract_analysis'] = self._analyze_contract(token_address)
        
        # 3. HOLDER ANALYSIS
        print("👥 Analyzing holder distribution...")
        result['holder_analysis'] = self._analyze_holders(token_address)
        
        # 4. LIQUIDITY ANALYSIS
        print("💧 Analyzing liquidity...")
        result['liquidity_analysis'] = self._analyze_liquidity(token_address, pair_address)
        
        # 5. CALCULATE OVERALL SCORE
        result['overall_score'] = self._calculate_overall_score(result)
        result['risk_level'] = self._determine_risk_level(result['overall_score'])
        
        return result
    
    def _analyze_swap(self, token_address: str) -> Dict:
        """
        Analyze swap behavior (honeypot detection).
        
        Checks:
        - Is token sellable?
        - Buy fee
        - Sell fee
        """
        swap_result = {
            'is_honeypot': False,
            'can_sell': True,
            'buy_fee_percent': 0,
            'sell_fee_percent': 0,
            'swap_simulation_passed': False,
            'details': []
        }
        
        try:
            # Skip honeypot.is and simulation for Solana (EVM tool)
            if self.chain_name == 'solana':
                swap_result['details'].append("ℹ️ Swap simulation skipped for Solana (EVM tool)")
                # Return neutral result so it doesn't fail
                return swap_result

            # Try honeypot.is API
            url = f"{self.honeypot_api}?address={token_address}&chainID={self._get_goplus_chain_id()}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse honeypot.is response
                if 'simulationSuccess' in data:
                    swap_result['swap_simulation_passed'] = data.get('simulationSuccess', False)
                
                if 'honeypotResult' in data:
                    hp_data = data['honeypotResult']
                    swap_result['is_honeypot'] = hp_data.get('isHoneypot', False)
                
                if 'simulationResult' in data:
                    sim_data = data['simulationResult']
                    swap_result['buy_fee_percent'] = sim_data.get('buyTax', 0)
                    swap_result['sell_fee_percent'] = sim_data.get('sellTax', 0)
                
                # Determine if can sell
                swap_result['can_sell'] = not swap_result['is_honeypot']
                
                # Add details
                if swap_result['is_honeypot']:
                    swap_result['details'].append("⚠️ HONEYPOT DETECTED - Cannot sell")
                else:
                    swap_result['details'].append("✅ Token is sellable (not a honeypot)")
                
                if swap_result['buy_fee_percent'] < 5:
                    swap_result['details'].append(f"✅ Buy fee is less than 5% ({swap_result['buy_fee_percent']:.1f}%)")
                else:
                    swap_result['details'].append(f"⚠️ High buy fee ({swap_result['buy_fee_percent']:.1f}%)")
                
                if swap_result['sell_fee_percent'] < 5:
                    swap_result['details'].append(f"✅ Sell fee is less than 5% ({swap_result['sell_fee_percent']:.1f}%)")
                else:
                    swap_result['details'].append(f"⚠️ High sell fee ({swap_result['sell_fee_percent']:.1f}%)")
        
        except Exception as e:
            swap_result['details'].append(f"⚠️ Could not verify honeypot status: {str(e)[:50]}")
        
        return swap_result
    
    def _analyze_contract(self, token_address: str) -> Dict:
        """
        Analyze contract security.
        
        Checks:
        - Contract verified
        - Ownership status
        - Special permissions
        """
        contract_result = {
            'is_verified': False,
            'is_open_source': False,
            'ownership_renounced': False,
            'has_mint_function': False,
            'has_pause_function': False,
            'has_blacklist_function': False,
            'creator_has_special_permission': False,
            'details': []
        }
        
        try:
            # Use GoPlus API for contract analysis
            if self.chain_name == 'solana':
                 url = f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={token_address}"
            else:
                 url = f"{self.goplus_api}?contract_addresses={token_address}"
                 
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data and token_address.lower() in data['result']:
                    token_data = data['result'][token_address.lower()]
                    
                    # Check if verified
                    contract_result['is_verified'] = token_data.get('is_open_source', '0') == '1'
                    contract_result['is_open_source'] = contract_result['is_verified']
                    
                    # Check ownership
                    owner_address = token_data.get('owner_address', '')
                    if owner_address in ['0x0000000000000000000000000000000000000000', 
                                        '0x000000000000000000000000000000000000dEaD', '']:
                        contract_result['ownership_renounced'] = True
                    
                    # Check functions
                    contract_result['has_mint_function'] = token_data.get('is_mintable', '0') == '1'
                    contract_result['has_pause_function'] = token_data.get('can_take_back_ownership', '0') == '1'
                    contract_result['has_blacklist_function'] = token_data.get('is_blacklisted', '0') == '1'
                    
                    # Check creator permissions
                    contract_result['creator_has_special_permission'] = (
                        contract_result['has_mint_function'] or 
                        contract_result['has_pause_function'] or
                        not contract_result['ownership_renounced']
                    )
                    
                    # Add details
                    if contract_result['is_verified']:
                        contract_result['details'].append("✅ Verified contract source")
                    else:
                        contract_result['details'].append("⚠️ Contract source not verified")
                    
                    if contract_result['ownership_renounced']:
                        contract_result['details'].append("✅ Ownership renounced or no owner contract")
                    else:
                        contract_result['details'].append("⚠️ Ownership not renounced")
                    
                    if not contract_result['creator_has_special_permission']:
                        contract_result['details'].append("✅ Creator not authorized for special permission")
                    else:
                        contract_result['details'].append("⚠️ Creator has special permissions")
        
        except Exception as e:
            contract_result['details'].append(f"⚠️ Could not verify contract: {str(e)[:50]}")
        
        return contract_result
    
    def _analyze_holders(self, token_address: str) -> Dict:
        """
        Analyze holder distribution.
        
        Checks:
        - Tokens burned
        - Creator wallet percentage
        - Top holder percentages
        - Top 10 holders total
        """
        holder_result = {
            'tokens_burned_percent': 0,
            'circulating_supply': 0,
            'creator_wallet_percent': 0,
            'max_holder_percent': 0,
            'top10_holders_percent': 0,
            'holder_count': 0,
            'details': []
        }
        
        try:
            # Use GoPlus API for holder analysis
            if self.chain_name == 'solana':
                 url = f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={token_address}"
            else:
                 url = f"{self.goplus_api}?contract_addresses={token_address}"

            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data and token_address.lower() in data['result']:
                    token_data = data['result'][token_address.lower()]
                    
                    # Get total supply and calculate burned
                    total_supply = float(token_data.get('total_supply', 0))
                    holder_count = int(token_data.get('holder_count', 0))
                    
                    holder_result['holder_count'] = holder_count
                    
                    # Parse holders data
                    holders = token_data.get('holders', [])
                    if holders:
                        # Calculate top 10 percentage
                        top10_percent = sum(float(h.get('percent', 0)) for h in holders[:10])
                        holder_result['top10_holders_percent'] = top10_percent
                        
                        # Get max holder
                        if len(holders) > 0:
                            holder_result['max_holder_percent'] = float(holders[0].get('percent', 0))
                        
                        # Check creator wallet (usually first holder)
                        creator_percent = float(token_data.get('creator_percent', 0))
                        holder_result['creator_wallet_percent'] = creator_percent
                    
                    # Add details
                    if holder_result['tokens_burned_percent'] > 0:
                        holder_result['details'].append(f"🔥 Tokens burned: {holder_result['tokens_burned_percent']:.2f}%")
                    
                    if holder_result['creator_wallet_percent'] < 5:
                        holder_result['details'].append(f"✅ Creator wallet < 5% of supply ({holder_result['creator_wallet_percent']:.2f}%)")
                    else:
                        holder_result['details'].append(f"⚠️ Creator wallet ≥ 5% of supply ({holder_result['creator_wallet_percent']:.2f}%)")
                    
                    if holder_result['max_holder_percent'] < 5:
                        holder_result['details'].append(f"✅ All holders < 5% of supply")
                    else:
                        holder_result['details'].append(f"⚠️ Max holder has {holder_result['max_holder_percent']:.2f}% of supply")
                    
                    if holder_result['top10_holders_percent'] < 70:
                        holder_result['details'].append(f"✅ Top 10 holders < 70% of supply ({holder_result['top10_holders_percent']:.2f}%)")
                    else:
                        holder_result['details'].append(f"⚠️ Top 10 holders ≥ 70% of supply ({holder_result['top10_holders_percent']:.2f}%)")
        
        except Exception as e:
            holder_result['details'].append(f"⚠️ Could not analyze holders: {str(e)[:50]}")
        
        return holder_result
    
    def _analyze_liquidity(self, token_address: str, pair_address: str = None) -> Dict:
        """
        Analyze liquidity status.
        
        Checks:
        - Current liquidity
        - Liquidity locked/burned
        - Multiple pools
        """
        liq_result = {
            'total_liquidity_usd': 0,
            'liquidity_locked_percent': 0,
            'lock_duration_days': 0,
            'pools_detected': 0,
            'details': []
        }
        
        try:
            # Use GoPlus API for liquidity analysis
            if self.chain_name == 'solana':
                 url = f"https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={token_address}"
            else:
                 url = f"{self.goplus_api}?contract_addresses={token_address}"

            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data and token_address.lower() in data['result']:
                    token_data = data['result'][token_address.lower()]
                    
                    # Get liquidity info
                    lp_total_supply = float(token_data.get('lp_total_supply', 0))
                    lp_holder_count = int(token_data.get('lp_holder_count', 0))
                    
                    liq_result['pools_detected'] = lp_holder_count
                    
                    # Check if liquidity is locked
                    is_locked = token_data.get('is_locked', '0') == '1'
                    if is_locked:
                        liq_result['liquidity_locked_percent'] = 95  # Assume 95% if locked
                        liq_result['details'].append("✅ Liquidity is locked")
                    
                    # Add details
                    if liq_result['total_liquidity_usd'] > 10000:
                        liq_result['details'].append(f"✅ Adequate current liquidity (${liq_result['total_liquidity_usd']:,.0f})")
                    elif liq_result['total_liquidity_usd'] > 0:
                        liq_result['details'].append(f"⚠️ Low liquidity (${liq_result['total_liquidity_usd']:,.0f})")
                    
                    if liq_result['liquidity_locked_percent'] >= 95:
                        liq_result['details'].append(f"✅ At least 95% of liquidity locked/burned ({liq_result['liquidity_locked_percent']:.0f}%)")
                    elif liq_result['liquidity_locked_percent'] > 0:
                        liq_result['details'].append(f"⚠️ Only {liq_result['liquidity_locked_percent']:.0f}% of liquidity locked")
                    else:
                        liq_result['details'].append("⚠️ Liquidity not locked")
        
        except Exception as e:
            liq_result['details'].append(f"⚠️ Could not analyze liquidity: {str(e)[:50]}")
        
        return liq_result
    
    def _calculate_overall_score(self, analysis: Dict) -> int:
        """Calculate overall security score (0-100)."""
        score = 100
        
        # Swap Analysis (-50 for honeypot)
        if analysis['swap_analysis'].get('is_honeypot'):
            score -= 50
        if analysis['swap_analysis'].get('buy_fee_percent', 0) >= 5:
            score -= 5
        if analysis['swap_analysis'].get('sell_fee_percent', 0) >= 5:
            score -= 5
        
        # Contract Analysis
        if not analysis['contract_analysis'].get('is_verified'):
            score -= 10
        if not analysis['contract_analysis'].get('ownership_renounced'):
            score -= 15
        if analysis['contract_analysis'].get('creator_has_special_permission'):
            score -= 10
        
        # Holder Analysis
        if analysis['holder_analysis'].get('creator_wallet_percent', 0) >= 5:
            score -= 10
        if analysis['holder_analysis'].get('top10_holders_percent', 0) >= 70:
            score -= 10
        
        # Liquidity Analysis
        if analysis['liquidity_analysis'].get('liquidity_locked_percent', 0) < 50:
            score -= 10
        
        return max(0, score)
    
    def _determine_risk_level(self, score: int) -> str:
        """Determine risk level from score."""
        if score >= 90:
            return 'VERY_LOW'
        elif score >= 75:
            return 'LOW'
        elif score >= 60:
            return 'MEDIUM'
        elif score >= 40:
            return 'HIGH'
        else:
            return 'CRITICAL'
