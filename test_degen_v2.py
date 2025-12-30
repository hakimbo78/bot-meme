
import asyncio
import sys
import os

# Mock classes to avoid full dependency load
class MockNotifier:
    def __init__(self):
        self.chat_id = 123
        self.bot = MockBot()

class MockBot:
    async def send_message(self, chat_id, text, parse_mode=None, disable_web_page_preview=False):
        print(f"[MOCK TELEGRAM] Sending to {chat_id}:\n{text}\n")

# Import the actual modules
from offchain.filters import OffChainFilter
from offchain.deduplicator import Deduplicator
from offchain.normalizer import PairNormalizer
from offchain_config import DEGEN_SNIPER_CONFIG

async def test_v2_system():
    print("Testing DEGEN SNIPER MODE C V2 Components...")
    
    # 1. Test Config Loading
    config = DEGEN_SNIPER_CONFIG
    assert config['mode_name'] == 'DEGEN_SNIPER_V2'
    print("✅ Config loaded")
    
    # 2. Test Normalizer
    norm = PairNormalizer()
    raw_dex_pair = {
        'chainId': 'base',
        'pairAddress': '0x123',
        'baseToken': {'address': '0xToken', 'symbol': 'TEST', 'name': 'Test Token'},
        'liquidity': {'usd': 60000},
        'volume': {'h24': 80000},
        'priceChange': {'h1': 15},
        'txns': {'h24': {'buys': 60, 'sells': 50}},
        'pairCreatedAt': 1700000000000 # Old timestamp
    }
    normalized = norm.normalize_dexscreener(raw_dex_pair)
    print(f"Normalized: {normalized.keys()}")
    assert normalized['liquidity'] == 60000
    assert normalized['tx_24h'] == 110
    print("✅ Normalizer passed")

    # 3. Test Deduplicator
    dedup = Deduplicator(config['deduplication'])
    # First see
    assert dedup.is_token_duplicate("0xToken", "base") == False
    # Second see (should be duplicate)
    assert dedup.is_token_duplicate("0xToken", "base") == True
    print("✅ Deduplicator passed (Token Level)")
    
    # 4. Test Filters & Scoring
    filt = OffChainFilter(config)
    
    # High Score Scenario
    # Liq 60k -> >50k = ~24pts
    # Vol 80k -> >50k = ~24pts
    # Price 15% -> >10% = ~8pts
    # Tx 110 -> >100 = ~12pts
    # Total approx 68pts -> HIGH -> VERIFY
    
    passed, reason, meta = filt.apply_filters(normalized)
    if not passed:
        print(f"Filter failed unexpectedly: {reason}")
    print(f"Filter Result: Passed={passed}, Score={meta.get('score') if meta else 'N/A'}, Verdict={meta.get('verdict') if meta else 'N/A'}")
    assert passed == True
    assert meta['score'] > 60
    assert meta['verdict'] == 'VERIFY'
    
    # Low Score Scenario
    raw_low = raw_dex_pair.copy()
    raw_low['liquidity'] = {'usd': 6000} # Low liq -> ~6pts
    raw_low['volume'] = {'h24': 3000} # Low vol -> ~6pts
    import time
    raw_low['pairCreatedAt'] = int((time.time() - 3600) * 1000) # 1 hour old (fresh)
    
    norm_low = norm.normalize_dexscreener(raw_low)
    passed_low, reason_low, meta_low = filt.apply_filters(norm_low)
    print(f"Low Result: Passed={passed_low}, Reason={reason_low}, Score={meta_low.get('score') if meta_low else 'N/A'}")
    
    # Guardrail Fail
    raw_fail = raw_dex_pair.copy()
    raw_fail['liquidity'] = {'usd': 100} # < 5000
    norm_fail = norm.normalize_dexscreener(raw_fail)
    passed_fail, reason_fail, meta_fail = filt.apply_filters(norm_fail)
    print(f"Fail Result: Passed={passed_fail}, Reason={reason_fail}")
    assert passed_fail == False
    
    print("✅ Filters passed")
    
    print("ALL SYSTEMS GO 🚀")

if __name__ == "__main__":
    asyncio.run(test_v2_system())
