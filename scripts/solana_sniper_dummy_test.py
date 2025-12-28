"""
Synthetic test to confirm SNIPER eligibility continues without token metadata.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.solana.solana_sniper import SolanaSniperDetector

def main():
    sniper = SolanaSniperDetector({
        'sniper': {
            'enabled': True,
            'max_age_seconds': 120,
            'min_sol_inflow': 10.0,
            'min_buy_velocity': 15.0,
            'min_sniper_score': 70
        },
        'debug': {
            'enabled': True,
            'log_top_n': 1,
            'log_interval_seconds': 0
        }
    })

    token = {
        'source': 'pumpfun',
        'symbol': 'TEST',
        'token_address': 'So11111111111111111111111111111111111111112',
        'tx_signature': 'ABCDEFG1234567890',
        'metadata_status': 'missing',
        'age_seconds': 60,
        'sol_inflow': 80.0,
        'buy_velocity': 40.0,
        'has_raydium_pool': False,
        'creator_sold': False,
        'unique_buyers': 12,
        'liquidity_trend': 'growing'
    }

    res = sniper.check_sniper_eligibility(token)
    print(f"Eligible={res['eligible']} Score={res.get('sniper_score')} Skips={res['skip_reasons']}")

if __name__ == '__main__':
    main()
