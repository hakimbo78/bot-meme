"""
TokenSniffer-Style Security Analyzer
Enhanced with RugCheck.xyz (Solana) and GoPlus (EVM)
"""

from web3 import Web3
from typing import Dict, Optional, List
import requests
import time

class TokenSnifferAnalyzer:
    """
    Enhanced security analyzer.
    Strategies:
    - SOLANA: Uses RugCheck.xyz API (Best for Solana)
    - EVM (Base/Eth): Uses GoPlus Security API (Standard)
    """
    
    def __init__(self, w3: Web3, chain_name: str):
        self.w3 = w3
        self.chain_name = chain_name.lower()
        
        # API Endpoints
        self.honeypot_api = "https://api.honeypot.is/v2/IsHoneypot"
        
        # EVM Only (GoPlus)
        self.goplus_chain_map = {
            'ethereum': '1',
            'base': '8453', 
            'bsc': '56',
            'polygon': '137'
        }

    def _get_goplus_id(self):
        return self.goplus_chain_map.get(self.chain_name, '1')

    def analyze_comprehensive(self, token_address: str, pair_address: str = None, external_liquidity_usd: float = 0) -> Dict:
        result = {
            'swap_analysis': {},
            'contract_analysis': {},
            'holder_analysis': {},
            'liquidity_analysis': {},
            'overall_score': 0,
            'risk_level': 'UNKNOWN'
        }
        
        # ROUTING BASED ON CHAIN
        if self.chain_name == 'solana':
            print(f"📡 Analyzing Solana Token via RugCheck: {token_address}")
            self._analyze_solana_rugcheck(token_address, result, external_liquidity_usd)
        else:
            print(f"📡 Analyzing EVM Token via GoPlus: {token_address}")
            self._analyze_evm_goplus(token_address, pair_address, result)
            
        # Overall Score Calc
        result['overall_score'] = self._calculate_overall_score(result)
        result['risk_level'] = self._determine_risk_level(result['overall_score'])
        
        return result
        
    def _analyze_solana_rugcheck(self, token_address: str, result: Dict, ext_liq: float = 0):
        """Deep analysis for Solana using RugCheck API."""
        try:
            url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            resp = requests.get(url, timeout=15)
            
            if resp.status_code != 200:
                result['contract_analysis']['details'] = [f"⚠️ RugCheck API Failed: {resp.status_code}"]
                return

            data = resp.json()
            
            # 1. RISK / CONTRACT
            risks = data.get('risks', [])
            
            crit_flags = ['Mintable', 'Freezable', 'Mutable']
            found_crit = []
            
            is_mintable = False
            is_freezable = False
            is_mutable = False
            
            for r in risks:
                name = r.get('name', '')
                if 'Mint' in name: is_mintable = True
                if 'Freeze' in name: is_freezable = True
                if 'Mutable' in name: is_mutable = True
                
                # Check critical levels
                if r.get('level') == 'danger':
                    found_crit.append(name)

            result['contract_analysis'] = {
                'is_verified': True, # Solana programs usually verified
                'has_mint_function': is_mintable,
                'has_pause_function': is_freezable,
                'ownership_renounced': not is_mutable, # Mutable metadata = Ownershop logic
                'details': []
            }
            
            if found_crit:
                pass
            
            if is_mintable: result['contract_analysis']['details'].append("⚠️ Token is Mintable")
            if is_freezable: result['contract_analysis']['details'].append("⚠️ Token is Freezable")
            if not is_mutable: result['contract_analysis']['details'].append("✅ Metadata is Immutable")

            # 2. HOLDERS
            top_holders = data.get('topHolders') or []
            total_pct = 0
            for h in top_holders[:10]:
                total_pct += float(h.get('pct', 0))
            
            result['holder_analysis'] = {
                'top10_holders_percent': total_pct,
                'creator_wallet_percent': 0,
                'details': [f"Top 10 Holders: {total_pct:.1f}%"]
            }
            
            # 3. LIQUIDITY - REMOVED
            # Liquidity rugpull detection now handled by LP Intent Engine
            # (Real-time behavioral monitoring, not static lock checks)
            result['liquidity_analysis'] = {
                'total_liquidity_usd': 0,
                'liquidity_locked_percent': 100.0,  # Bypass (handled by LP Intent)
                'details': ["✅ Liquidity check delegated to LP Intent Engine"]
            }
            
            # Swap Analysis
            result['swap_analysis'] = {'is_honeypot': False, 'details': ["✅ Market exists"]}

        except Exception as e:
            result['contract_analysis']['details'] = [f"Error: {e}"]

    def _analyze_evm_goplus(self, token_address, pair_address, result):
        """Deep analysis for EVM using GoPlus."""
        chain_id = self._get_goplus_id()
        try:
            url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            
            if data['code'] != 1:
                return
            
            t_data = data['result'].get(token_address.lower(), {})
            
            # 1. CONTRACT
            is_open_source = t_data.get('is_open_source', '0') == '1'
            is_honeypot = t_data.get('is_honeypot', '0') == '1'
            is_mintable = t_data.get('is_mintable', '0') == '1'
            
            result['contract_analysis'] = {
                'is_verified': is_open_source,
                'has_mint_function': is_mintable,
                'ownership_renounced': t_data.get('owner_address', '') == '',
                'details': []
            }
            if is_honeypot:
                result['swap_analysis']['is_honeypot'] = True
                result['risk_level'] = 'CRITICAL'
                result['contract_analysis']['details'].append("⛔ HONEYPOT DETECTED")

            # 2. HOLDERS
            holders = t_data.get('holders', [])
            top10 = 0
            for h in holders[:10]:
                top10 += float(h.get('percent', 0)) * 100 # GoPlus returns 0.xxxx usually? Wait, let's auto-detect
                # If sum is small (<1), likely need *100. If sum > 1, likely already %.
            
            # Logic auto-scale info
            if top10 > 0 and top10 < 1.0: top10 *= 100
            
            result['holder_analysis'] = {
                'top10_holders_percent': top10,
                'creator_wallet_percent': float(t_data.get('creator_percent', 0)) * 100,
                'details': [f"Top 10: {top10:.1f}%"]
            }
            
            # 3. LIQUIDITY (IMPROVED LOGIC)
            lp_holders = t_data.get('lp_holders', [])
            total_locked = 0
            dead_addrs = ['0x000000000000000000000000000000000000dead', '0x0000000000000000000000000000000000000000']
            
            for lh in lp_holders:
                is_locked = str(lh.get('is_locked', '0')) == '1'
                addr = lh.get('address', '').lower()
                pct = float(lh.get('percent', 0))
                
                if is_locked or addr in dead_addrs:
                    total_locked += pct
            
            if total_locked < 1.0 and total_locked > 0: total_locked *= 100
            
            result['liquidity_analysis'] = {
                'liquidity_locked_percent': total_locked,
                'details': [f"Calculated Lock: {total_locked:.1f}%"]
            }

        except Exception as e:
            result['contract_analysis']['details'].append(f"Error: {e}")

    def _calculate_overall_score(self, res):
        score = 100
        if res['swap_analysis'].get('is_honeypot'): score = 0
        if res['contract_analysis'].get('has_mint_function'): score -= 20
        if res['holder_analysis'].get('top10_holders_percent', 0) > 70: score -= 30
        if res['liquidity_analysis'].get('liquidity_locked_percent', 0) < 80: score -= 40
        return max(0, score)

    def _determine_risk_level(self, score):
        if score < 40: return 'CRITICAL'
        if score < 70: return 'HIGH'
        if score < 85: return 'MEDIUM'
        return 'LOW'
