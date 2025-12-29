# UPDATED OFF-CHAIN SCREENER CONFIGURATION

## ⚙️ PRODUCTION CONFIG (H1-BASED)

```python
OFFCHAIN_SCREENER_CONFIG = {
    'enabled': True,
    'enabled_chains': ['base', 'ethereum', 'solana'],
    
    # FILTERS (H1-BASED ONLY - NO 5M METRICS)
    'filters': {
        # Level-0: Quality Gate
        'min_liquidity': 1000,          # $1,000 USD
        'min_volume_1h': 300,            # $300 hourly volume
        'min_tx_1h': 10,                 # 10 hourly transactions
        'max_age_hours': None,           # Disabled (allow old pairs if momentum detected)
        
        # Level-1: Momentum Detection
        'min_price_change_1h': 5.0,      # 5% price gain in 1h
        'min_volume_spike_ratio': 2.0,   # 2.0x volume spike (h1 vs h24 avg)
        
        # DEXTools bypass
        'dextools_top_rank': 50,         # Top 50 ranks force-pass
    },
    
    # DEDUPLICATOR (with momentum re-evaluation)
    'deduplicator': {
        'cooldown_seconds': 600,         # 10 min cooldown
        # Re-evaluation triggers:
        # - volume_1h increased >= 50%
        # - price_change_1h increased >= 3%
    },
    
    # SCORING WEIGHTS (H1-based)
    'scoring': {
        'offchain_weight': 0.6,          # 60% off-chain
        'onchain_weight': 0.4,           # 40% on-chain
        'verify_threshold': 60,          # Score >= 60 triggers on-chain verify
        
        # Off-chain component weights (total = 100%)
        'liquidity_weight': 0.30,        # 30% - liquidity.usd
        'volume_1h_weight': 0.30,        # 30% - volume.h1
        'price_change_1h_weight': 0.25,  # 25% - priceChange.h1
        'tx_1h_weight': 0.15,            # 15% - txns.h1
    },
}
```

---

## 🎯 FILTER LOGIC

### **Level-0: Quality Gate** (eliminates dead/inactive pairs)
```
PASS if ALL of:
  ✅ liquidity >= $1,000
  ✅ volume.h1 >= $300
  ✅ txns.h1 >= 10
```

### **Level-1: Momentum Detection** (identifies breakouts)
```
PASS if ANY of:
  ✅ priceChange.h1 >= 5%
     OR
  ✅ Volume Spike Ratio >= 2.0x
     (where ratio = volume.h1 / (volume.h24 / 24))
```

---

## 📊 SCORING FORMULA

### Off-Chain Score (0-100)
```
score = 0

# Liquidity (0-30 points)
if liquidity >= 100k: +30
elif liquidity >= 50k: +21
elif liquidity >= 20k: +15
elif liquidity >= 10k: +9
elif liquidity >= 5k: +6

# Volume h1 (0-30 points)
if volume_1h >= 50k: +30
elif volume_1h >= 10k: +21
elif volume_1h >= 5k: +15
elif volume_1h >= 1k: +9
elif volume_1h >= 500: +6

# Price Change h1 (0-25 points)
if price_change_1h >= 100%: +25
elif price_change_1h >= 50%: +17.5
elif price_change_1h >= 20%: +12.5
elif price_change_1h >= 10%: +7.5
elif price_change_1h >= 5%: +5

# Transactions h1 (0-15 points)
if tx_1h >= 200: +15
elif tx_1h >= 100: +10.5
elif tx_1h >= 50: +7.5
elif tx_1h >= 20: +4.5
elif tx_1h >= 10: +3

# Confidence bonus (0-10 points)
score += confidence * 10

# DEXTools rank bonus
if source == 'dextools' and rank <= 10: +20
elif source == 'dextools' and rank <= 30: +15
elif source == 'dextools' and rank <= 50: +10
```

### Final Score
```
FINAL_SCORE = (offchain_score × 0.6) + (onchain_score × 0.4)

IF FINAL_SCORE >= 60:
    → Trigger on-chain verification
ELSE:
    → Skip (RPC savings)
```

---

## 🔄 DEDUPLICATOR LOGIC

### Standard Behavior
```
IF pair was seen within last 10 minutes:
    IF volume_1h increased >= 50%:
        → Allow re-evaluation (momentum increase)
    ELIF price_change_1h increased >= 3%:
        → Allow re-evaluation (momentum increase)
    ELSE:
        → Block (duplicate, no momentum)
ELSE:
    → Allow (cooldown expired)
```

### Example
```
T=0:    Pair seen with volume_1h=$500, price_change_1h=+3%
T=5min: Same pair, volume_1h=$800 (+60%)
        → ALLOWED (volume spike >= 50%)

T=0:    Pair seen with volume_1h=$500, price_change_1h=+3%
T=5min: Same pair, volume_1h=$550 (+10%), price_change_1h=+7% (+4%)
        → ALLOWED (price change increase >= 3%)

T=0:    Pair seen with volume_1h=$500, price_change_1h=+3%
T=5min: Same pair, volume_1h=$520 (+4%), price_change_1h=+4% (+1%)
        → BLOCKED (no significant momentum increase)
```

---

## 📝 API DATA MAPPING

### DexScreener API → Normalized Format

```javascript
// DexScreener API response
{
  "priceChange": {
    "h1": 15.3,     // ✅ USED
    "h24": 120.5    // ✅ USED
  },
  "volume": {
    "h1": 5000,     // ✅ USED
    "h24": 80000    // ✅ USED
  },
  "liquidity": {
    "usd": 25000    // ✅ USED
  },
  "txns": {
    "h1": {
      "buys": 15,   // ✅ USED
      "sells": 30   // ✅ USED
    },
    "h24": {
      "buys": 120,  // ✅ USED
      "sells": 200  // ✅ USED
    }
  }
}
```

```python
# Normalized format (NO 5m fields)
{
    "liquidity": 25000,
    "volume_1h": 5000,       # Direct from API
    "volume_24h": 80000,     # Direct from API
    "tx_1h": 45,             # buys + sells from h1
    "tx_24h": 320,           # buys + sells from h24
    "price_change_1h": 15.3, # Direct from API
    "price_change_24h": 120.5 # Direct from API
}
```

---

## 🎯 EXAMPLE SCENARIOS

### ✅ PASS: Low-Volume Breakout
```
Liquidity: $2,000        ✅ (>= $1,000)
Volume h1: $500          ✅ (>= $300)
Volume h24: $3,000       
Spike Ratio: 500/(3000/24) = 4.0x  ✅ (>= 2.0x)
Tx h1: 15                ✅ (>= 10)
→ PASS Level-0 & Level-1
```

### ✅ PASS: Price Momentum
```
Liquidity: $5,000        ✅ (>= $1,000)
Volume h1: $400          ✅ (>= $300)
Price change h1: +8%     ✅ (>= 5%)
Tx h1: 20                ✅ (>= 10)
→ PASS Level-0 & Level-1
```

### ❌ FAIL: Dead Pair
```
Liquidity: $800          ❌ (< $1,000)
→ FAIL Level-0 (Quality Gate)
```

### ❌ FAIL: No Momentum
```
Liquidity: $3,000        ✅ (>= $1,000)
Volume h1: $350          ✅ (>= $300)
Volume h24: $8,400       
Spike Ratio: 350/(8400/24) = 1.0x  ❌ (< 2.0x)
Price change h1: +2%     ❌ (< 5%)
Tx h1: 12                ✅ (>= 10)
→ FAIL Level-1 (Momentum Detection)
```

---

## 🚀 MIGRATION GUIDE

### 1. Update Config File
```python
# OLD (REMOVE)
'min_volume_5m_virtual': 50,
'min_tx_5m_virtual': 2,

# NEW (ADD)
'min_volume_1h': 300,
'min_tx_1h': 10,
```

### 2. No Code Changes Needed
- All modules updated automatically
- Deduplicator backward-compatible
- Logs will show h1 metrics

### 3. Deploy & Monitor
```bash
# Restart service
sudo systemctl restart bot-meme

# Check logs
journalctl -u bot-meme -f | grep OFFCHAIN
```

**Expected Logs:**
```
[OFFCHAIN DEBUG] Processing pair 0xAbCd... | Liq: $2,500 | Vol1h: $820 | Tx1h: 18 | Δ1h: +7.3%
[OFFCHAIN] ✅ DEXSCREENER | BASE | 0xAbCd... | Score: 42.5 | SECONDARY_MARKET
```

---

## ✅ VALIDATION

Run quick test:
```bash
python test_offchain_screener.py
```

Expected result:
- [x] No errors
- [x] At least 1-2 pairs found
- [x] Logs show h1 metrics
- [x] No 5m references

---

**Status: PRODUCTION READY** 🎯
