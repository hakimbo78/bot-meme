# Ultra-Aggressive Anti-Rugpull Mode - Configuration Summary

## Problem Statement
After 2 live trades, rugpulls were happening faster than bot could detect and exit:
- Rugpull execution: 0-5 seconds (instant LP removal)
- Bot detection (old): 30 seconds polling interval
- Bot exit: ~35-40 seconds total → **TOO LATE**

## Solution Implemented

### 1. Entry Prevention (main.py)
**Changed:** Block threshold from 70 → **30**

```python
# OLD
if lp_risk['risk_score'] > 70:  # Only block CRITICAL
    BLOCK

# NEW (ULTRA-AGGRESSIVE)
if lp_risk['risk_score'] > 30:  # Block even MODERATE risk
    BLOCK
```

**Impact:**
- **99% of meme coins will be blocked** (most score 40-60)
- Only ultra-safe tokens (score < 30) can enter
- Philosophy: **Prevention > Detection**

---

### 2. Faster Monitoring (lp_monitor_daemon.py)
**Changed:** Polling interval from 30s → **5s**

```python
# OLD
await asyncio.sleep(30)  # Check every 30 seconds

# NEW
await asyncio.sleep(5)  # Check every 5 seconds
```

**Impact:**
- Detection window: **5-10 seconds** (vs 30-60s before)
- 6x faster response time
- ~12 API calls/minute (vs 2/minute before)

---

### 3. Aggressive Exit (lp_monitor_daemon.py)
**Changed:** Exit thresholds more sensitive

```python
# OLD
if lp_risk['risk_score'] > 70:  # CRITICAL only
if lp_delta_5m < -5:  # 5% drop

# NEW
if lp_risk['risk_score'] > 50:  # HIGH risk (not just critical)
if lp_delta_5m < -2:  # 2% drop (more sensitive)
```

**Impact:**
- Exit triggers **earlier**
- More false-positives possible (may exit legitimate volatile tokens)
- Better safe than sorry

---

## Expected Behavior

### Entry Phase:
```
Token detected → LP Intent check
Risk Score 15 → ✅ PASS (buy)
Risk Score 25 → ⚠️ WARNING (buy with caution)
Risk Score 35 → ❌ BLOCKED [most tokens blocked here]
Risk Score 50 → ❌ BLOCKED
Risk Score 70 → ❌ BLOCKED
```

**Result:** Only ultra-safe tokens (score < 30) can enter.

### Monitoring Phase:
```
Check #1 (t=0s):   Risk 20, LP stable → Continue
Check #2 (t=5s):   Risk 25, LP -1% → Continue
Check #3 (t=10s):  Risk 45, LP -2.5% → 🚨 EXIT (LP drop >2%)
Check #4 (t=15s):  Risk 55, LP -5% → 🚨 EXIT (risk >50)
```

**Result:** Exit within 5-15 seconds of first warning sign.

---

## Trade-offs

### Pros ✅
- **Much faster detection** (5-15s vs 30-60s)
- **Prevent most rugpulls at entry** (block score >30)
- **Earlier exit signals** (2% drop vs 5%)
- Higher chance of escaping before total collapse

### Cons ❌
- **Very low trade frequency** (99% blocked)
- **More API calls** (12/min vs 2/min) - DexScreener rate limit concern
- **More false exits** (legitimate volatile tokens may trigger exit)
- May miss legitimate early opportunities

---

## Recommended Usage

### For Testing (Current Config):
```yaml
Budget per trade: $1
Max positions: 1
Entry threshold: 30 (ultra-strict)
Exit threshold: 50 (aggressive)
Polling: 5 seconds
```

**Test for 24-48 hours to see:**
1. How many trades get blocked (expect >95%)
2. How many false exits happen
3. If any rugpulls still slip through

### If Too Strict (No Trades):
Relax entry threshold to **40** (instead of 30):
```python
if lp_risk['risk_score'] > 40:  # Slightly less strict
```

### If Still Getting Rugged:
Consider:
1. **Don't trade tokens <1 hour old**
2. **Require minimum liquidity >$100k**
3. **Only trade verified/KYC projects**

---

## Files Modified

1. `main.py` - Entry threshold 70 → 30
2. `lp_monitor_daemon.py` - Polling 30s → 5s, Exit 70 → 50, LP drop 5% → 2%

---

## Deployment

```bash
# Stop current processes
pkill -f main.py
pkill -f lp_monitor_daemon.py

# Restart with new settings
python main.py &
python lp_monitor_daemon.py &
```

---

## Monitoring

Watch for these patterns:
```bash
# Check how many trades blocked
grep "BLOCKED BY LP INTENT" logs/main.log | wc -l

# Check exit frequency
grep "EMERGENCY EXIT" logs/lp_monitor.log

# Check average risk scores
grep "LP Intent Risk:" logs/lp_monitor.log
```

---

## Next Steps (If Needed)

If this is still too slow:
1. **WebSocket monitoring** (instant, complex)
2. **Pre-trade simulation** (test sell before buy)
3. **Avoid fresh tokens entirely** (only trade >24h old)

For now, **monitor and tune thresholds** based on real performance.
