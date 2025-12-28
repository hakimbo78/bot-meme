"""
Synthetic test to confirm scoring continues without token metadata.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.solana.solana_score_engine import SolanaScoreEngine

def main():
    engine = SolanaScoreEngine({
        'debug': {
            'enabled': True,
            'log_top_n': 1,
            'log_interval_seconds': 0
        },
        'alert_thresholds': {
            'INFO': 30,
            'WATCH': 50,
            'TRADE': 70
        }
    })

    token = {
        'symbol': 'TEST',
        'token_address': 'So11111111111111111111111111111111111111112',
        'tx_signature': 'ABCDEFG1234567890',
        'metadata_status': 'missing',
        'sol_inflow': 20.0,
        'buy_velocity': 18.0,
        'has_raydium_pool': False,
        'liquidity_usd': 0,
        'liquidity_trend': 'stable',
        'jupiter_listed': False,
        'jupiter_volume_24h': 0,
        'creator_sold': False,
        'unique_buyers': 8
    }

    res = engine.calculate_score(token)
    print(f"Score={res['score']} Verdict={res['verdict']} SkipReason={res['skip_reason']}")

if __name__ == '__main__':
    main()
