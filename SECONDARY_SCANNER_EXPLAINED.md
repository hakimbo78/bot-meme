# 📖 SECONDARY MARKET SCANNER - Complete Flow & How It Works

## 🎯 **Apa Itu Secondary Market Scanner?**

Secondary Market Scanner adalah **sistem monitoring untuk token yang SUDAH ADA** (launched) dan mencari **"breakout signals"** - tanda-tanda bahwa token existing akan pump/rally.

**Bedanya dengan Primary Scanner:**
- **Primary Scanner**: Detect **NEW** token launches (PairCreated events)
- **Secondary Scanner**: Monitor **EXISTING** tokens yang sudah punya pair, cari yang mau breakout

---

## 🔄 **Complete Flow**

### **Phase 1: Discovery (Startup) - Satu Kali**

```
Bot Start
    ↓
[1] Scan Recent Pair Created Events
    - Query Uniswap V2/V3 factories
    - V2: Last 6 hours (3000 blocks BASE, 1800 ETH)
    - V3: Last 24 hours (12000 blocks BASE, 7200 ETH)
    ↓
[2] Filter WETH Pairs Only
    - Skip non-WETH pairs (e.g., USDC/USDT pairs)
    - Only monitor [TOKEN]/WETH pairs
    ↓
[3] Build Monitoring List
    - Store 50 most recent pairs per chain
    - Total: ~100 pairs (BASE + ETHEREUM)
    ↓
Ready to Monitor!
```

**Current Status:**
- BASE: 49 V2 pairs
- ETHEREUM: 50 V2 pairs (limit)
- V3: 0 pairs (very low activity)

---

### **Phase 2: Continuous Monitoring - Setiap 30 Detik**

```
Every 30 seconds:

[1] Scan All Monitored Pairs (100 pairs)
    ↓
[2] For Each Pair:
    ├─ Get Current Metrics
    │   ├─ Price
    │   ├─ Liquidity
    │   ├─ Volume (5m, 1h)
    │   ├─ Holders count
    │   └─ Price history
    │
    ├─ Calculate Rolling Metrics
    │   ├─ Volume spike ratio
    │   ├─ Liquidity growth %
    │   ├─ Price change %
    │   └─ Holder growth rate
    │
    ├─ Evaluate Triggers (4 types)
    │   ├─ Volume Spike: 5x in 5min + >$20k vol
    │   ├─ Liquidity Growth: +30% in 1h + >$50k liq
    │   ├─ Price Breakout: +25% in 1h OR new 24h high
    │   └─ Holder Acceleration: 3x growth rate + >200 holders
    │
    ├─ Check Signal Threshold
    │   └─ IF: ≥2 triggers active + risk score ≥70
    │       THEN: SECONDARY SIGNAL! 🎯
    │
    └─ Send Alert (if signal detected)
        └─ Telegram notification with:
            - Token info
            - Active triggers
            - Metrics
            - Risk analysis
    ↓
[3] Discover New Pairs (every scan)
    - Check for NEW pairs created since last scan
    - Add to monitoring list (up to limit)
    ↓
[4] Cleanup
    - Remove old detections
    - Update state
    ↓
Sleep until next cycle (30s)
```

---

## 📊 **Detailed Breakdown**

### **1. Pair Discovery Process**

**What it does:**
```python
# Every 30 seconds, check for new pairs
discover_pairs():
    - Query PairCreated events from Uniswap factories
    - Filter for WETH pairs only
    - Take 50 most recent pairs
    - Add to monitoring list
```

**Why WETH pairs only?**
- Most liquid pairs are [TOKEN]/WETH
- Easy to calculate USD value
- Easier to detect real trading activity
- Skip stablecoin pairs (less relevant for meme trading)

---

### **2. Metrics Collection**

**Per Pair, Every 30s:**

```python
MarketMetrics.update_pair_data():
    1. Query pair contract (Uniswap V2/V3)
    2. Get reserves (token balance, WETH balance)
    3. Calculate price = WETH_reserve / Token_reserve
    4. Calculate liquidity in USD
    5. Track swap events (volume)
    6. Store in rolling windows (5m, 1h, 24h)
```

**Rolling Metrics Calculated:**
- `volume_5m`: Volume in last 5 minutes
- `volume_1h`: Volume in last hour
- `liquidity_delta_1h`: % change in liquidity
- `price_change_1h`: % price change
- `holder_growth_rate`: Holder count growth

---

### **3. Trigger Evaluation**

**4 Independent Triggers:**

#### 📈 **Trigger 1: Volume Spike**
```
Condition: 
  - Volume in last 5m is 5x the 1h average
  - AND volume ≥ $20,000

Example:
  1h avg volume per 5m: $5,000
  Current 5m volume: $30,000
  Ratio: 6x ✅ TRIGGERED!
```

#### 💰 **Trigger 2: Liquidity Growth**
```
Condition:
  - Liquidity grew ≥30% in last hour
  - AND current liquidity ≥ $50,000

Example:
  1h ago: $100,000
  Now: $140,000
  Growth: 40% ✅ TRIGGERED!
```

#### 🚀 **Trigger 3: Price Breakout**
```
Condition (either):
  - Price up ≥25% in last hour
  OR
  - Price is ≥2% above 24h high (new ATH)

Example:
  1h ago: $0.001
  Now: $0.00135
  Change: +35% ✅ TRIGGERED!
```

#### 👥 **Trigger 4: Holder Acceleration**
```
Condition:
  - Holder growth rate ≥3x
  - AND current holders ≥200

Example:
  Previous growth: 5 holders/minute
  Current growth: 18 holders/minute
  Ratio: 3.6x ✅ TRIGGERED!
```

---

### **4. Signal Generation**

**Combined Signal Logic:**

```python
SECONDARY_SIGNAL = (
    (Active Triggers ≥ 2)  # At least 2 of 4 triggers firing
    AND
    (Risk Score ≥ 70)      # Token seems legitimate
)
```

**Example 1: SIGNAL! ✅**
```
Volume Spike: ✅ (6x spike)
Price Breakout: ✅ (+30%)
Liquidity Growth: ❌
Holder Acceleration: ❌
Risk Score: 75

Result: SIGNAL (2 triggers + good risk) → SEND ALERT!
```

**Example 2: No Signal ❌**
```
Volume Spike: ✅ (8x spike)
Price Breakout: ❌
Liquidity Growth: ❌
Holder Acceleration: ❌
Risk Score: 85

Result: NO SIGNAL (only 1 trigger) → Skip
```

---

## 🎯 **Use Cases - Kapan Berguna?**

### **Case 1: Retroactive Discovery ("Missed the Launch")**
```
Situation:
  - Token launched 2 hours ago
  - You missed the initial pump
  - Now showing strong momentum

Secondary Scanner Detects:
  ✅ Volume spiking (people buying)
  ✅ New ATH breakout
  → ALERT: "Retroactive momentum detected!"
```

### **Case 2: Second Pump Detection**
```
Situation:
  - Token launched yesterday
  - First pump happened, cooled down
  - Now starting second wave

Secondary Scanner Detects:
  ✅ Volume spike (renewed interest)
  ✅ Liquidity growing (big buyers entering)
  → ALERT: "Secondary wave forming!"
```

### **Case 3: Breakout from Accumulation**
```
Situation:
  - Token been quiet for hours
  - Suddenly big volume + price move
  - Holders accelerating

Secondary Scanner Detects:
  ✅ Price breakout (new high)
  ✅ Holder acceleration
  ✅ Volume spike
  → ALERT: "Breakout pattern - 3 triggers!"
```

---

## ⚙️ **Configuration**

### **In chains.yaml:**
```yaml
secondary_scanner:
  enabled: true
  min_volume_5m: 20000      # Minimum 5m volume for alerts
  min_liquidity: 50000      # Minimum liquidity
  min_holders: 200          # Minimum holder count
  min_risk_score: 70        # Minimum risk score
```

### **In Code:**
```python
scan_interval: 30 seconds    # How often to scan pairs
max_pairs_per_scan: 100     # Max pairs to monitor
lookback_v2: 6 hours        # How far back to discover V2 pairs
lookback_v3: 24 hours       # How far back to discover V3 pairs
```

---

## 📱 **Alert Example**

When a signal is detected, you get Telegram alert:

```
🎯 SECONDARY SIGNAL: RETROACTIVE

💎 Token: MEME ($MEME)
📍 Chain: BASE
💱 Pair: 0x1234...5678

🎲 Triggers (3/4):
  📈 Volume Spike
  🚀 Price Breakout  
  👥 Holder Acceleration

📊 Metrics:
  Price: $0.00145 (+35% 1h)
  Liquidity: $180K (+45% 1h)
  Volume 5m: $35K
  Holders: 450 (+3.5x growth)

⚠️ Risk Score: 75/100

🕐 Age: 2h 15m
```

---

## 🔄 **State Machine**

Secondary scanner tracks token states:

```
DETECTED (initial signal)
    ↓
    (if momentum continues)
    ↓
CONFIRMED (signal strengthening)
    ↓
    (if triggers keep firing)
    ↓
UPGRADED (→ main TRADE alert)
```

---

## ⏱️ **Timeline Example**

```
T+0min: Token launches
        (Primary scanner catches this)

T+5min: Initial buyers, price stable
        (No secondary signal yet)

T+30min: Small pump, cools down
         (Secondary scanner monitoring)

T+90min: BIG buyer enters
         - Liquidity jumps 50%
         - Volume spikes 8x
         - Price +40%
         ✅ SECONDARY SIGNAL!
         → Alert sent!

T+120min: Momentum confirmed
          - More triggers active
          → UPGRADED to TRADE alert
```

---

## 💡 **Key Points**

1. **Continuous**: Runs every 30 seconds, always monitoring
2. **Selective**: Only alerts on 2+ triggers + good risk score
3. **Retroactive**: Catches tokens you missed at launch
4. **Dynamic**: Adapts to changing market conditions
5. **Filter-Heavy**: 100 pairs monitored, ~2-5 alerts per day (high quality)

---

## 🎓 **Summary**

**Secondary Market Scanner:**
- ✅ Monitors 100 existing token pairs
- ✅ Scans every 30 seconds for breakout signals
- ✅ Uses 4 independent triggers (volume, liquidity, price, holders)
- ✅ Only alerts when ≥2 triggers + risk score ≥70
- ✅ Catches "second wave" pumps and retroactive opportunities
- ✅ Complements primary scanner (new launches)

**Perfect for:** Catching tokens that are starting to pump AFTER launch, not just at launch moment.
