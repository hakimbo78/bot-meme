# Alert Sending & Scoring Logic Summary

## 1. TELEGRAM ALERT SENDING LOGIC

### When Alerts Are Actually Sent
**File:** [telegram_notifier.py](telegram_notifier.py)

Alerts are sent through the `send_alert_async()` function with the following conditions:

```python
async def send_alert_async(self, token_data, score_data):
    """Send formatted alert to Telegram with enhanced features."""
    if not self.enabled:
        return False
    
    # 1. Check re-alert eligibility
    eligibility = self._check_realert_eligibility(token_address, score_data, token_data)
    
    if not eligibility['eligible']:
        return False  # ALERT BLOCKED by re-alert cooldown
    
    # 2. Check score threshold (must be >= INFO level)
    alert_level = score_data.get('alert_level')
    if not alert_level:
        return False  # ALERT BLOCKED if no alert_level
    
    # 3. Send to Telegram
    await self.bot.send_message(...)
    return True
```

### Alert Eligibility Conditions
**File:** [telegram_notifier.py](telegram_notifier.py#L51-L120)

```python
def _check_realert_eligibility(self, token_address: str, score_data: dict, 
                                token_data: dict) -> dict:
```

**First Alert:** Always eligible (no history)

**Re-alerts:** Must meet ONE of these conditions:

1. **Hourly Limit Check**
   - Max 3 alerts per token per hour
   - `REALERT_MAX_PER_HOUR = 3`
   - Blocked if limit exceeded

2. **Cooldown Period** (15 minutes)
   - `REALERT_COOLDOWN_MINUTES = 15`
   - If still in cooldown, check for significant improvements:
     - **Score improved by 15+** → Re-alert allowed
     - **Liquidity improved by 30%+** → Re-alert allowed
     - **Ownership renounced** → Re-alert allowed
     - Otherwise → Blocked with reason "In cooldown, no significant improvement"
   - After cooldown expires → Re-alert allowed

### Alert Level Classification
**File:** [config.py](config.py#L29-L33)

```python
ALERT_THRESHOLDS = {
    "INFO": 40,   # 40-59: Lower quality signals
    "WATCH": 60,  # 60-74: Medium quality signals
    "TRADE": 75   # 75+: High quality signals
}
```

**Classification Logic** (calculated in score engines):
```
If score >= 75:    "TRADE"     [Red 🟥]
Else if >= 60:     "WATCH"     [Yellow 🟨]
Else if >= 40:     "INFO"      [Blue 🟦]
Else:              No alert sent
```

### Alert Message Format
**File:** [telegram_notifier.py](telegram_notifier.py#L243-L280)

The alert includes:
- Token name, symbol, address
- Score (0-100)
- Age, Liquidity
- Risk flags
- Market intelligence (Pattern matches, Narrative, Smart Money, Conviction)
- Security status
- Operator hints
- Final verdict

---

## 2. SCORE THRESHOLDS & VERDICTS

### Base Score Thresholds (All Chains)
**File:** [config.py](config.py)

```python
ALERT_THRESHOLDS = {
    "INFO": 40,   # Minimum to send alert
    "WATCH": 60,  # Medium quality
    "TRADE": 75   # High quality
}
```

### Solana-Specific Score Thresholds
**File:** [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L56-L63)

```python
self._thresholds = {
    'INFO': self.config.get('alert_thresholds', {}).get('INFO', 30),
    'WATCH': self.config.get('alert_thresholds', {}).get('WATCH', 50),
    'TRADE': self.config.get('alert_thresholds', {}).get('TRADE', 70)
}
```

**Note:** Solana uses slightly lower defaults (30/50/70) but can be overridden by config

### Verdict Determination Logic
**Files:** 
- [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L170-L188)
- [solana_score_engine_vps.py](solana_score_engine_vps.py#L174-L195)

```python
if final_score >= self._thresholds['TRADE']:
    verdict = "TRADE"
elif final_score >= self._thresholds['WATCH']:
    verdict = "WATCH"
elif final_score >= self._thresholds['INFO']:
    verdict = "INFO"
else:
    verdict = "SKIP"

# Determine Skip Reason if Skipped
if verdict == "SKIP":
    if creator_penalty < 0:
        skip_reason = "RISK_FLAG"
    elif score_components["liquidity"] < 10:
        skip_reason = "LOW_LIQUIDITY"
    elif score_components["buy_velocity"] < 5:
        skip_reason = "LOW_BUY_VELOCITY"
    else:
        skip_reason = "LOW_SCORE"
```

### Score Component Breakdown (Max Points)
**File:** [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L85-160)

```
1. Inflow Score          (0-20 points)
2. Velocity Score        (0-20 points)
3. Raydium Score         (0-20 points)
4. Jupiter Score         (0-20 points)
5. Trend Score           (0-10 points)
6. Creator Penalty       (-30 points if creator_sold)
7. Concentration Penalty (-15 to 0 points)

Total Maximum: 100 points
```

**Component Scoring Details:**

**Inflow (SOL inflow from token_data):**
- >= 50 SOL: 20 points
- >= 15 SOL: 15 points
- >= 5 SOL: 10 points
- > 0 SOL: 5 points
- 0 SOL: 0 points

**Velocity (Buy transactions per minute):**
- >= 30 buys/min: 20 points
- >= 15 buys/min: 15 points
- >= 5 buys/min: 10 points
- > 0 buys/min: 5 points
- 0 buys/min: 0 points

**Raydium Pool Presence:**
- Has Raydium AND Liquidity >= $20,000: 20 points
- Has Raydium AND Liquidity >= $10,000: 15 points
- Has Raydium AND Liquidity < $10,000: 10 points
- No Raydium: 0 points (Flag: "No Raydium pool")

**Jupiter Listing:**
- Listed AND Volume >= $100,000: 20 points
- Listed AND Volume >= $10,000: 15 points
- Listed AND Volume < $10,000: 10 points
- Not listed: 0 points

**Liquidity Trend:**
- Growing: 10 points
- Stable: 5 points
- Declining: 0 points (Flag: "Liquidity declining")
- Unknown: 0 points

**Creator & Holder Risk:**
- Creator sold: -30 points (Flag: "⚠️ CREATOR SOLD")
- < 5 unique buyers: -15 points (Flag: "Low buyer diversity")
- 5-9 unique buyers: -5 points
- >= 10 unique buyers: 0 points

### Sniper Score Thresholds
**File:** [sniper/sniper_score_engine.py](sniper/sniper_score_engine.py#L35-40)

```python
self._max_score = self.config.get('sniper_score_max', 90)
self._min_threshold = self.config.get('sniper_score_min_threshold', 80)
```

**Sniper Score Formula:**
```
1. Base Score Contribution: min(base_score * 0.5, 40) points
   - Takes 50% of TokenScorer base_score, max 40 points

2. Momentum Bonus: +15 if confirmed, -10 if not confirmed
   - Early tokens with confirmed momentum get significant boost

3. Liquidity Trend Bonus: +10 (growing), +5 (stable), -15 (declining)
   - Rewards stable/growing liquidity, penalizes dumps

4. Holder Risk Penalties: -5 per flag (max -20 penalty)
   - High concentration (>50%): -5
   - Dev DUMP flag: -10
   - Dev WARNING flag: -5
   - MEV detected: -5
   - Fake pump: -5

Final: max(0, min(total_score, 90))
```

**Sniper Verdict Classification:**
```python
if sniper_score >= 85:
    risk_level = 'OPTIMAL'
elif sniper_score >= 80:  # MIN_THRESHOLD
    risk_level = 'ACCEPTABLE'
elif sniper_score >= 70:
    risk_level = 'ELEVATED'
else:
    risk_level = 'HIGH'
```

---

## 3. LIQUIDITY THRESHOLD ISSUE

### Why Tokens Get "LOW_LIQUIDITY" Flag

**File:** [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L180-190)

```python
# Score components breakdown check
if verdict == "SKIP":
    if score_components["liquidity"] < 10:
        skip_reason = "LOW_LIQUIDITY"
```

**The Problem:**

The `liquidity` score component is calculated as:
```python
score_components["liquidity"] = inflow_score + raydium_score + trend_score
```

It receives **LOW_LIQUIDITY skip reason** when this component < 10 points, which happens when:

1. **No Raydium Pool** (raydium_score = 0) AND
2. **Low/No Inflow** (inflow_score < 5) AND  
3. **No Trend Bonus** (trend_score = 0)

### Minimum Liquidity Requirements by Mode
**File:** [modules/solana/solana_utils.py](modules/solana/solana_utils.py#L318-320)

```python
MIN_LIQUIDITY_SNIPER = 5000       # $5,000 USD for sniper mode
MIN_LIQUIDITY_TRADE = 20000       # $20,000 USD for trading
MIN_LIQUIDITY_RUNNING = 50000     # $50,000 USD for running mode
```

### Why All Tokens Show LOW_LIQUIDITY

**Possible Causes:**

1. **Missing Raydium Pool Data**
   - If `has_raydium_pool` is always False
   - Check SolanaScanner's Raydium detection logic

2. **Missing Inflow Data**
   - If `sol_inflow` is 0 or very low
   - Check token_data['sol_inflow'] calculation

3. **Liquidity Below Raydium Threshold**
   - $liquidity_usd < $10,000 (min for raydium_score)
   - Only receives raydium_score = 0, no points

**Example Scenario:**
```
Token with:
- has_raydium_pool = False (0 points)
- sol_inflow = 0 (0 points)
- liquidity_trend = 'unknown' (0 points)

Result: liquidity_score = 0 + 0 + 0 = 0
        verdict = "SKIP" with reason "LOW_LIQUIDITY"
```

### Score Thresholds for Liquidity Component
**File:** [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L118-128)

```python
# 3. Raydium (+20 max)
has_raydium = token_data.get('has_raydium_pool', False)
liquidity_usd = token_data.get('liquidity_usd', 0)
if has_raydium:
    if liquidity_usd >= MIN_LIQUIDITY_TRADE:        # $20,000
        raydium_score = 20
    elif liquidity_usd >= MIN_LIQUIDITY_TRADE / 2:  # $10,000
        raydium_score = 15
    else:
        raydium_score = 10
else:
    raydium_score = 0  # ← ZERO if no Raydium!
```

### The Root Issue

**All tokens marked LOW_LIQUIDITY likely because:**
- Raydium pool detection is failing (always returning False)
- OR liquidity_usd is not being populated correctly
- OR inflow data is missing from token_data

**Check These Fields in token_data:**
```python
token_data = {
    'has_raydium_pool': bool,      # Critical - likely False for all tokens
    'liquidity_usd': float,         # Critical - likely 0 or missing
    'sol_inflow': float,            # Critical - likely 0 or missing
    'liquidity_trend': str,         # Optional - 'growing'|'stable'|'declining'
}
```

---

## 4. RE-ALERT CONFIGURATION

**File:** [config.py](config.py#L44-48)

```python
# Re-alert settings
REALERT_COOLDOWN_MINUTES = 15
REALERT_SCORE_IMPROVEMENT = 15
REALERT_LIQUIDITY_IMPROVEMENT = 0.30  # 30%
REALERT_MAX_PER_HOUR = 3
```

**Re-alert Tracking:**
- Stored per token address in `self.alert_history`
- Tracks: timestamp, score, liquidity, renounced status, count

---

## 5. SKIP REASONS ENUM

**File:** [modules/solana/solana_score_engine.py](modules/solana/solana_score_engine.py#L13-24)

```python
SKIP_REASONS = [
    "LOW_LIQUIDITY",       # Liquidity score < 10
    "LOW_BUY_VELOCITY",    # Buy velocity score < 5
    "NO_SMART_WALLET",     # No quality wallet activity
    "LOW_PRIORITY_FEE",    # Gas/priority fees insufficient
    "AGE_TOO_YOUNG",       # Token < min age
    "AGE_TOO_OLD",         # Token > max age
    "RISK_FLAG",           # Creator sold or other red flags
    "LOW_SCORE"            # Final score below INFO threshold
]
```

---

## Summary Table

| Component | Threshold | Alert Blocked If | Skip Reason |
|-----------|-----------|-----------------|-------------|
| **Score** | >= 40 | score < 40 | "LOW_SCORE" |
| **Liquidity** | Component < 10 | No Raydium + Low Inflow | "LOW_LIQUIDITY" |
| **Velocity** | Component < 5 | Low buy velocity | "LOW_BUY_VELOCITY" |
| **Risk Flags** | Creator Penalty < 0 | Creator sold | "RISK_FLAG" |
| **Re-alert** | Cooldown 15 min | No improvement + cooldown active | "In cooldown" |
| **Alert Rate** | 3/hour | > 3 alerts/hour | "Max alerts/hour" |

