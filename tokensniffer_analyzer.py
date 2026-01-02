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

    from offchain_config import DEGEN_SNIPER_CONFIG
    
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
        
    def _check_bonding_curve_status(self, data: Dict) -> tuple:
        """
        Detect bonding curve status for Pump.fun and Meteora tokens.
        Returns: (is_bonding_curve, completion_pct, platform, dex_pools)
        """
        markets = data.get('markets', [])
        
        # DEBUG
        print(f"   [BC DEBUG] Checking {len(markets)} markets")
        
        bonding_curve_market = None
        platform = 'none'
        dex_pools = []
        # Default to 100% if NO BC detected (so we don't block normal tokens)
        # But if BC IS detected, we will reset this to 0.0 inside the loop logic
        completion_pct = 100.0
        
        for market in markets:
            # FIX: Force lowercase for robust matching
            mtype = market.get('marketType', '').lower()
            print(f"   [BC DEBUG] Market type: {mtype}")
            
            # PRIMARY: Pump.fun bonding curve (most common)
            # HANDLES: pump_fun_amm AND pump_fun (both variations seen in production)
            if mtype in ['pump_fun_amm', 'pump_fun', 'pumpfun']:
                bonding_curve_market = market
                platform = 'pump_fun'
                
                # Default to 0.0 for detected BC (Safe Default)
                # If calculations fail/data missing, we assume incomplete -> BLOCK
                current_completion = 0.0
                
                # Calculate completion for Pump.fun
                lp = market.get('lp', {})
                current = float(lp.get('lpCurrentSupply', 0))
                total = float(lp.get('lpTotalSupply', 0))
                
                if total > 0:
                    current_completion = (current / total) * 100
                
                # Update main completion_pct only if we found a valid calculation
                # Or force it to 0 if it's the first BC we found
                if completion_pct == 100.0: # Resetting the global default
                     completion_pct = current_completion
                else:
                     completion_pct = max(completion_pct, current_completion)
                     
                print(f"   [BC DEBUG] PUMP.FUN BC: {completion_pct:.1f}%")
            
            
            
            # SECONDARY: Meteora Dynamic BC
            # NOTE: Meteora BC has lpTotalSupply=0, so we detect by marketType + risk indicators
            elif mtype in ['meteora_damm_v2', 'meteora_dbc']:
                print(f"   [BC DEBUG] Meteora BC ({mtype}) detected")
                
                # meteora_dbc = Dynamic Bonding Curve (IS a BC by definition!)
                # meteora_damm_v2 = Dynamic AMM (check risks to confirm if BC phase)
                is_meteora_bc = False
                
                if mtype == 'meteora_dbc':
                    # DBC = always a bonding curve
                    is_meteora_bc = True
                    print(f"   [BC DEBUG] meteora_dbc confirmed (BC by definition)")
                else:
                    # DAMM v2 - check risks to confirm BC phase
                    risks = data.get('risks', [])
                    print(f"   [BC DEBUG] meteora_damm_v2 - checking {len(risks)} risks")
                    
                    has_unlocked_lp_risk = any(
                        'LP Unlocked' in risk.get('name', '') or 
                        'Low amount of LP Providers' in risk.get('name', '')
                        for risk in risks
                    )
                    
                    print(f"   [BC DEBUG] Has unlocked LP risk: {has_unlocked_lp_risk}")
                    is_meteora_bc = has_unlocked_lp_risk
                
                # If confirmed as Meteora BC
                if is_meteora_bc:
                    bonding_curve_market = market
                    platform = 'meteora_bc'
                    
                    # For Meteora, estimate completion based on liquidity vs typical BC threshold
                    # Typical Meteora BC completes around $69K-85K liquidity
                    lp = market.get('lp', {})
                    total_liq_usd = float(lp.get('quoteUSD', 0)) + float(lp.get('baseUSD', 0))
                    
                    current_completion = 0.0
                    
                    if total_liq_usd > 0:
                        # Estimate: 85K = 100% completion
                        current_completion = min(100.0, (total_liq_usd / 85000) * 100)
                    
                    # Reset global default if needed
                    if completion_pct == 100.0: 
                        completion_pct = current_completion
                    else:
                        completion_pct = max(completion_pct, current_completion)
                        
                    print(f"   [BC DEBUG] METEORA BC: ${total_liq_usd:,.0f} = {completion_pct:.1f}%")
            
            
            
            # Track DEX pools (post-graduation)
            elif mtype in ['raydium_clmm', 'raydium_amm', 'orca_whirlpool']:
                dex_pools.append(market)
        
        # Return BC status
        if bonding_curve_market:
            print(f"   [BC DEBUG] DETECTED: {platform} at {completion_pct:.1f}%")
            return True, completion_pct, platform, dex_pools
        
        print(f"   [BC DEBUG] NO BC DETECTED")
        return False, 100.0, platform, dex_pools
    
    
    def _analyze_solana_rugcheck(self, token_address: str, result: Dict, ext_liq: float = 0):
        """Deep analysis for Solana using RugCheck API with SCORE-BASED detection."""
        try:
            url = f"https://api.rugcheck.xyz/v1/tokens/{token_address}/report"
            resp = requests.get(url, timeout=15)
            
            if resp.status_code != 200:
                result['contract_analysis']['details'] = [f"⚠️ RugCheck API Failed: {resp.status_code}"]
                result['risk_score'] = 50  # Moderate risk if can't verify
                result['risk_level'] = 'WARN'
                return

            data = resp.json()
            
            # START SCORE-BASED CALCULATION
            # Base score from RugCheck (0-100, lower = better)
            base_score = data.get('score', 50)
            
            # Our enhanced score starts from RugCheck
            score = base_score
            details = []

            # 0. MIN HOLDERS CHECK (From Config)
            min_holders = self.DEGEN_SNIPER_CONFIG.get('global_guardrails', {}).get('quality_check', {}).get('min_holders', 50)
            total_holders_cnt = data.get('totalHolders', 0)
            
            if total_holders_cnt < min_holders:
                score += 50
                details.append(f"🚨 TOO FEW HOLDERS: {total_holders_cnt} < {min_holders}")
            
            # 1. CRITICAL RISK CHECKS
            risks = data.get('risks', [])
            is_mintable = False
            is_freezable = False
            is_mutable = False
            
            for r in risks:
                name = r.get('name', '')
                level = r.get('level', 'info')
                
                # Check specific risks
                if 'Mint' in name:
                    is_mintable = True
                    if level in ['danger', 'critical']:
                        score += 30  # Major penalty
                        details.append("🚨 Mintable (CRITICAL)")
                    else:
                        score += 15
                        details.append("⚠️ Mintable")
                        
                if 'Freeze' in name:
                    is_freezable = True
                    if level in ['danger', 'critical']:
                        score += 25
                        details.append("🚨 Freezable (CRITICAL)")
                    else:
                        score += 10
                        details.append("⚠️ Freezable")
                        
                if 'Mutable' in name:
                    is_mutable = True
                    score += 5
                    details.append("⚠️ Mutable Metadata")
                
                # Add penalty for other critical/danger risks
                if level == 'danger' and 'Mint' not in name and 'Freeze' not in name:
                    score += 15
                    details.append(f"🚨 {name}")
                elif level == 'warning':
                    score += 5
                    details.append(f"⚠️ {name}")
            
            # 2. HOLDER CONCENTRATION (FIXED: Filter out AMM/LOCKERs)
            top_holders = data.get('topHolders') or []
            known_accounts = data.get('knownAccounts', {})
            
            # Filter out non-holder addresses (AMM pools, LOCKERs, etc)
            filtered_holders = []
            for h in top_holders:
                owner = h.get('owner', '')
                acc_info = known_accounts.get(owner, {})
                acc_type = acc_info.get('type', '')
                
                # Skip if this is an AMM pool, LOCKER, or burn address
                if acc_type in ['AMM', 'LOCKER'] or owner == '11111111111111111111111111111111':
                    continue
                    
                filtered_holders.append(h)
            
            # Calculate Top 10 from REAL holders only
            top10_pct = sum(float(h.get('pct', 0)) for h in filtered_holders[:10])
            
            if top10_pct > 90:
                score += 25
                details.append(f"🚨 Top 10 Holders: {top10_pct:.1f}% (Extreme)")
            elif top10_pct > 80:
                score += 15
                details.append(f"⚠️ Top 10 Holders: {top10_pct:.1f}% (High)")
            elif top10_pct > 70:
                score += 10
                details.append(f"⚠️ Top 10 Holders: {top10_pct:.1f}%")
            elif top10_pct > 60:
                score += 5
                details.append(f"📊 Top 10 Holders: {top10_pct:.1f}%")
            else:
                details.append(f"✅ Top 10 Holders: {top10_pct:.1f}% (Distributed)")
            
            # 3. LP LOCK/BURN BONUS (FIXED: Correct path to lp data)
            markets = data.get('markets', [])
            if markets:
                # Access nested lp object (CORRECT path)
                lp_data = markets[0].get('lp', {})
                lp_locked = float(lp_data.get('lpLockedPct', 0))
                lp_burned = float(lp_data.get('lpBurnedPct', 0))  # Usually 0 for Pump.fun
                total_secure = lp_locked + lp_burned
                
                if total_secure >= 90:
                    score = max(0, score - 20)  # Big bonus!
                    details.append(f"✅ LP Secured: {total_secure:.1f}% (Excellent)")
                elif total_secure >= 70:
                    score = max(0, score - 15)
                    details.append(f"✅ LP Secured: {total_secure:.1f}% (Good)")
                elif total_secure >= 50:
                    score = max(0, score - 10)
                    details.append(f"📊 LP Secured: {total_secure:.1f}%")
                elif total_secure > 0:
                    details.append(f"⚠️ LP Secured: {total_secure:.1f}% (Low)")
                else:
                    score += 10
                    details.append(f"🚨 LP Not Secured (0%)")
            
            # 4. BONDING CURVE DETECTION & RISK SCORING (NEW)
            is_bc, completion, platform, dex_pools = self._check_bonding_curve_status(data)
            
            print(f"   [BC BLOCK CHECK] is_bc={is_bc}, completion={completion:.1f}%, platform={platform}")
            
            if is_bc and completion < 100:
                # POLICY: WAIT FOR GRADUATION - Block ALL BC tokens
                score += 100  # Auto-block
                details.append(f"⛔ {platform.upper()} Bonding Curve {completion:.1f}% - WAITING FOR GRADUATION")
                print(f"   [BC BLOCK] BLOCKED! Score +100")
                
                # Store BC info for bypass tracking (will be used by deduplicator)
                result['bonding_curve_status'] = {
                    'in_curve': True,
                    'completion': completion,
                    'platform': platform
                }
            
            
            elif completion >= 100 and len(dex_pools) > 0:
                # POST-GRADUATION: Check LP lock AND liquidity size
                lp_locked_on_dex = False
                dex_lp_pct = 0
                max_dex_liq_usd = 0
                
                # Minimum DEX liquidity requirement (prevent micro-liq scams)
                MIN_DEX_LIQUIDITY_USD = 10000
                
                for dex_pool in dex_pools:
                    dex_lp = dex_pool.get('lp', {})
                    dex_lock = float(dex_lp.get('lpLockedPct', 0))
                    
                    # Calculate total DEX liquidity in USD
                    quote_usd = float(dex_lp.get('quoteUSD', 0))
                    base_usd = float(dex_lp.get('baseUSD', 0))
                    total_liq_usd = quote_usd + base_usd
                    
                    # Track max liquidity across all DEX pools
                    if total_liq_usd > max_dex_liq_usd:
                        max_dex_liq_usd = total_liq_usd
                    
                    # Check both LP lock % AND liquidity amount
                    if dex_lock >= 90 and total_liq_usd >= MIN_DEX_LIQUIDITY_USD:
                        lp_locked_on_dex = True
                        dex_lp_pct = dex_lock
                        break
                
                if lp_locked_on_dex:
                    details.append(f"✅ Post-Graduation: LP Locked {dex_lp_pct:.1f}% on DEX (${max_dex_liq_usd:,.0f})")
                elif max_dex_liq_usd < MIN_DEX_LIQUIDITY_USD:
                    # CRITICAL: Micro liquidity scam
                    score += 50
                    details.append(f"🚨 POST-GRADUATION: Micro Liquidity (${max_dex_liq_usd:,.0f} < ${MIN_DEX_LIQUIDITY_USD:,.0f})")
                else:
                    # CRITICAL: LP not locked after graduation
                    score += 50
                    details.append(f"🚨 POST-GRADUATION: LP NOT LOCKED ({dex_lp_pct:.1f}%) - RUGPULL RISK")
            
            # 5. FINALIZE SCORE
            final_score = min(100, max(0, score))
            risk_level = self._determine_risk_level(final_score)
            
            # Store results
            result['risk_score'] = final_score
            result['risk_level'] = risk_level
            result['contract_analysis'] = {
                'is_verified': True,
                'has_mint_function': is_mintable,
                'has_pause_function': is_freezable,
                'ownership_renounced': not is_mutable,
                'details': details
            }
            result['holder_analysis'] = {
                'top10_holders_percent': top10_pct,
                'creator_wallet_percent': 0,
                'details': []
            }
            result['liquidity_analysis'] = {
                'total_liquidity_usd': 0,
                'liquidity_locked_percent': 100.0,
                'details': ["✅ Liquidity delegated to LP Intent Engine"]
            }
            result['swap_analysis'] = {
                'is_honeypot': False,
                'details': ["✅ Market exists"]
            }
            
            # Add score summary
            details.insert(0, f"📊 RugCheck Base Score: {base_score}")
            details.insert(1, f"📊 Final Risk Score: {final_score}/100 ({risk_level})")

        except Exception as e:
            result['contract_analysis']['details'] = [f"Error: {e}"]
            result['risk_score'] = 50
            result['risk_level'] = 'WARN'

    def _analyze_evm_goplus(self, token_address, pair_address, result):
        """Deep analysis for EVM using GoPlus with SCORE-BASED detection."""
        chain_id = self._get_goplus_id()
        try:
            url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={token_address}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            
            if data['code'] != 1:
                result['contract_analysis']['details'] = [f"⚠️ GoPlus API Error: {data.get('message')}"]
                result['risk_score'] = 50
                result['risk_level'] = 'WARN'
                return
            
            t_data = data['result'].get(token_address.lower(), {})
            
            # START SCORING (0-100)
            score = 0
            details = []
            
            # 0. MIN HOLDERS CHECK (From Config)
            min_holders = self.DEGEN_SNIPER_CONFIG.get('global_guardrails', {}).get('quality_check', {}).get('min_holders', 50)
            holder_count = int(t_data.get('holder_count', 0))

            if holder_count < min_holders:
                score += 50
                details.append(f"⛔ TOO FEW HOLDERS: {holder_count} < {min_holders}")

            # 1. HONEYPOT & CRITICAL (Base Score)
            is_honeypot = str(t_data.get('is_honeypot', '0')) == '1'
            if is_honeypot:
                score += 100
                details.append("⛔ HONEYPOT DETECTED (CRITICAL)")
            
            # 2. TRADING RESTRICTIONS
            cannot_buy = str(t_data.get('cannot_buy', '0')) == '1'
            cannot_sell_all = str(t_data.get('cannot_sell_all', '0')) == '1'
            
            if cannot_buy:
                score += 20
                details.append("🚨 Cannot Buy")
            if cannot_sell_all:
                score += 20
                details.append("🚨 Cannot Sell All")
                
            # 3. CONTRACT RISK
            is_proxy = str(t_data.get('is_proxy', '0')) == '1'
            is_mintable = str(t_data.get('is_mintable', '0')) == '1'
            external_call = str(t_data.get('external_call', '0')) == '1'
            
            if is_proxy:
                score += 10
                details.append("⚠️ Proxy Contract")
            if is_mintable:
                score += 10
                details.append("⚠️ Mintable")
            if external_call:
                score += 5
                details.append("⚠️ External Calls")
                
            # 4. HOLDER CONCENTRATION
            holders = t_data.get('holders', [])
            top10 = 0
            for h in holders[:10]:
                pct = float(h.get('percent', 0))
                # Auto-scale if needed (some APIs return 0.5 for 50%, some 50)
                if pct < 1.0 and pct > 0: pct *= 100
                top10 += pct
            
            if top10 > 90:
                score += 25
                details.append(f"🚨 Top 10 Holders: {top10:.1f}% (Extreme)")
            elif top10 > 80:
                score += 15
                details.append(f"⚠️ Top 10 Holders: {top10:.1f}% (High)")
            elif top10 > 60:
                score += 5
                details.append(f"📊 Top 10 Holders: {top10:.1f}%")
            
            # 5. TAX RISK
            buy_tax = float(t_data.get('buy_tax', 0)) * 100 if float(t_data.get('buy_tax', 0)) < 1 else float(t_data.get('buy_tax', 0))
            sell_tax = float(t_data.get('sell_tax', 0)) * 100 if float(t_data.get('sell_tax', 0)) < 1 else float(t_data.get('sell_tax', 0))
            
            if buy_tax > 15 or sell_tax > 15:
                score += 15
                details.append(f"⚠️ High Tax: Buy {buy_tax}% / Sell {sell_tax}%")
            elif buy_tax > 10 or sell_tax > 10:
                score += 5
                details.append(f"📊 Tax: Buy {buy_tax}% / Sell {sell_tax}%")

            # 6. LIQUIDITY BONUS (If info available)
            # Currently static check, real liquidity check handles actual value
            # But we can check for locked status if available
            lp_holders = t_data.get('lp_holders', [])
            total_locked = 0
            dead_addrs = ['0x000000000000000000000000000000000000dead', '0x0000000000000000000000000000000000000000']
            
            for lh in lp_holders:
                is_locked = str(lh.get('is_locked', '0')) == '1'
                addr = lh.get('address', '').lower()
                pct = float(lh.get('percent', 0))
                if pct < 1.0 and pct > 0: pct *= 100
                
                if is_locked or addr in dead_addrs:
                    total_locked += pct
            
            if total_locked > 80:
                score = max(0, score - 20)
                details.append(f"✅ LP Locked: {total_locked:.1f}%")
            elif total_locked > 50:
                score = max(0, score - 10)
                details.append(f"✅ LP Locked: {total_locked:.1f}%")
            
            # FINALIZE
            final_score = min(100, max(0, score))
            risk_level = self._determine_risk_level(final_score)
            
            result['risk_score'] = final_score
            result['risk_level'] = risk_level
            result['contract_analysis'] = {
                'is_verified': str(t_data.get('is_open_source', '0')) == '1',
                'has_mint_function': is_mintable,
                'ownership_renounced': t_data.get('owner_address', '') == '',
                'details': details
            }
            result['holder_analysis'] = {
                'top10_holders_percent': top10,
                'creator_wallet_percent': float(t_data.get('creator_percent', 0)) * 100,
                'details': []
            }
            result['liquidity_analysis'] = {
                'liquidity_locked_percent': total_locked,
                'details': []
            }
            result['swap_analysis'] = {'is_honeypot': is_honeypot, 'details': []}
            
            # Add summary
            details.insert(0, f"📊 GoPlus Risk Score: {final_score}/100 ({risk_level})")

        except Exception as e:
            result['contract_analysis']['details'].append(f"Error: {e}")
            result['risk_score'] = 50
            result['risk_level'] = 'WARN'

    def _calculate_overall_score(self, res):
        """
        Calculate overall score if not already present.
        Legacy fallback for older logic.
        """
        if 'risk_score' in res:
            return res['risk_score']
            
        score = 0  # 0 = Safe, 100 = Risky
        
        # Binary to Score conversion (Legacy)
        if res['swap_analysis'].get('is_honeypot'): score += 100
        if res['contract_analysis'].get('has_mint_function'): score += 20
        
        pct = res['holder_analysis'].get('top10_holders_percent', 0)
        if pct > 90: score += 30
        elif pct > 70: score += 15
        
        liq = res['liquidity_analysis'].get('liquidity_locked_percent', 0)
        if liq < 50: score += 20
        
        return min(100, score)

    def _determine_risk_level(self, score):
        """
        Determine risk level based on 0-100 Risk Score.
        0-30: SAFE (Pass)
        31-60: WARN (Caution)
        61-100: FAIL (Block)
        """
        if score <= 30: return 'SAFE'
        if score <= 60: return 'WARN'
        return 'FAIL'
