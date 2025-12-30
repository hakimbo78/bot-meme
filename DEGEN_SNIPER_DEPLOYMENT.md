# 🚀 MODE C V2: DEGEN SNIPER - DEPLOYMENT REPORT

**Status:** ✅ DEPLOYED & TESTED
**Mode:** HYBRID OFF-CHAIN FIRST (Score-Based Gating)

---

## 📋 V2 UPGRADE SUMMARY

The **DEGEN SNIPER** has been upgraded to **V2**. This mode prioritizes off-chain signals (DexScreener) and acts as a strict gatekeeper to protect RPC usage.

### 🛡️ Guardrails & Gating
*   **Off-Chain First:** No on-chain verification unless score ≥ **55**.
*   **Low Tier Rejection:** Scores < **25** are silently dropped.
*   **Spam Protection:** Strict global guardrails (Liq > $5k, Vol > 0, Age < 24h unless high volume).

### 🎯 Scoring V2 (0-100 Scale)
Based on weighted off-chain metrics:
*   **Liquidity (30%)**: Target $100k
*   **Volume 24h (30%)**: Target $100k
*   **Price Change 1h (20%)**: Target 100%
*   **Tx Count (24h) (20%)**: Target 500 tx

### 🔔 Telegram Tiering
| Tier | Score Range | Action | Rate Limit |
| :--- | :--- | :--- | :--- |
| **LOW** | 25 - 39 | 🟡 Alert Only | 1 per 10m |
| **MID** | 40 - 59 | 🟡 Alert Only | 1 per 1m |
| **HIGH** | ≥ 60 | 🚨 **VERIFY** + Alert | No Limit |

### 🛑 Deduplication
*   **Token Level:** 30 minutes cooldown.
*   **Pair Level:** 15 minutes cooldown.

---

## 🧪 TEST RESULTS

Running `test_degen_v2.py`... **ALL PASS**.

| Scenario | Result | Reason |
| :--- | :--- | :--- |
| **High Score (68)** | ✅ VERIFY | Score ≥ 55. Enqueued for on-chain scan. |
| **Low Score (12)** | ❌ DROP | Score < 25. Ignored to save resources. |
| **Guardrails** | ❌ DROP | Failed Liquidity/Volume checks. |

---

## 🔧 FILES UPDATED

1.  `offchain_config.py`: Complete V2 config with tiers.
2.  `offchain/filters.py`: New scoring engine (0-100) and tiers.
3.  `offchain/deduplicator.py`: Added Token-level (30m) deduplication.
4.  `offchain/normalizer.py`: Strict JSON normalization.
5.  `offchain/integration.py`: Gatekeeper logic (Verify only if Score ≥ 55).

## 🚀 NEXT STEPS

Start the bot normally. It is now running in **DEGEN SNIPER V2** mode.

```bash
python main.py
```
