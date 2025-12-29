# 🚀 MODE C: DEGEN SNIPER - DEPLOYMENT REPORT

**Status:** ✅ DEPLOYED & TESTED
**Mode:** EXTREMELY AGGRESSIVE (Ultra-Early Detection)

---

## 📋 SUMMARY

The **DEGEN SNIPER** mode has been successfully implemented and integrated into the off-chain screener. This mode is optimized to catch tokens in their earliest moments while filtering out absolute garbage.

### Key Features Implemented:

1.  **Level-0: Loose Viability Check**
    *   PASS if: Liquidity ≥ $5,000 OR Vol.h24 ≥ $2,000.
    *   *Purpose:* Don't kill pairs just because they are new (h1 volume might be 0).

2.  **Level-1: Momentum Triggers (ANY)**
    *   Trigger if: Txns.h1 ≥ 1 OR Vol.h1 ≥ 10 OR PriceChange.h1 ≠ 0.
    *   *Purpose:* Detect the very first sign of life.

3.  **Level-2: Structural Quality**
    *   Must satisfy at least 2 of: Liq ≥ $10k, Vol.h24 ≥ $10k, Txns.h24 ≥ 20, Abs(ΔPrice) ≥ 5%.
    *   *Purpose:* Ensure the token isn't dead on arrival.

4.  **Bonus Signals (+1 Score each)**
    *   **Fresh LP:** Liquidity > Volume.h24
    *   **Warmup:** Txns.h1 ratio is high relative to h24
    *   **Solana Active:** Solana chain & Txns.h24 ≥ 10

5.  **Smart Deduplication**
    *   Base Cooldown: **120 seconds** (Aggressive)
    *   **Bypass Cooldown If:**
        *   Txns increase (ANY amount)
        *   Volume increases ≥ $5
        *   Price changes ≥ 0.1%

---

## 🧪 TEST RESULTS

Running `test_degen_sniper.py`... **ALL PASS**.

| Scenario | Result | Reason |
| :--- | :--- | :--- |
| **Early Solana** | ✅ PASS | Ignored 0 volume, caught by Txn count & Bonus |
| **Fresh LP (Base)** | ✅ PASS | Caught by Fresh LP bonus + Level 2 |
| **Dead Pair** | ❌ FAIL | Failed Level-0 (No viability) |
| **Fake Liquidity** | ❌ FAIL | Failed Level-2 (High liq but no volume/tx) |
| **Guardrails** | ❌ FAIL | Liquidity < $3k or Zero h24 Volume |

---

## 🔧 FILES UPDATED

1.  `offchain_config.py`: Replaced with new DEGEN SNIPER config.
2.  `offchain/filters.py`: Replaced with new 3-level filter logic.
3.  `offchain/deduplicator.py`: Updated to support sensitive re-evaluation thresholds from config.

## 🚀 NEXT STEPS

The bot is now configured in **DEGEN SNIPER** mode. Start the bot normally to begin aggressive scanning.

```bash
python main.py
```

*Note: Expect a higher volume of alerts. Tune `min_score_to_pass` in `offchain_config.py` if too noisy.*
