import requests
import time
from datetime import datetime
from web3 import Web3
from functools import wraps
from config import GOPLUS_API_URL

# Import new security analysis modules
from momentum_tracker import MomentumTracker
from transaction_analyzer import TransactionAnalyzer
from wallet_tracker import WalletTracker
from phase_detector import detect_market_phase, get_phase_scoring_weights

# Minimal ERC20 ABI
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}], "type": "function"}
]

# Uniswap V2 Pair ABI (minimal)
PAIR_ABI = [
    {"constant": True, "inputs": [], "name": "getReserves", "outputs": [
        {"name": "reserve0", "type": "uint112"},
        {"name": "reserve1", "type": "uint112"},
        {"name": "blockTimestampLast", "type": "uint32"}
    ], "type": "function"},
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"}
]

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator to retry functions with exponential backoff on network errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, requests.exceptions.ConnectionError, 
                        requests.exceptions.Timeout, requests.exceptions.RequestException,
                        OSError) as e:
                    if attempt == max_retries - 1:
                        print(f"⚠️  Max retries reached for {func.__name__}")
                        return None  # Return None instead of crashing
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️  Network error in {func.__name__}, retrying in {delay}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class TokenAnalyzer:
    def __init__(self, web3_provider=None, adapter=None):
        """
        Initialize TokenAnalyzer in either legacy or adapter mode.
        
        Args:
            web3_provider: Web3 instance (legacy mode - for backward compatibility)
            adapter: ChainAdapter instance (new multi-chain mode)
            
        Initializes new security analysis modules:
        - MomentumTracker: Multi-cycle validation
        - TransactionAnalyzer: Fake pump/MEV detection
        - WalletTracker: Dev/smart money tracking
        """
        # Determine mode
        if adapter is not None:
            # New adapter-based approach
            self.adapter = adapter
            self.mode = 'adapter'
            self.w3 = None
            
            # Initialize security analysis modules with adapter
            self.momentum_tracker = MomentumTracker(adapter=adapter)
            self.transaction_analyzer = TransactionAnalyzer(adapter=adapter)
            self.wallet_tracker = WalletTracker(adapter=adapter)
        else:
            # Legacy web3 mode (backward compatibility)
            self.w3 = web3_provider
            self.mode = 'legacy'
            self.adapter = None
            
            # Initialize security modules without adapter (limited functionality)
            self.momentum_tracker = MomentumTracker(adapter=None)
            self.transaction_analyzer = TransactionAnalyzer(adapter=None)
            self.wallet_tracker = WalletTracker(adapter=None)
            
            if web3_provider:
                self.weth = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
                self.eth_price_usd = 3500

    def analyze_token(self, pair_data):
        """
        Takes raw pair data from scanner and enriches it with:
        - Token name/symbol
        - Liquidity in USD
        - Ownership status (renounced)
        - Security flags (GoPlus API)
        - Age in minutes
        
        NEW - Security Audit Upgrades:
        - Momentum validation (multi-cycle confirmation)
        - Fake pump / MEV detection
        - Wallet tracking (dev + smart money)
        - Market phase classification
        """
        # In adapter mode, delegate to adapter then enrich
        if self.mode == 'adapter' and self.adapter:
            analysis = self.adapter.analyze_token(pair_data)
            if analysis:
                # Enrich with security analysis modules
                analysis = self._enrich_with_security_analysis(analysis, pair_data)
            return analysis
        
        # Legacy mode (unchanged logic)
        try:
            token_address = Web3.to_checksum_address(pair_data['token_address'])
            pair_address = Web3.to_checksum_address(pair_data['pair_address'])
        except Exception as e:
            print(f"⚠️  Invalid address format: {e}")
            return None
        
        # Get token metadata with retry
        name, symbol = self._get_token_metadata(token_address)
        
        # Get liquidity from pair
        liquidity_usd = self._get_liquidity(pair_address, token_address)
        if liquidity_usd is None:
            liquidity_usd = 0
        
        # Check ownership renounced
        renounced = self._check_renounced(token_address)
        if renounced is None:
            renounced = False
        
        # Get security info from GoPlus
        security_data = self._get_security_data(token_address)
        if security_data is None:
            security_data = {'is_mintable': True, 'is_blacklisted': False, 'holder_count': 100}
        
        # Calculate age
        age_minutes = (int(time.time()) - pair_data['timestamp']) / 60
        
        return {
            'name': name,
            'symbol': symbol,
            'address': token_address,
            'age_minutes': age_minutes,
            'liquidity_usd': liquidity_usd,
            'renounced': renounced,
            'mintable': security_data.get('is_mintable', False),
            'blacklist': security_data.get('is_blacklisted', False),
            'top10_holders_percent': security_data.get('holder_count', 100)
        }
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _get_token_metadata(self, token_address):
        """Get token name and symbol with retry logic"""
        try:
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            return name, symbol
        except Exception as e:
            print(f"⚠️  Error getting token metadata: {e}")
            return "UNKNOWN", "???"
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _get_liquidity(self, pair_address, token_address):
        """Calculate liquidity in USD from pair reserves"""
        try:
            pair_contract = self.w3.eth.contract(address=pair_address, abi=PAIR_ABI)
            token0 = pair_contract.functions.token0().call()
            reserves = pair_contract.functions.getReserves().call()
            
            # Determine which reserve is WETH
            if token0.lower() == self.weth.lower():
                weth_reserve = reserves[0]
            else:
                weth_reserve = reserves[1]
            
            # Convert WETH to USD (WETH has 18 decimals)
            liquidity_usd = (weth_reserve / 1e18) * self.eth_price_usd
            return liquidity_usd
        except Exception as e:
            print(f"⚠️  Error getting liquidity: {e}")
            return 0
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _check_renounced(self, token_address):
        """Check if ownership is renounced (owner == 0x0 or 0xdead)"""
        try:
            token_contract = self.w3.eth.contract(address=token_address, abi=ERC20_ABI)
            owner = token_contract.functions.owner().call()
            zero_address = "0x0000000000000000000000000000000000000000"
            dead_address = "0x000000000000000000000000000000000000dEaD"
            return owner.lower() in [zero_address.lower(), dead_address.lower()]
        except:
            # If no owner() function, assume not renounced
            return False
    
    @retry_with_backoff(max_retries=2, base_delay=1)
    def _get_security_data(self, token_address):
        """Fetch security data from GoPlus API"""
        try:
            url = f"{GOPLUS_API_URL}?contract_addresses={token_address}"
            response = requests.get(url, timeout=10)  # Increased timeout
            response.raise_for_status()  # Raise exception for bad status codes
            data = response.json()
            
            if 'result' in data and token_address.lower() in data['result']:
                token_data = data['result'][token_address.lower()]
                
                # Parse GoPlus response
                is_mintable = token_data.get('is_mintable', '0') == '1'
                is_blacklisted = token_data.get('is_blacklisted', '0') == '1'
                
                # Calculate top 10 holder percentage
                holders = token_data.get('holders', [])
                if holders and len(holders) >= 10:
                    top10_percent = sum(float(h.get('percent', 0)) for h in holders[:10])
                else:
                    top10_percent = 100  # Assume worst case
                
                return {
                    'is_mintable': is_mintable,
                    'is_blacklisted': is_blacklisted,
                    'holder_count': top10_percent
                }
        except Exception as e:
            print(f"⚠️  GoPlus API error: {e}")
        
        # Default to risky values if API fails
        return {'is_mintable': True, 'is_blacklisted': False, 'holder_count': 100}
    
    def _enrich_with_security_analysis(self, analysis: dict, pair_data: dict) -> dict:
        """
        Enrich token analysis with security audit modules.
        
        Adds:
        - Momentum validation
        - Transaction pattern analysis (fake pump/MEV)
        - Wallet tracking (dev/smart money)
        - Market phase classification
        
        Args:
            analysis: Base analysis from adapter
            pair_data: Original pair data from scanner
            
        Returns:
            Enriched analysis dict
        """
        try:
            token_address = analysis.get('address', '')
            pair_address = analysis.get('pair_address', pair_data.get('pair_address', ''))
            liquidity_usd = analysis.get('liquidity_usd', 0)
            block_number = analysis.get('block_number', pair_data.get('block_number', 0))
            age_minutes = analysis.get('age_minutes', 0)
            
            # 1. Market Phase Detection
            market_phase = detect_market_phase(age_minutes)
            analysis['market_phase'] = market_phase
            analysis['phase_weights'] = get_phase_scoring_weights(market_phase)
            
            # 2. Momentum Validation
            try:
                momentum_result = self.momentum_tracker.get_quick_momentum(
                    token_address=token_address,
                    liquidity_usd=liquidity_usd,
                    price_estimate=1.0,  # Simplified - would compute from reserves
                    volume_indicator=1.0 if liquidity_usd > 0 else 0,
                    block_number=block_number
                )
                analysis['momentum_confirmed'] = momentum_result.get('momentum_confirmed', False)
                analysis['momentum_score'] = momentum_result.get('momentum_score', 0)
                analysis['momentum_details'] = momentum_result.get('momentum_details', {})
            except Exception as e:
                print(f"⚠️  Momentum tracking error: {e}")
                analysis['momentum_confirmed'] = False
                analysis['momentum_score'] = 0
                analysis['momentum_details'] = {'error': str(e)}
            
            # 3. Transaction Pattern Analysis (Fake Pump / MEV Detection)
            try:
                tx_result = self.transaction_analyzer.analyze_token_transactions(
                    token_address=token_address,
                    pair_address=pair_address,
                    liquidity_usd=liquidity_usd,
                    current_block=block_number
                )
                analysis['fake_pump_suspected'] = tx_result.get('fake_pump_suspected', False)
                analysis['mev_pattern_detected'] = tx_result.get('mev_pattern_detected', False)
                analysis['manipulation_details'] = tx_result.get('manipulation_details', [])
            except Exception as e:
                print(f"⚠️  Transaction analysis error: {e}")
                analysis['fake_pump_suspected'] = False
                analysis['mev_pattern_detected'] = False
                analysis['manipulation_details'] = [f'Analysis error: {str(e)[:30]}']
            
            # 4. Wallet Tracking (Dev + Smart Money)
            try:
                wallet_result = self.wallet_tracker.get_quick_wallet_analysis(
                    token_address=token_address,
                    pair_address=pair_address,
                    creation_block=block_number
                )
                analysis['dev_activity_flag'] = wallet_result.get('dev_activity_flag', 'UNKNOWN')
                analysis['smart_money_involved'] = wallet_result.get('smart_money_involved', False)
                analysis['deployer_address'] = wallet_result.get('deployer_address', '')
                analysis['wallet_details'] = wallet_result.get('wallet_details', {})
            except Exception as e:
                print(f"⚠️  Wallet tracking error: {e}")
                analysis['dev_activity_flag'] = 'UNKNOWN'
                analysis['smart_money_involved'] = False
                analysis['deployer_address'] = ''
                analysis['wallet_details'] = {'error': str(e)}
            
        except Exception as e:
            print(f"⚠️  Security analysis enrichment error: {e}")
        
        return analysis

