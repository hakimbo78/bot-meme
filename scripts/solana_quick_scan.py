"""
Quick Solana scan to validate metadata-optional flow and debug logs.

Runs the SolanaScanner for a few cycles and evaluates SNIPER eligibility.
Prints [SOLANA][DEBUG] logs with tx signature, score, metadata_status, and skip_reason.
"""
import time
import os
import sys

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import load_chain_configs
from modules.solana.solana_scanner import SolanaScanner
from modules.solana.solana_sniper import SolanaSniperDetector
from modules.solana.solana_utils import solana_log


def main():
    cfgs = load_chain_configs()
    sol_cfg = cfgs.get('chains', {}).get('solana', {})
    if not sol_cfg or not sol_cfg.get('enabled', False):
        print("[SOLANA][DEBUG] Solana chain not enabled in chains.yaml")
        return

    scanner = SolanaScanner(sol_cfg)
    sniper = SolanaSniperDetector(sol_cfg)

    if not scanner.connect():
        print("[SOLANA][DEBUG] Scanner failed to connect")
        return

    solana_log("Starting quick scan loop (3 cycles)...", "DEBUG")

    cycles = 3
    for i in range(cycles):
        events = scanner.scan_new_pairs()
        if events:
            solana_log(f"Cycle {i+1}: {len(events)} unified events", "DEBUG")
        else:
            solana_log(f"Cycle {i+1}: 0 events", "DEBUG")

        # Evaluate sniper eligibility on fresh events
        for ev in events:
            res = sniper.check_sniper_eligibility(ev)
            # Explicit quick-print to confirm scoring continues without metadata
            sig = ev.get('tx_signature')
            meta_status = ev.get('metadata_status', 'missing')
            score = res.get('sniper_score', 0)
            skips = res.get('skip_reasons', [])
            sr = ','.join(skips) if skips else ''
            if sig:
                print(f"[SOLANA][DEBUG] Sig={str(sig)[:8]}... | Score={score} | Metadata={meta_status} | SkipReason={sr}", flush=True)
            else:
                print(f"[SOLANA][DEBUG] Score={score} | Metadata={meta_status} | SkipReason={sr}", flush=True)

        # Short delay between cycles
        time.sleep(5)


if __name__ == "__main__":
    main()
