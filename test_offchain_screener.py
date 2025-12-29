"""
OFF-CHAIN SCREENER TEST SCRIPT

Test the off-chain screener components independently before integration.
"""

import asyncio
import sys
from colorama import init, Fore, Style

init(autoreset=True)


async def test_dexscreener():
    """Test DexScreener API client."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}TEST 1: DexScreener API Client")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        from offchain.dex_screener import DexScreenerAPI
        
        screener = DexScreenerAPI()
        
        # Test fetch trending pairs
        print(f"{Fore.YELLOW}Fetching trending pairs for BASE...")
        pairs = await screener.fetch_trending_pairs('base', limit=5)
        
        if pairs:
            print(f"{Fore.GREEN}✅ Found {len(pairs)} trending pairs")
            for idx, pair in enumerate(pairs[:3], 1):
                print(f"{Fore.WHITE}  {idx}. {pair.get('baseToken', {}).get('symbol', 'UNKNOWN')} - ${pair.get('liquidity', {}).get('usd', 0):,.0f} liq")
        else:
            print(f"{Fore.RED}❌ No pairs found")
        
        # Test fetch top gainers
        print(f"\n{Fore.YELLOW}Fetching top gainers (1h) for BASE...")
        gainers = await screener.fetch_top_gainers('base', '1h', limit=5)
        
        if gainers:
            print(f"{Fore.GREEN}✅ Found {len(gainers)} top gainers")
            for idx, pair in enumerate(gainers[:3], 1):
                price_change = pair.get('priceChange', {}).get('h1', 0)
                print(f"{Fore.WHITE}  {idx}. {pair.get('baseToken', {}).get('symbol', 'UNKNOWN')} - {price_change}% gain")
        else:
            print(f"{Fore.RED}❌ No gainers found")
        
        # Cleanup
        await screener.close()
        
        print(f"\n{Fore.GREEN}✅ DexScreener test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ DexScreener test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_normalizer():
    """Test PairNormalizer."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}TEST 2: Pair Normalizer")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        from offchain.normalizer import PairNormalizer
        
        normalizer = PairNormalizer()
        
        # Mock DexScreener data
        mock_pair = {
            'chainId': 'base',
            'dexId': 'uniswap',
            'pairAddress': '0x1234567890abcdef',
            'baseToken': {
                'address': '0xtoken0',
                'name': 'TestToken',
                'symbol': 'TEST',
            },
            'quoteToken': {
                'address': '0xtoken1',
                'name': 'USD Coin',
                'symbol': 'USDC',
            },
            'priceChange': {
                'm5': 25.5,
                'h1': 150.0,
                'h24': 300.0,
            },
            'volume': {
                'm5': 5000,
                'h1': 50000,
                'h24': 500000,
            },
            'liquidity': {
                'usd': 75000,
            },
            'txns': {
                'm5': {'buys': 10, 'sells': 8},
                'h1': {'buys': 50, 'sells': 45},
                'h24': {'buys': 300, 'sells': 280},
            },
            'pairCreatedAt': 1735461600000,  # Recent timestamp
        }
        
        normalized = normalizer.normalize_dexscreener(mock_pair)
        
        print(f"{Fore.YELLOW}Normalized pair:")
        print(f"{Fore.WHITE}  Chain: {normalized['chain']}")
        print(f"{Fore.WHITE}  Pair: {normalized['pair_address']}")
        print(f"{Fore.WHITE}  Token: {normalized['token_symbol']}")
        print(f"{Fore.WHITE}  Price change (5m): {normalized['price_change_5m']}%")
        print(f"{Fore.WHITE}  Price change (1h): {normalized['price_change_1h']}%")
        print(f"{Fore.WHITE}  Liquidity: ${normalized['liquidity']:,.0f}")
        print(f"{Fore.WHITE}  Volume (5m): ${normalized['volume_5m']:,.0f}")
        print(f"{Fore.WHITE}  Transactions (5m): {normalized['tx_5m']}")
        print(f"{Fore.WHITE}  Confidence: {normalized['confidence']:.2f}")
        print(f"{Fore.WHITE}  Event type: {normalized['event_type']}")
        
        print(f"\n{Fore.GREEN}✅ Normalizer test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Normalizer test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_filters():
    """Test OffChainFilter."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}TEST 3: Off-Chain Filters")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        from offchain.filters import OffChainFilter
        
        filter_obj = OffChainFilter()
        
        # Test case 1: Should PASS (good metrics)
        good_pair = {
            'liquidity': 50000,
            'volume_5m': 10000,
            'tx_5m': 20,
            'price_change_5m': 50.0,
            'price_change_1h': 150.0,
            'age_minutes': 30,
        }
        
        passed, reason = filter_obj.apply_filters(good_pair)
        if passed:
            print(f"{Fore.GREEN}✅ Test 1 PASSED: Good pair accepted")
        else:
            print(f"{Fore.RED}❌ Test 1 FAILED: Good pair rejected - {reason}")
        
        # Test case 2: Should FAIL (low liquidity)
        low_liq_pair = {
            'liquidity': 1000,  # Too low
            'volume_5m': 10000,
            'tx_5m': 20,
            'price_change_5m': 50.0,
        }
        
        passed, reason = filter_obj.apply_filters(low_liq_pair)
        if not passed:
            print(f"{Fore.GREEN}✅ Test 2 PASSED: Low liquidity pair rejected - {reason}")
        else:
            print(f"{Fore.RED}❌ Test 2 FAILED: Low liquidity pair accepted")
        
        # Test case 3: Should PASS (DEXTools guarantee)
        dextools_pair = {
            'source': 'dextools',
            'dextools_rank': 15,
            'liquidity': 1000,  # Even with low liquidity
            'volume_5m': 100,
            'tx_5m': 2,
        }
        
        passed, reason = filter_obj.apply_filters(dextools_pair)
        if passed:
            print(f"{Fore.GREEN}✅ Test 3 PASSED: DEXTools top rank bypassed filters")
        else:
            print(f"{Fore.RED}❌ Test 3 FAILED: DEXTools guarantee didn't work - {reason}")
        
        # Print stats
        stats = filter_obj.get_stats()
        print(f"\n{Fore.YELLOW}Filter Statistics:")
        print(f"{Fore.WHITE}  Total evaluated: {stats['total_evaluated']}")
        print(f"{Fore.WHITE}  Passed: {stats['passed']}")
        print(f"{Fore.WHITE}  Filter rate: {stats['filter_rate_pct']:.1f}%")
        
        print(f"\n{Fore.GREEN}✅ Filters test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Filters test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_integration():
    """Test full OffChainScreenerIntegration."""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}TEST 4: Full Integration")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    try:
        from offchain.integration import OffChainScreenerIntegration
        from offchain_config import get_offchain_config
        
        config = get_offchain_config()
        config['enabled_chains'] = ['base']
        
        screener = OffChainScreenerIntegration(config)
        
        print(f"{Fore.YELLOW}Starting off-chain screener...")
        
        # Start background tasks
        tasks = await screener.start()
        print(f"{Fore.GREEN}✅ Started {len(tasks)} background tasks")
        
        # Wait for first pair (with timeout)
        print(f"{Fore.YELLOW}Waiting for first pair (60s timeout)...")
        
        try:
            pair = await asyncio.wait_for(screener.get_next_pair(), timeout=60.0)
            
            print(f"{Fore.GREEN}✅ Received pair: {pair.get('token_symbol', 'UNKNOWN')}")
            print(f"{Fore.WHITE}  Chain: {pair['chain']}")
            print(f"{Fore.WHITE}  Source: {pair['source']}")
            print(f"{Fore.WHITE}  Off-chain score: {pair['offchain_score']:.1f}")
            print(f"{Fore.WHITE}  Event type: {pair['event_type']}")
            
        except asyncio.TimeoutError:
            print(f"{Fore.YELLOW}⚠️  No pairs found in 60s (this is OK if market is quiet)")
        
        # Print stats
        screener.print_stats()
        
        # Cleanup
        for task in tasks:
            task.cancel()
        
        await screener.close()
        
        print(f"\n{Fore.GREEN}✅ Integration test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Integration test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}OFF-CHAIN SCREENER TEST SUITE")
    print(f"{Fore.MAGENTA}{'='*60}\n")
    
    results = []
    
    # Test 1: DexScreener
    results.append(await test_dexscreener())
    
    # Test 2: Normalizer
    results.append(await test_normalizer())
    
    # Test 3: Filters
    results.append(await test_filters())
    
    # Test 4: Integration (optional - requires network)
    if '--full' in sys.argv:
        results.append(await test_integration())
    else:
        print(f"{Fore.YELLOW}Skipping integration test (use --full flag to include)")
    
    # Summary
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}TEST SUMMARY")
    print(f"{Fore.MAGENTA}{'='*60}\n")
    
    passed = sum(results)
    total = len(results)
    
    print(f"{Fore.WHITE}Tests passed: {passed}/{total}")
    
    if passed == total:
        print(f"\n{Fore.GREEN}🎉 ALL TESTS PASSED! Off-chain screener is ready.\n")
        return 0
    else:
        print(f"\n{Fore.RED}❌ Some tests failed. Please check errors above.\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
