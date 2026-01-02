#!/usr/bin/env python3
"""
Verification Script for Recent Bot Fixes
=========================================
Tests:
1. RugCheck parsing fixes (holder concentration + LP lock)
2. Config updates (min_holders, min_signal_score, max_risk_score)
3. Real token test (SCM token as example)

Usage:
    python3 verify_fixes.py
"""

import sys
import json
import requests
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*60}\n")

def print_test(test_name, passed, details=""):
    status = f"{Fore.GREEN}✅ PASS" if passed else f"{Fore.RED}❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"      {Fore.YELLOW}{details}")

def test_config_values():
    """Test 1: Verify config values are updated correctly"""
    print_header("TEST 1: Config Values")
    
    results = []
    
    try:
        # Import configs
        from offchain_config import DEGEN_SNIPER_CONFIG
        from trading_config import TradingConfig
        
        # Test min_holders
        min_holders = DEGEN_SNIPER_CONFIG['global_guardrails']['quality_check']['min_holders']
        passed = min_holders == 35
        print_test(f"min_holders = 35", passed, f"Current: {min_holders}")
        results.append(passed)
        
        # Test min_signal_score
        trading_cfg = TradingConfig.get_config()
        min_signal = trading_cfg['trading']['min_signal_score']
        passed = min_signal == 60
        print_test(f"min_signal_score = 60", passed, f"Current: {min_signal}")
        results.append(passed)
        
        # Test max_risk_score
        max_risk = trading_cfg['risk']['max_risk_score']
        passed = max_risk == 30
        print_test(f"max_risk_score = 30", passed, f"Current: {max_risk}")
        results.append(passed)
        
    except Exception as e:
        print_test("Config Import", False, str(e))
        return False
    
    return all(results)

def test_rugcheck_parsing():
    """Test 2: Verify RugCheck parsing fixes with SCM token"""
    print_header("TEST 2: RugCheck Parsing Fixes")
    
    results = []
    
    try:
        from tokensniffer_analyzer import TokenSnifferAnalyzer
        
        # Test with SCM token (known good token with 99.99% LP lock)
        SCM_TOKEN = "9NrkmoqwF1rBjsfKZvn7ngCy6zqvb8A6A5RfTvR2pump"
        
        print(f"{Fore.YELLOW}Testing with SCM token...")
        print(f"{Fore.YELLOW}Address: {SCM_TOKEN}\n")
        
        analyzer = TokenSnifferAnalyzer(None, 'solana')
        result = analyzer.analyze_comprehensive(SCM_TOKEN)
        
        # Extract metrics
        risk_score = result.get('risk_score', 100)
        risk_level = result.get('risk_level', 'UNKNOWN')
        details = result.get('contract_analysis', {}).get('details', [])
        
        print(f"{Fore.CYAN}Analysis Results:")
        print(f"  Risk Score: {risk_score}/100")
        print(f"  Risk Level: {risk_level}\n")
        
        print(f"{Fore.CYAN}Details:")
        for detail in details:
            print(f"  {detail}")
        print()
        
        # Test 1: Risk score should be LOW (< 10)
        passed = risk_score < 10
        print_test("Risk Score < 10", passed, f"Score: {risk_score}/100")
        results.append(passed)
        
        # Test 2: Should find "Top 10 Holders" in details
        top10_detail = [d for d in details if 'Top 10 Holders' in d]
        if top10_detail:
            # Extract percentage
            import re
            match = re.search(r'(\d+\.?\d*)%', top10_detail[0])
            if match:
                top10_pct = float(match.group(1))
                # Should be ~26%, definitely NOT 99.9%
                passed = top10_pct < 50
                print_test("Top 10 Holders < 50%", passed, 
                          f"Found: {top10_pct}% (Should be ~26%)")
                results.append(passed)
            else:
                print_test("Top 10 Holders parsing", False, "Cannot extract percentage")
                results.append(False)
        else:
            print_test("Top 10 Holders found", False, "Detail not found")
            results.append(False)
        
        # Test 3: Should find "LP Secured" in details
        lp_detail = [d for d in details if 'LP Secured' in d or 'LP Not Secured' in d]
        if lp_detail:
            # Should show high LP lock, NOT 0%
            passed = 'LP Not Secured (0%)' not in lp_detail[0]
            print_test("LP Lock Detected", passed, 
                      f"Found: '{lp_detail[0]}'")
            results.append(passed)
        else:
            print_test("LP Lock found", False, "Detail not found")
            results.append(False)
        
        # Test 4: Risk level should be SAFE or WARN (not FAIL)
        passed = risk_level in ['SAFE', 'WARN']
        print_test(f"Risk Level = SAFE/WARN", passed, f"Current: {risk_level}")
        results.append(passed)
        
    except Exception as e:
        print_test("RugCheck Test", False, str(e))
        import traceback
        traceback.print_exc()
        return False
    
    return all(results)

def test_code_changes():
    """Test 3: Verify code changes are present"""
    print_header("TEST 3: Code Changes Verification")
    
    results = []
    
    try:
        with open('tokensniffer_analyzer.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Test 1: AMM/LOCKER filter present
        passed = "Filter out AMM/LOCKERs" in code or "Filter out non-holder" in code
        print_test("AMM/LOCKER filter code present", passed)
        results.append(passed)
        
        # Test 2: LP lock path fix present
        passed = "markets[0].get('lp'" in code or "lp_data = markets[0]" in code
        print_test("LP lock path fix present", passed)
        results.append(passed)
        
        # Test 3: knownAccounts usage
        passed = "knownAccounts" in code
        print_test("knownAccounts filtering present", passed)
        results.append(passed)
        
    except Exception as e:
        print_test("Code Review", False, str(e))
        return False
    
    return all(results)

def test_api_connection():
    """Test 4: Verify RugCheck API is accessible"""
    print_header("TEST 4: API Connection")
    
    try:
        url = "https://api.rugcheck.xyz/v1/tokens/9NrkmoqwF1rBjsfKZvn7ngCy6zqvb8A6A5RfTvR2pump/report"
        resp = requests.get(url, timeout=10)
        
        passed = resp.status_code == 200
        print_test("RugCheck API accessible", passed, 
                  f"Status: {resp.status_code}")
        
        if passed:
            data = resp.json()
            # Verify data structure
            has_holders = 'topHolders' in data
            has_markets = 'markets' in data
            has_lp = data.get('markets', [{}])[0].get('lp') is not None if data.get('markets') else False
            
            print_test("API has topHolders", has_holders)
            print_test("API has markets", has_markets)
            print_test("API has markets[0].lp", has_lp)
            
            return all([passed, has_holders, has_markets, has_lp])
        
        return False
        
    except Exception as e:
        print_test("API Connection", False, str(e))
        return False

def main():
    """Run all tests"""
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}BOT FIX VERIFICATION SCRIPT")
    print(f"{Fore.MAGENTA}{'='*60}")
    
    # Track results
    test_results = {}
    
    # Run tests
    test_results['Config Values'] = test_config_values()
    test_results['API Connection'] = test_api_connection()
    test_results['Code Changes'] = test_code_changes()
    test_results['RugCheck Parsing'] = test_rugcheck_parsing()
    
    # Summary
    print_header("SUMMARY")
    
    all_passed = all(test_results.values())
    
    for test_name, passed in test_results.items():
        print_test(test_name, passed)
    
    print()
    if all_passed:
        print(f"{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}✅ ALL TESTS PASSED!")
        print(f"{Fore.GREEN}Bot is ready for deployment.")
        print(f"{Fore.GREEN}{'='*60}\n")
        sys.exit(0)
    else:
        print(f"{Fore.RED}{'='*60}")
        print(f"{Fore.RED}❌ SOME TESTS FAILED!")
        print(f"{Fore.RED}Please review errors above.")
        print(f"{Fore.RED}{'='*60}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
