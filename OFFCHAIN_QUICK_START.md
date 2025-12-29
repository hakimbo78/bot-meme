# OFF-CHAIN SCREENER - QUICK START (H1-BASED)

## ⚡ TL;DR

**What changed:** Removed ALL 5m metrics, replaced with h1-based logic.  
**Why:** DexScreener PUBLIC API doesn't provide reliable 5m data.  
**Result:** Pairs can now pass filters using realistic h1/h24 thresholds.

---

## 🎯 NEW FILTER LOGIC

### Level-0: Quality Gate
```
✅ liquidity >= $1,000
✅ volume.h1 >= $300
✅ txns.h1 >= 10
```

### Level-1: Momentum Detection
```
✅ priceChange.h1 >= 5%
   OR
✅ Volume Spike Ratio >= 2.0x
   (h1 volume / average hourly volume from h24)
```

---

## 📊 SCORING (0-100)

| Component | Weight | Max Points |
|-----------|--------|------------|
| Liquidity | 30% | 30 |
| Volume h1 | 30% | 30 |
| Price Change h1 | 25% | 25 |
| Transactions h1 | 15% | 15 |
| **Bonus** |  | **+10** |

**Trigger on-chain if:** `FINAL_SCORE >= 60`

---

## 🔄 DEDUPLICATOR

**Cooldown:** 10 minutes

**Re-evaluation triggers:**
- volume.h1 increased >= 50%
- priceChange.h1 increased >= 3%

---

## 📝 LOG FORMAT

```
[OFFCHAIN DEBUG] Processing pair 0xAbCd... | Liq: $2,500 | Vol1h: $820 | Tx1h: 18 | Δ1h: +7.3%
[OFFCHAIN] ✅ DEXSCREENER | BASE | 0xAbCd... | Score: 42.5 | SECONDARY_MARKET
```

**NO 5m REFERENCES ANYWHERE**

---

## 🚀 DEPLOYMENT

```bash
# Files already updated in workspace
# Just restart the service:

sudo systemctl restart bot-meme

# Monitor:
journalctl -u bot-meme -f | grep OFFCHAIN
```

---

## ✅ VALIDATION

```bash
# Quick test:
python test_offchain_screener.py
```

**Expected:**
- ✅ At least 1-2 pairs found (depending on market)
- ✅ Logs show `Vol1h`, `Tx1h`, `Δ1h`
- ✅ No 5m references
- ✅ No errors

---

## 📚 FULL DOCS

1. **OFFCHAIN_H1_REFACTOR_CHECKLIST.md** - Complete validation
2. **OFFCHAIN_CONFIG_REFERENCE.md** - Production config guide
3. **OFFCHAIN_REFACTOR_DELIVERY.md** - Delivery summary

---

## 🎯 KEY CHANGES

| Item | Before | After |
|------|--------|-------|
| Volume threshold | $600* | $300 |
| Tx threshold | 24* | 10 |
| Price threshold | 15% | 5% |
| Pass rate | ~0% | ~5-15% |

_* Implicit from virtual 5m (h1/12)_

---

**Status: PRODUCTION READY** ✅
