# SCORING SYSTEM REVIEW & TIGHTENING

**Date:** 2025-12-31  
**Current Status:** Detecting TOO MANY coins (user overwhelmed)  
**Goal:** Only HIGH QUALITY coins should pass

---

## 📊 CURRENT SCORING SYSTEM ANALYSIS

### **Current Thresholds:**
```python
LOW:    30-44 points  → Suppressed (no alert)
MID:    45-64 points  → Alert sent ✅
HIGH:   65-100 points → Alert sent + On-chain verify ✅
```

### **Point Distribution (Max 100):**
```
Price Change 5m:  30 points (30%)
Price Change 1h:  20 points (20%)
Tx 5m:            20 points (20%)
Liquidity:        10 points (10%)
Volume 24h:       10 points (10%)
Revival Bonus:    10 points (10%)
```

---

## ⚠️ **CURRENT PROBLEMS:**

### **1. TOO EASY to get MID tier (45 points):**

**Example - LOW QUALITY coin getting 45+ points:**
```
tx_5m = 1          → 4 points  (20 * 0.2)
price_change_1h = 15% → 8 points  (20 * 0.4)
liquidity = $2,000 → 4 points  (10 * 0.4)
volume_24h = $5,000 → 4 points  (10 * 0.4)
price_change_5m = 5% → 12 points (30 * 0.4)
────────────────────────────────
TOTAL = 32 points → LOW tier

BUT if price_change_1h = 20%:
tx_5m = 1          → 4 points
price_change_1h = 20% → 12 points (20 * 0.6)
liquidity = $2,000 → 4 points
volume_24h = $5,000 → 4 points
price_change_5m = 10% → 18 points (30 * 0.6)
────────────────────────────────
TOTAL = 42 points → Still LOW

BUT if tx_5m = 5:
tx_5m = 5          → 8 points  (20 * 0.4)
price_change_1h = 20% → 12 points
liquidity = $2,000 → 4 points
volume_24h = $5,000 → 4 points
price_change_5m = 10% → 18 points
────────────────────────────────
TOTAL = 46 points → MID TIER! ✅ ALERT SENT
```

**Problem:** Koin dengan liquidity rendah ($2K) dan volume rendah ($5K) bisa lolos!

---

### **2. Liquidity & Volume TOO LOW:**

**Current minimums:**
- Liquidity: $500 (Level-0 filter)
- Volume: No minimum

**Current scoring:**
```
Liquidity $500   → 2 points (10 * 0.2)
Liquidity $2,000 → 4 points (10 * 0.4)
Liquidity $5,000 → 6 points (10 * 0.6)
```

**Problem:** Koin dengan $500 liquidity masih bisa lolos filter!

---

### **3. tx_5m = 1 is TOO LOOSE:**

**Current:**
```
tx_5m = 1 → 4 points (20 * 0.2)
```

**Problem:** 1 transaksi dalam 5 menit bisa jadi bot/spam!

---

## ✅ **RECOMMENDED CHANGES:**

### **OPTION A: TIGHTEN THRESHOLDS (Conservative)**

**New Thresholds:**
```python
LOW:    30-54 points  → Suppressed
MID:    55-74 points  → Alert sent
HIGH:   75-100 points → Alert sent + Verify
```

**Impact:**
- MID tier requires 55 points (was 45) → +10 points harder
- HIGH tier requires 75 points (was 65) → +10 points harder
- Reduces alerts by ~40-50%

---

### **OPTION B: INCREASE MINIMUM REQUIREMENTS (Aggressive)**

**New Guardrails:**
```python
'global_guardrails': {
    'min_liquidity_usd': 2000,     # Was 500 → 4x stricter
    'min_tx_5m': 3,                # Was 1 → 3x stricter
    'min_volume_24h': 1000,        # NEW requirement
}
```

**New Scoring Buckets:**
```python
# Liquidity (0-10)
if liq >= 100000: score += 10    # $100K+
elif liq >= 50000: score += 8    # $50K+
elif liq >= 20000: score += 6    # $20K+
elif liq >= 10000: score += 4    # $10K+
elif liq >= 5000: score += 2     # $5K+
else: score += 0                  # < $5K → 0 points

# Volume 24h (0-10)
if vol >= 100000: score += 10    # $100K+
elif vol >= 50000: score += 8    # $50K+
elif vol >= 20000: score += 6    # $20K+
elif vol >= 10000: score += 4    # $10K+
elif vol >= 5000: score += 2     # $5K+
else: score += 0                  # < $5K → 0 points

# Tx 5m (0-20)
if tx >= 50: score += 20          # 50+ tx
elif tx >= 20: score += 16        # 20+ tx
elif tx >= 10: score += 12        # 10+ tx
elif tx >= 5: score += 8          # 5+ tx
else: score += 0                  # < 5 tx → 0 points
```

**Impact:**
- Filters out low liquidity (<$2K)
- Filters out low activity (<3 tx in 5m)
- Filters out low volume (<$1K in 24h)
- Reduces alerts by ~60-70%

---

### **OPTION C: HYBRID (Recommended)**

**Combine both:**
1. Increase thresholds: MID=55, HIGH=75
2. Increase minimums: liq=$2K, tx_5m=3, vol=$1K
3. Tighten scoring buckets

**Impact:**
- Only HIGH QUALITY coins pass
- Reduces alerts by ~50-60%
- Still catches good opportunities

---

## 📈 **COMPARISON:**

| Metric | Current | Option A | Option B | Option C |
|--------|---------|----------|----------|----------|
| **Min Liquidity** | $500 | $500 | $2,000 | $2,000 |
| **Min Tx 5m** | 1 | 1 | 3 | 3 |
| **Min Volume** | None | None | $1,000 | $1,000 |
| **MID Threshold** | 45 | 55 | 45 | 55 |
| **HIGH Threshold** | 65 | 75 | 65 | 75 |
| **Alert Reduction** | - | 40-50% | 60-70% | 50-60% |
| **Quality** | Medium | Good | Very Good | **Excellent** |

---

## 🎯 **MY RECOMMENDATION: OPTION C (HYBRID)**

**Why:**
- ✅ Balanced approach
- ✅ Filters out obvious garbage
- ✅ Still catches good opportunities
- ✅ Reduces alert spam significantly
- ✅ Focuses on HIGH QUALITY only

**Implementation:**
1. Update `offchain_config.py` - Increase thresholds & minimums
2. Update `offchain/filters.py` - Tighten scoring buckets
3. Test for 1 hour
4. Adjust if needed

---

## 📝 **PROPOSED NEW CONFIG:**

```python
# offchain_config.py

'global_guardrails': {
    'min_liquidity_usd': 2000,      # Was 500 → 4x stricter
    'min_tx_5m': 3,                 # Was 1 → 3x stricter
    'min_volume_24h': 1000,         # NEW requirement
    'require_h24_volume': True,     # Enforce volume check
},

'scoring_v3': {
    'thresholds': {
        'low': 30,
        'mid': 55,      # Was 45 → +10 harder
        'high': 75,     # Was 65 → +10 harder
        'verify': 75    # Was 65 → +10 harder
    }
},
```

---

## ⚡ **EXPECTED RESULTS AFTER TIGHTENING:**

**Before:**
- Alerts per scan: 10-15
- Alerts per day: 200-300
- Quality: Mixed (some garbage)

**After (Option C):**
- Alerts per scan: 4-6
- Alerts per day: 80-120
- Quality: HIGH (mostly good coins)

**Reduction:** ~50-60% fewer alerts, but MUCH higher quality!

---

## 🚀 **READY TO IMPLEMENT?**

Which option do you prefer?

**A.** Tighten thresholds only (conservative)
**B.** Increase minimums only (aggressive)
**C.** Hybrid approach (recommended)
**D.** Custom (you specify the values)

Let me know and I'll implement it immediately! 🎯
