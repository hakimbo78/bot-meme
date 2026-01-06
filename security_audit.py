"""
Security Audit Module for Signal-Only Mode
Lightweight module to call RugCheck (Solana) and GoPlus (EVM) APIs.
Fully Asynchronous (aiohttp) with Caching.
"""

import aiohttp
import asyncio
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Cache settings
_audit_cache = {}
CACHE_TTL = 1800  # 30 minutes

# Rate limiting (per process)
_last_request_time = 0
_min_request_interval = 0.2

async def _rate_limit():
    """Enforce rate limiting between requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _min_request_interval:
        await asyncio.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()

def _get_cache(key: str) -> Optional[Dict]:
    """Get from cache if valid."""
    if key in _audit_cache:
        timestamp, data = _audit_cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
        else:
            del _audit_cache[key]
    return None

def _set_cache(key: str, data: Dict):
    """Set cache with timestamp."""
    _audit_cache[key] = (time.time(), data)


# ============================================
# PHASE 2: CIRCUIT BREAKER & RETRY MECHANISM
# ============================================

class CircuitBreaker:
    """
    Circuit Breaker pattern for API resilience.
    Tracks failure rate and disables failing APIs temporarily.
    """
    def __init__(self, name: str, failure_threshold: float = 0.5, timeout: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.results = []  # Last 10 results (True/False)
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0
        self.alert_sent = False
    
    def record_success(self):
        """Record successful API call."""
        self.results.append(True)
        if len(self.results) > 10:
            self.results.pop(0)
        
        # If we were open and got success, close circuit
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.alert_sent = False
            print(f"[CIRCUIT] ✅ {self.name} recovered - Circuit CLOSED")
    
    def record_failure(self):
        """Record failed API call."""
        self.results.append(False)
        if len(self.results) > 10:
            self.results.pop(0)
        
        # Calculate failure rate
        if len(self.results) >= 5:  # Need at least 5 samples
            failure_rate = 1 - (sum(self.results) / len(self.results))
            
            if failure_rate >= self.failure_threshold and self.state == 'CLOSED':
                self.state = 'OPEN'
                self.last_failure_time = time.time()
                print(f"[CIRCUIT] 🔴 {self.name} failure rate {failure_rate:.0%} - Circuit OPEN")
                return True  # Signal to send alert
        
        return False
    
    def can_attempt(self) -> bool:
        """Check if API call is allowed."""
        if self.state == 'CLOSED':
            return True
        
        if self.state == 'OPEN':
            # Check if timeout elapsed
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = 'HALF_OPEN'
                print(f"[CIRCUIT] 🟡 {self.name} attempting recovery - Circuit HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN: Allow one test call
        return True


# Circuit breakers for each API
_rugcheck_breaker = CircuitBreaker('RugCheck', failure_threshold=0.6, timeout=300)
_goplus_breaker = CircuitBreaker('GoPlus', failure_threshold=0.6, timeout=300)

# Telegram notifier for alerts (lazy init)
_telegram_notifier = None

def set_telegram_notifier(notifier):
    """Set Telegram notifier for circuit breaker alerts."""
    global _telegram_notifier
    _telegram_notifier = notifier


async def _send_circuit_alert(api_name: str, state: str):
    """Send Telegram alert when circuit opens."""
    if _telegram_notifier:
        try:
            message = f"🔴 **SECURITY AUDIT ALERT**\n\n"
            message += f"API: {api_name}\n"
            message += f"Status: Circuit {state}\n"
            message += f"Impact: All tokens will be BLOCKED until API recovers\n"
            message += f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            await _telegram_notifier.send_message_async(message)
        except Exception as e:
            logger.error(f"Failed to send circuit alert: {e}")


async def _api_call_with_retry(session, url: str, max_retries: int = 3) -> Optional[Dict]:
    """
    Make API call with exponential backoff retry.
    Returns: JSON response or None if all retries fail.
    """
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                
                # Retryable errors (5xx server errors)
                if resp.status >= 500 and attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                    continue
                
                # Non-retryable (4xx client errors)
                return None
                
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
        
        except Exception as e:
            logger.warning(f"API call error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
    
    return None


async def check_bonding_curve(token_address: str, chain: str) -> Dict:
    """
    Check if a token is still in bonding curve (Solana).
    Uses RugCheck markets data + Moralis fallback.
    Async implementation.
    """
    if chain.lower() != 'solana':
        return {'is_bonding_curve': False, 'progress': 100, 'reason': 'Not Solana'}

    # 1. Try RugCheck First (More reliable for fresh tokens)
    try:
        await _rate_limit()
        url = f"https://api.rugcheck.xyz/v1/tokens/{token_address.strip()}/report"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
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
                        
                        if dex_name in ['raydium', 'orca', 'meteora', 'fluxbeam'] and liq_usd > 500:
                            valid_dex_found = True
                            break
                    
                    if not valid_dex_found:
                         return {
                            'is_bonding_curve': True,
                            'progress': 99,
                            'reason': f"No valid DEX found (Markets: {[m.get('dex') for m in markets]})"
                        }
                    
                    return {
                        'is_bonding_curve': False, 
                        'progress': 100, 
                        'reason': 'Valid DEX market found'
                    }
                    
    except Exception as e:
        logger.warning(f"[BC_CHECK] ⚠️ RugCheck failed: {e}")
        # Fallthrough to Moralis
    
    # 2. Fallback to Moralis (if RugCheck fails)
    # Keeping Moralis sync for now as it uses library, but it's rarely used if RugCheck works.
    # To prevent blocking, run in executor if possible, or just accept small block.
    # Ideally should move Moralis to async too, but keeping it simple for now.
    try:
        from moralis_client import get_moralis_client
        client = get_moralis_client()
        if not client.api_key:
             return {'is_bonding_curve': False, 'progress': 100, 'reason': 'No API Key'}
             
        # Run sync call in thread pool to avoid blocking loop
        res = await asyncio.to_thread(client.check_bonding_status, token_address)
        
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
        logger.error(f"[BC_CHECK] ❌ Moralis failed: {e}")
    
    return {'is_bonding_curve': False, 'progress': 100, 'reason': 'Checks Failed (Default Safe)'}


async def audit_solana_token(token_address: str) -> Dict:
    """
    Audit Solana token using RugCheck API (Async with Circuit Breaker).
    """
    cache_key = f"solana_{token_address}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    result = {
        'risk_score': 50, 'risk_level': 'WARN', 'is_honeypot': False, 'is_mintable': False,
        'is_freezable': False, 'lp_locked_percent': 0, 'lp_burned_percent': 0,
        'top10_holders_percent': 0, 'holder_count': 0, 'risks': [],
        'api_source': 'rugcheck', 'api_error': None
    }
    
    if not token_address or len(token_address) < 32:
        result['api_error'] = 'Invalid address'
        return result
    
    # PHASE 2: Circuit Breaker Check
    if not _rugcheck_breaker.can_attempt():
        result['api_error'] = 'Circuit OPEN (API Down)'
        result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe mode
        result['risks'] = ['⛔ Security audit unavailable (RugCheck down)']
        print(f"[SECURITY] ⛔ RugCheck circuit OPEN - Blocking token")
        return result
    
    await _rate_limit()
    
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{token_address.strip()}/report"
        
        async with aiohttp.ClientSession() as session:
            # PHASE 2: Use retry mechanism
            data = await _api_call_with_retry(session, url)
            
            if not data:
                # Record failure
                should_alert = _rugcheck_breaker.record_failure()
                if should_alert and not _rugcheck_breaker.alert_sent:
                    await _send_circuit_alert('RugCheck', 'OPEN')
                    _rugcheck_breaker.alert_sent = True
                
                result['api_error'] = 'API call failed after retries'
                result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe
                result['risks'] = ['⛔ Security audit failed (RugCheck timeout)']
                print(f"[SECURITY] ⚠️ RugCheck failed after retries")
                return result
            
            # Record success
            _rugcheck_breaker.record_success()
            
            # Base score from RugCheck
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
            
            # Analyze holders
            top_holders = data.get('topHolders', [])
            known_accounts = data.get('knownAccounts', {})
            filtered_holders = [
                h for h in top_holders 
                if known_accounts.get(h.get('owner', ''), {}).get('type', '') not in ['AMM', 'LOCKER']
                and h.get('owner') != '11111111111111111111111111111111'
            ]
            
            top10_pct = sum(float(h.get('pct', 0)) for h in filtered_holders[:10])
            result['top10_holders_percent'] = top10_pct
            result['holder_count'] = data.get('totalHolders', 0)
            
            if top10_pct > 80: score += 15; risks.append(f'🚨 Top10: {top10_pct:.1f}%')
            elif top10_pct > 60: score += 5; risks.append(f'⚠️ Top10: {top10_pct:.1f}%')
            
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
            
            score = min(score, 100)
            result['risk_score'] = score
            result['risks'] = risks[:5]
            
            if score <= 30: result['risk_level'] = 'SAFE'
            elif score <= 60: result['risk_level'] = 'WARN'
            else: result['risk_level'] = 'FAIL'
            
            print(f"[SECURITY] 🔐 RugCheck: {token_address[:16]}... → Score: {score}, Level: {result['risk_level']}")
            _set_cache(cache_key, result)
            return result
                
    except Exception as e:
        # Record failure
        should_alert = _rugcheck_breaker.record_failure()
        if should_alert and not _rugcheck_breaker.alert_sent:
            await _send_circuit_alert('RugCheck', 'OPEN')
            _rugcheck_breaker.alert_sent = True
        
        print(f"[SECURITY] ❌ RugCheck Error: {e}")
        result['api_error'] = str(e)
        result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe
        result['risks'] = ['⛔ Security audit error']
        return result


async def audit_evm_token(token_address: str, chain: str = 'base') -> Dict:
    """
    Audit EVM token using GoPlus API (Async with Circuit Breaker).
    """
    cache_key = f"{chain}_{token_address}"
    cached = _get_cache(cache_key)
    if cached:
        return cached

    result = {
        'risk_score': 50, 'risk_level': 'WARN', 'is_honeypot': False, 'is_mintable': False,
        'is_freezable': False, 'lp_locked_percent': 0, 'lp_burned_percent': 0,
        'top10_holders_percent': 0, 'holder_count': 0, 'risks': [],
        'api_source': 'goplus', 'api_error': None
    }
    
    if not token_address:
        result['api_error'] = 'Invalid address'
        return result
    
    # PHASE 2: Circuit Breaker Check
    if not _goplus_breaker.can_attempt():
        result['api_error'] = 'Circuit OPEN (API Down)'
        result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe mode
        result['risks'] = ['⛔ Security audit unavailable (GoPlus down)']
        print(f"[SECURITY] ⛔ GoPlus circuit OPEN - Blocking token")
        return result
    
    chain_map = {'base': '8453', 'ethereum': '1', 'eth': '1', 'bsc': '56', 'polygon': '137'}
    chain_id = chain_map.get(chain.lower(), '8453')
    
    await _rate_limit()
    
    try:
        url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address.lower()}"
        
        async with aiohttp.ClientSession() as session:
            # PHASE 2: Use retry mechanism
            data = await _api_call_with_retry(session, url)
            
            if not data or data.get('code') != 1:
                # Record failure
                should_alert = _goplus_breaker.record_failure()
                if should_alert and not _goplus_breaker.alert_sent:
                    await _send_circuit_alert('GoPlus', 'OPEN')
                    _goplus_breaker.alert_sent = True
                
                result['api_error'] = 'API call failed after retries'
                result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe
                result['risks'] = ['⛔ Security audit failed (GoPlus timeout)']
                print(f"[SECURITY] ⚠️ GoPlus failed after retries")
                return result
            
            token_data = data.get('result', {}).get(token_address.lower(), {})
            if not token_data:
                _goplus_breaker.record_failure()
                result['api_error'] = 'Token not found'
                result['risk_level'] = 'FAIL'
                result['risks'] = ['⛔ Token not found in GoPlus']
                return result
            
            # Record success
            _goplus_breaker.record_success()
            
            score = 0
            risks = []
            
            is_honeypot = token_data.get('is_honeypot', '0') == '1'
            result['is_honeypot'] = is_honeypot
            if is_honeypot: score += 100; risks.append('🚨 HONEYPOT DETECTED')
            
            if token_data.get('is_mintable', '0') == '1':
                result['is_mintable'] = True; score += 20; risks.append('⚠️ Mintable')
            if token_data.get('is_proxy', '0') == '1':
                score += 15; risks.append('⚠️ Proxy Contract')
            if token_data.get('can_take_back_ownership', '0') == '1':
                score += 15; risks.append('⚠️ Can Take Back Ownership')
            if token_data.get('hidden_owner', '0') == '1':
                score += 20; risks.append('🚨 Hidden Owner')
            if token_data.get('trading_cooldown', '0') == '1':
                score += 10; risks.append('⚠️ Has Trading Cooldown')
            if token_data.get('is_blacklisted', '0') == '1':
                score += 15; risks.append('⚠️ Has Blacklist Function')
            if token_data.get('is_anti_whale', '0') == '1':
                score += 5; risks.append('⚠️ Anti-Whale Mechanism')
            
            # Check holders
            try:
                result['holder_count'] = int(token_data.get('holder_count', 0))
                if result['holder_count'] < 50: score += 15; risks.append(f"⚠️ Low Holders: {result['holder_count']}")
            except: pass
            
            try:
                holders = token_data.get('holders', [])
                if holders:
                    top10 = sum(float(h.get('percent', 0)) * 100 for h in holders[:10])
                    result['top10_holders_percent'] = top10
                    if top10 > 80: score += 15; risks.append(f'🚨 Top10: {top10:.1f}%')
                    elif top10 > 60: score += 5; risks.append(f'⚠️ Top10: {top10:.1f}%')
            except: pass
            
            # Check LP
            try:
                locked_pct = 0
                for lp in token_data.get('lp_holders', []):
                    if lp.get('is_locked', 0) == 1: locked_pct += float(lp.get('percent', 0)) * 100
                result['lp_locked_percent'] = locked_pct
                if locked_pct < 50: score += 10; risks.append(f'⚠️ LP Lock: {locked_pct:.0f}%')
            except: pass
            
            score = min(score, 100)
            result['risk_score'] = score
            result['risks'] = risks[:5]
            
            if is_honeypot: result['risk_level'] = 'FAIL'
            elif score <= 30: result['risk_level'] = 'SAFE'
            elif score <= 60: result['risk_level'] = 'WARN'
            else: result['risk_level'] = 'FAIL'
            
            print(f"[SECURITY] 🔐 GoPlus: {token_address[:16]}... → Score: {score}, Level: {result['risk_level']}")
            _set_cache(cache_key, result)
            return result

    except Exception as e:
        # Record failure
        should_alert = _goplus_breaker.record_failure()
        if should_alert and not _goplus_breaker.alert_sent:
            await _send_circuit_alert('GoPlus', 'OPEN')
            _goplus_breaker.alert_sent = True
        
        print(f"[SECURITY] ❌ GoPlus Error: {e}")
        result['api_error'] = str(e)
        result['risk_level'] = 'FAIL'  # OPTION B: Fail-safe
        result['risks'] = ['⛔ Security audit error']
        return result


async def audit_token(token_address: str, chain: str) -> Dict:
    """Route to appropriate async security audit."""
    if chain.lower() == 'solana':
        return await audit_solana_token(token_address)
    else:
        return await audit_evm_token(token_address, chain.lower())
