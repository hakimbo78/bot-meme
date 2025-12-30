"""
Improved Solana Token Analyzer

Uses multiple data sources to get comprehensive token information:
1. Solana RPC - On-chain data
2. DexScreener API - Market data, liquidity, price
3. Birdeye API - Token metadata, holder info (optional)
4. RugCheck API - Security analysis (optional)
"""

import requests
import time
from typing import Dict, Optional
from colorama import Fore


class ImprovedSolanaAnalyzer:
    """Enhanced Solana token analyzer with multiple data sources."""
    
    def __init__(self, rpc_url: str = None):
        """Initialize analyzer."""
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex"
        
    def analyze_token(self, token_address: str) -> Dict:
        """
        Comprehensive Solana token analysis.
        
        Returns dict with:
        - name, symbol, decimals
        - liquidity_sol, liquidity_usd
        - pool_address, dex
        - price_usd, price_change_24h
        - volume_24h, tx_24h
        - holder_count (if available)
        - security_flags
        """
        print(f"{Fore.CYAN}Analyzing Solana token: {token_address}")
        
        result = {
            'token_address': token_address,
            'name': 'UNKNOWN',
            'symbol': '???',
            'decimals': 0,
            'liquidity_sol': 0,
            'liquidity_usd': 0,
            'pool_address': 'N/A',
            'dex': 'UNKNOWN',
            'price_usd': 0,
            'price_change_24h': 0,
            'volume_24h': 0,
            'tx_24h': 0,
            'holder_count': 0,
            'metadata_ok': False,
            'lp_valid': False,
            'state': 'UNKNOWN'
        }
        
        # 1. Try DexScreener API (most reliable for market data)
        print(f"{Fore.YELLOW}Fetching data from DexScreener...")
        dex_data = self._get_dexscreener_data(token_address)
        
        if dex_data:
            result.update(dex_data)
            result['metadata_ok'] = True
            result['lp_valid'] = True
            result['state'] = 'ACTIVE'
            print(f"{Fore.GREEN}✅ DexScreener data retrieved")
        else:
            print(f"{Fore.YELLOW}⚠️  No DexScreener data found")
        
        # 2. Try Solana RPC for on-chain data
        print(f"{Fore.YELLOW}Fetching on-chain data...")
        rpc_data = self._get_rpc_data(token_address)
        
        if rpc_data:
            # Merge RPC data (don't overwrite DexScreener data)
            if not result['metadata_ok']:
                result.update(rpc_data)
            print(f"{Fore.GREEN}✅ RPC data retrieved")
        
        return result
    
    def _get_dexscreener_data(self, token_address: str) -> Optional[Dict]:
        """Get token data from DexScreener API."""
        try:
            url = f"{self.dexscreener_api}/tokens/{token_address}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if 'pairs' not in data or not data['pairs']:
                return None
            
            # Get the pair with highest liquidity
            pairs = data['pairs']
            main_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
            
            # Extract data
            base_token = main_pair.get('baseToken', {})
            quote_token = main_pair.get('quoteToken', {})
            liquidity = main_pair.get('liquidity', {})
            volume = main_pair.get('volume', {})
            price_change = main_pair.get('priceChange', {})
            txns = main_pair.get('txns', {})
            
            # Determine which is the meme token
            if base_token.get('address', '').lower() == token_address.lower():
                token_info = base_token
            else:
                token_info = quote_token
            
            return {
                'name': token_info.get('name', 'UNKNOWN'),
                'symbol': token_info.get('symbol', '???'),
                'decimals': 9,  # Standard for Solana SPL tokens
                'liquidity_usd': float(liquidity.get('usd', 0) or 0),
                'liquidity_sol': float(liquidity.get('quote', 0) or 0),  # Assuming quote is SOL
                'pool_address': main_pair.get('pairAddress', 'N/A'),
                'dex': main_pair.get('dexId', 'UNKNOWN'),
                'price_usd': float(main_pair.get('priceUsd', 0) or 0),
                'price_change_24h': float(price_change.get('h24', 0) or 0),
                'volume_24h': float(volume.get('h24', 0) or 0),
                'tx_24h': txns.get('h24', {}).get('buys', 0) + txns.get('h24', {}).get('sells', 0),
                'age_minutes': (time.time() - main_pair.get('pairCreatedAt', time.time())) / 60000 if main_pair.get('pairCreatedAt') else 0
            }
            
        except Exception as e:
            print(f"{Fore.RED}DexScreener API error: {e}")
            return None
    
    def _get_rpc_data(self, token_address: str) -> Optional[Dict]:
        """Get basic token data from Solana RPC."""
        try:
            # Get token supply
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [token_address]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'value' in data['result']:
                    decimals = data['result']['value'].get('decimals', 9)
                    return {
                        'decimals': decimals,
                        'state': 'DETECTED'
                    }
            
            return None
            
        except Exception as e:
            print(f"{Fore.RED}RPC error: {e}")
            return None
    
    def get_security_analysis(self, token_address: str) -> Dict:
        """
        Get security analysis for Solana token.
        
        Checks:
        - Liquidity adequacy
        - Holder distribution (if available)
        - Price volatility
        - Volume/Liquidity ratio
        """
        analysis = self.analyze_token(token_address)
        
        security_score = 100
        risk_flags = []
        
        # Check liquidity
        if analysis['liquidity_usd'] < 1000:
            security_score -= 30
            risk_flags.append("Very low liquidity")
        elif analysis['liquidity_usd'] < 10000:
            security_score -= 15
            risk_flags.append("Low liquidity")
        
        # Check if metadata resolved
        if not analysis['metadata_ok']:
            security_score -= 20
            risk_flags.append("Metadata not resolved")
        
        # Check if LP valid
        if not analysis['lp_valid']:
            security_score -= 20
            risk_flags.append("No valid liquidity pool found")
        
        # Check volume/liquidity ratio (should be reasonable)
        if analysis['liquidity_usd'] > 0:
            vol_liq_ratio = analysis['volume_24h'] / analysis['liquidity_usd']
            if vol_liq_ratio > 10:  # Very high turnover
                security_score -= 10
                risk_flags.append("Abnormally high volume/liquidity ratio")
        
        # Check price volatility
        if abs(analysis['price_change_24h']) > 100:  # >100% change
            security_score -= 10
            risk_flags.append("Extreme price volatility")
        
        return {
            'security_score': max(0, security_score),
            'risk_flags': risk_flags,
            'analysis': analysis
        }


# Example usage
if __name__ == "__main__":
    analyzer = ImprovedSolanaAnalyzer()
    
    # Test with a token
    token = "8bh8FWc1k8PowxVthwcojAfRuhUbND5FvarDfM86pump"
    
    result = analyzer.get_security_analysis(token)
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}ANALYSIS RESULT")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    analysis = result['analysis']
    
    print(f"{Fore.WHITE}Token: {Fore.CYAN}{analysis['name']} ({analysis['symbol']})")
    print(f"{Fore.WHITE}Address: {Fore.CYAN}{analysis['token_address']}")
    print(f"{Fore.WHITE}Pool: {Fore.CYAN}{analysis['pool_address']}")
    print(f"{Fore.WHITE}DEX: {Fore.CYAN}{analysis['dex']}")
    print(f"\n{Fore.WHITE}Liquidity: {Fore.CYAN}${analysis['liquidity_usd']:,.2f} ({analysis['liquidity_sol']:.2f} SOL)")
    print(f"{Fore.WHITE}Price: {Fore.CYAN}${analysis['price_usd']:.8f}")
    print(f"{Fore.WHITE}24h Change: {Fore.CYAN}{analysis['price_change_24h']:+.2f}%")
    print(f"{Fore.WHITE}24h Volume: {Fore.CYAN}${analysis['volume_24h']:,.2f}")
    print(f"{Fore.WHITE}24h Transactions: {Fore.CYAN}{analysis['tx_24h']}")
    
    print(f"\n{Fore.WHITE}Security Score: {Fore.CYAN}{result['security_score']}/100")
    
    if result['risk_flags']:
        print(f"\n{Fore.YELLOW}⚠️  Risk Flags:")
        for flag in result['risk_flags']:
            print(f"  • {Fore.YELLOW}{flag}")
    else:
        print(f"\n{Fore.GREEN}✅ No major risk flags detected")
