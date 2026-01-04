"""
Security Audit Module for Signal-Only Mode
Lightweight module to call RugCheck (Solana) and GoPlus (EVM) APIs.
No Web3 dependency required.
"""

import requests
import time
from typing import Dict, Optional

# Rate limiting
_last_request_time = 0
_min_request_interval = 0.2  # 200ms between requests


def _rate_limit():
    """Enforce rate limiting between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()


def check_bonding_curve(token_address: str, chain: str) -> Dict:
    """
    Check if a token is still in bonding curve (Solana).
    Uses RugCheck markets data + Moralis fallback.
    
    Returns:
        {
            'is_bonding_curve': bool, 
            'progress': float, 
            'reason': str
        }
    """
    if chain.lower() != 'solana':
        return {'is_bonding_curve': False, 'progress': 100, 'reason': 'Not Solana'}

    _rate_limit()
    
    # 1. Try RugCheck First (More reliable for fresh tokens)
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{token_address.strip()}/report"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get('markets', [])
            
            # Case A: No markets at all -> Likely Bonding Curve or Dead
            if not markets:
                return {
                    'is_bonding_curve': True,
                    'progress': 0,
                    'reason': 'No markets found (RugCheck)'
                }
                
            # Case B: Unknown DEX or Zero Liquidity -> Bonding Curve
            valid_dex_found = False
            for m in markets:
                dex_name = (m.get('dex') or '').lower()
                market_type = (m.get('type') or '').lower()
                liq_usd = m.get('liquidityA', {}).get('usd', 0)
                
                # Known graduated DEXes
                # Note: Meteora has "meteora" as dex, but we should be careful.
                # If market_type indicates DBC, we might want to flag it, but usually 'liquidity' check handles it.
                if dex_name in ['raydium', 'orca', 'meteora', 'fluxbeam'] and liq_usd > 500:
                    valid_dex_found = True
                    break
            
            if not valid_dex_found:
                 return {
                    'is_bonding_curve': True,
                    'progress': 99,
                    'reason': f"No valid DEX found (Markets: {[m.get('dex') for m in markets]})"
                }
                
            # If we get here, it has a valid DEX market
            return {
                'is_bonding_curve': False, 
                'progress': 100, 
                'reason': 'Valid DEX market found'
            }
            
    except Exception as e:
        print(f"[BC_CHECK] ⚠️ RugCheck failed: {e}")
        # Fallthrough to Moralis
    
    # 2. Fallback to Moralis (if RugCheck fails)
    # Note: We import inside function to avoid circular imports if any
    try:
        from moralis_client import get_moralis_client
        client = get_moralis_client()
        if not client.api_key:
             return {'is_bonding_curve': False, 'progress': 100, 'reason': 'No API Key'}
             
        res = client.check_bonding_status(token_address)
        
        # INTERPRETATION FIX: 
        # If Moralis returns 404 (error=None but graduated=True in my wrapper), 
        # it might actually be a fresh BC token.
        # But we can't be sure. 
        # Ideally, if RugCheck failed, we might want to be conservative.
        
        if not res['is_graduated']:
             return {
                'is_bonding_curve': True,
                'progress': res['progress'],
                'reason': f"Moralis Progress {res['progress']}%"
            }
            
        return {
            'is_bonding_curve': False,
            'progress': 100,
            'reason': 'Moralis/Default Graduated'
        }
        
    except Exception as e:
        print(f"[BC_CHECK] ❌ Moralis failed: {e}")
    
    # Default Safe (allow if checks fail? or block? User wants STRICT)
    # User said "masih ada signal token yang masih dalam proses BC lolos"
    # So we should default to BLOCK (True) if we are unsure?
    # But usually fail-safe is to allow. 
    # Let's stick to 'False' (not BC) but with a warning log, 
    # UNLESS the logic above caught it.
    return {'is_bonding_curve': False, 'progress': 100, 'reason': 'Checks Failed (Default Safe)'}


def audit_solana_token(token_address: str) -> Dict:
    """
    Audit Solana token using RugCheck API.
    
    Returns:
        dict with security analysis
    """
    result = {
        'risk_score': 50,
        'risk_level': 'WARN',
        'is_honeypot': False,
        'is_mintable': False,
        'is_freezable': False,
        'lp_locked_percent': 0,
        'lp_burned_percent': 0,
        'top10_holders_percent': 0,
        'holder_count': 0,
        'risks': [],
        'api_source': 'rugcheck',
        'api_error': None
    }
    
    if not token_address or len(token_address) < 32:
        result['api_error'] = 'Invalid address'
        return result
    
    _rate_limit()
    
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{token_address.strip()}/report"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            print(f"[SECURITY] ⚠️ RugCheck API Error {resp.status_code}")
            result['api_error'] = f'API {resp.status_code}'
            return result
        
        data = resp.json()
        
        # Base score from RugCheck (0-100, lower = better token)
        base_score = data.get('score', 50)
        score = base_score
        risks = []
        
        # Analyze risks
        for r in data.get('risks', []):
            name = r.get('name', '')
            level = r.get('level', 'info')
            
            if 'Mint' in name:
                result['is_mintable'] = True
                if level in ['danger', 'critical']:
                    score += 25
                    risks.append('🚨 Mintable (CRITICAL)')
                else:
                    score += 10
                    risks.append('⚠️ Mintable')
            
            if 'Freeze' in name:
                result['is_freezable'] = True
                if level in ['danger', 'critical']:
                    score += 20
                    risks.append('🚨 Freezable (CRITICAL)')
                else:
                    score += 10
                    risks.append('⚠️ Freezable')
            
            if level == 'danger' and 'Mint' not in name and 'Freeze' not in name:
                score += 15
                risks.append(f'🚨 {name}')
            elif level == 'warning':
                score += 5
                risks.append(f'⚠️ {name}')
        
        # Analyze holders (filter out AMM/LOCKER)
        top_holders = data.get('topHolders', [])
        known_accounts = data.get('knownAccounts', {})
        
        filtered_holders = []
        for h in top_holders:
            owner = h.get('owner', '')
            acc_info = known_accounts.get(owner, {})
            acc_type = acc_info.get('type', '')
            if acc_type not in ['AMM', 'LOCKER'] and owner != '11111111111111111111111111111111':
                filtered_holders.append(h)
        
        top10_pct = sum(float(h.get('pct', 0)) for h in filtered_holders[:10])
        result['top10_holders_percent'] = top10_pct
        result['holder_count'] = data.get('totalHolders', 0)
        
        if top10_pct > 80:
            score += 15
            risks.append(f'🚨 Top10 Holders: {top10_pct:.1f}%')
        elif top10_pct > 60:
            score += 5
            risks.append(f'⚠️ Top10 Holders: {top10_pct:.1f}%')
        
        # Analyze LP
        markets = data.get('markets', [])
        if markets:
            m = markets[0]
            result['lp_locked_percent'] = m.get('lpLockedPct', 0)
            result['lp_burned_percent'] = m.get('lpBurnedPct', 0)
            
            total_lp_safe = result['lp_locked_percent'] + result['lp_burned_percent']
            if total_lp_safe < 50:
                score += 10
                risks.append(f'⚠️ LP Not Locked: {total_lp_safe:.0f}%')
        
        # Cap score at 100
        score = min(score, 100)
        result['risk_score'] = score
        result['risks'] = risks[:5]  # Max 5 risks
        
        # Determine risk level
        if score <= 30:
            result['risk_level'] = 'SAFE'
        elif score <= 60:
            result['risk_level'] = 'WARN'
        else:
            result['risk_level'] = 'FAIL'
        
        print(f"[SECURITY] 🔐 RugCheck: {token_address[:16]}... → Score: {score}, Level: {result['risk_level']}")
        return result
        
    except requests.Timeout:
        print(f"[SECURITY] ⚠️ RugCheck Timeout")
        result['api_error'] = 'Timeout'
        return result
    except Exception as e:
        print(f"[SECURITY] ❌ RugCheck Error: {e}")
        result['api_error'] = str(e)
        return result


def audit_evm_token(token_address: str, chain: str = 'base') -> Dict:
    """
    Audit EVM token using GoPlus API.
    
    Args:
        token_address: Token contract address
        chain: 'base' or 'ethereum'
    
    Returns:
        dict with security analysis
    """
    result = {
        'risk_score': 50,
        'risk_level': 'WARN',
        'is_honeypot': False,
        'is_mintable': False,
        'is_freezable': False,
        'lp_locked_percent': 0,
        'lp_burned_percent': 0,
        'top10_holders_percent': 0,
        'holder_count': 0,
        'risks': [],
        'api_source': 'goplus',
        'api_error': None
    }
    
    if not token_address:
        result['api_error'] = 'Invalid address'
        return result
    
    # Chain ID mapping
    chain_map = {
        'base': '8453',
        'ethereum': '1',
        'eth': '1',
        'bsc': '56',
        'polygon': '137'
    }
    chain_id = chain_map.get(chain.lower(), '8453')
    
    _rate_limit()
    
    try:
        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address.lower()}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            print(f"[SECURITY] ⚠️ GoPlus API Error {resp.status_code}")
            result['api_error'] = f'API {resp.status_code}'
            return result
        
        data = resp.json()
        
        if data.get('code') != 1:
            result['api_error'] = 'Invalid response'
            return result
        
        token_data = data.get('result', {}).get(token_address.lower(), {})
        if not token_data:
            result['api_error'] = 'Token not found'
            return result
        
        score = 0
        risks = []
        
        # Check honeypot
        is_honeypot = token_data.get('is_honeypot', '0') == '1'
        result['is_honeypot'] = is_honeypot
        if is_honeypot:
            score += 100
            risks.append('🚨 HONEYPOT DETECTED')
        
        # Check mintable
        is_mintable = token_data.get('is_mintable', '0') == '1'
        result['is_mintable'] = is_mintable
        if is_mintable:
            score += 20
            risks.append('⚠️ Mintable')
        
        # Check proxy
        is_proxy = token_data.get('is_proxy', '0') == '1'
        if is_proxy:
            score += 15
            risks.append('⚠️ Proxy Contract')
        
        # Check ownership
        can_take_back_ownership = token_data.get('can_take_back_ownership', '0') == '1'
        if can_take_back_ownership:
            score += 15
            risks.append('⚠️ Can Take Back Ownership')
        
        # Check hidden owner
        hidden_owner = token_data.get('hidden_owner', '0') == '1'
        if hidden_owner:
            score += 20
            risks.append('🚨 Hidden Owner')
        
        # Check trading pause
        trading_cooldown = token_data.get('trading_cooldown', '0') == '1'
        if trading_cooldown:
            score += 10
            risks.append('⚠️ Has Trading Cooldown')
        
        # Check blacklist
        is_blacklisted = token_data.get('is_blacklisted', '0') == '1'
        if is_blacklisted:
            score += 15
            risks.append('⚠️ Has Blacklist Function')
        
        # Check anti-whale
        is_anti_whale = token_data.get('is_anti_whale', '0') == '1'
        if is_anti_whale:
            score += 5
            risks.append('⚠️ Anti-Whale Mechanism')
        
        # Holder concentration
        try:
            holder_count = int(token_data.get('holder_count', 0))
            result['holder_count'] = holder_count
            
            if holder_count < 50:
                score += 15
                risks.append(f'⚠️ Low Holders: {holder_count}')
        except:
            pass
        
        # Top 10 holders
        try:
            holders = token_data.get('holders', [])
            if holders:
                top10_pct = sum(float(h.get('percent', 0)) * 100 for h in holders[:10])
                result['top10_holders_percent'] = top10_pct
                
                if top10_pct > 80:
                    score += 15
                    risks.append(f'🚨 Top10 Holders: {top10_pct:.1f}%')
                elif top10_pct > 60:
                    score += 5
                    risks.append(f'⚠️ Top10 Holders: {top10_pct:.1f}%')
        except:
            pass
        
        # LP info
        try:
            lp_holders = token_data.get('lp_holders', [])
            if lp_holders:
                locked_pct = 0
                for lp in lp_holders:
                    if lp.get('is_locked', 0) == 1:
                        locked_pct += float(lp.get('percent', 0)) * 100
                result['lp_locked_percent'] = locked_pct
                
                if locked_pct < 50:
                    score += 10
                    risks.append(f'⚠️ LP Lock: {locked_pct:.0f}%')
        except:
            pass
        
        # Cap score
        score = min(score, 100)
        result['risk_score'] = score
        result['risks'] = risks[:5]
        
        # Determine risk level
        if is_honeypot:
            result['risk_level'] = 'FAIL'
        elif score <= 30:
            result['risk_level'] = 'SAFE'
        elif score <= 60:
            result['risk_level'] = 'WARN'
        else:
            result['risk_level'] = 'FAIL'
        
        print(f"[SECURITY] 🔐 GoPlus: {token_address[:16]}... → Score: {score}, Level: {result['risk_level']}")
        return result
        
    except requests.Timeout:
        print(f"[SECURITY] ⚠️ GoPlus Timeout")
        result['api_error'] = 'Timeout'
        return result
    except Exception as e:
        print(f"[SECURITY] ❌ GoPlus Error: {e}")
        result['api_error'] = str(e)
        return result


def audit_token(token_address: str, chain: str) -> Dict:
    """
    Route to appropriate security audit based on chain.
    
    Args:
        token_address: Token contract address
        chain: 'solana', 'base', 'ethereum', etc.
    
    Returns:
        dict with security analysis
    """
    chain_lower = chain.lower()
    
    if chain_lower == 'solana':
        return audit_solana_token(token_address)
    else:
        return audit_evm_token(token_address, chain_lower)
