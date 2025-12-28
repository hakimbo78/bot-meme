# Auto-Upgrade System (TRADE → SNIPER)

## Overview

The Auto-Upgrade System continuously monitors TRADE alerts and automatically upgrades them to SNIPER status when priority transaction signals or smart wallet activity is detected.

**READ-ONLY / INFORMATIONAL SYSTEM** — No private keys, no trading execution.

---

## Features

### 1. **TX Priority Detector** (`solana/priority_detector.py`)
Analyzes Solana transactions for priority signals:
- **High compute usage**: >200k compute units
- **Priority fees**: Fees above base transaction fee
- **Jito tips**: Detects system transfers to known Jito tip accounts

#### Scoring:
- High compute: +15 points
- Priority fee: +20 points
- Jito tip: +15 points
- **Max: 50 points**

---

### 2. **Smart Wallet Detector** (`solana/smart_wallet_detector.py`)
Tracks known profitable wallets with historical performance data:
- **Tier 1 (Elite)**: 70%+ win rate, 10+ trades → +40 points
- **Tier 2 (Good)**: 50%+ win rate, 5+ trades → +25 points
- **Tier 3 (Average)**: Any success, 3+ trades → +15 points
- **Max: 40 points**

Database: `data/smart_wallets.json`

#### Adding Wallets:
```python
from solana.smart_wallet_detector import SmartWalletDetector

detector = SmartWalletDetector()
detector.add_wallet("wallet_address_here", {
    'total_trades': 15,
    'wins': 12,
    'avg_profit_multiplier': 3.2,
    'early_entries': 10
})
```

---

### 3. **Auto-Upgrade Engine** (`sniper/auto_upgrade.py`)
Monitors TRADE alerts and upgrades to SNIPER when conditions are met:

#### Upgrade Logic:
```
final_score = base_score + priority_score + smart_wallet_score
final_score = min(95, final_score)

IF final_score >= 85 AND (priority_score > 0 OR smart_wallet_score > 0):
    UPGRADE to SNIPER
```

#### Monitoring Window:
- Max 30 minutes per token
- 5-minute cooldown between upgrades
- Persistent state across restarts

---

## Configuration

### `config.py`
```python
PRIORITY_DETECTOR_CONFIG = {
    "compute_threshold": 200000,  # 200k compute units
    "priority_fee_threshold": 10000,  # lamports
    "min_jito_tip": 10000,  # lamports
    "score_compute": 15,
    "score_priority_fee": 20,
    "score_jito_tip": 15,
}

SMART_WALLET_CONFIG = {
    "db_path": "data/smart_wallets.json",
    "tier1_min_success": 0.70,
    "tier1_min_trades": 10,
    "tier2_min_success": 0.50,
    "tier2_min_trades": 5,
    "score_tier1": 40,
    "score_tier2": 25,
    "score_tier3": 15,
}

AUTO_UPGRADE_ENGINE_CONFIG = {
    "enabled": True,
    "upgrade_threshold": 85,  # 85+ = SNIPER
    "max_monitoring_minutes": 30,
    "cooldown_seconds": 300,  # 5 min
    "base_weight": 1.0,
    "priority_weight": 1.0,
    "smart_wallet_weight": 1.0,
}
```

### `chains.yaml` (Solana section)
```yaml
solana:
  enabled: true
  rpc_url: "your_solana_rpc"
  
  # ... existing config ...
  
  priority_detector:
    enabled: true
    compute_threshold: 200000
    priority_fee_threshold: 10000
    min_jito_tip: 10000
  
  smart_wallet_detector:
    enabled: true
    db_path: "data/smart_wallets.json"
    tier1_min_success: 0.70
    tier1_min_trades: 10
    tier2_min_success: 0.50
    tier2_min_trades: 5
  
  auto_upgrade:
    enabled: true
    upgrade_threshold: 85
    max_monitoring_minutes: 30
    cooldown_seconds: 300
    base_weight: 1.0
    priority_weight: 1.0
    smart_wallet_weight: 1.0
```

---

## Integration

### Using `upgrade_integration.py`
```python
from upgrade_integration import UpgradeIntegration
from config import PRIORITY_DETECTOR_CONFIG, SMART_WALLET_CONFIG, AUTO_UPGRADE_ENGINE_CONFIG

# Initialize
integration = UpgradeIntegration({
    'priority_detector': PRIORITY_DETECTOR_CONFIG,
    'smart_wallet': SMART_WALLET_CONFIG,
    'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
})

# Register TRADE alert for monitoring
integration.register_trade(token_data, score_data)

# In main loop: Process pending upgrades
summary = integration.process_pending_upgrades(
    telegram_notifier=telegram,
    transaction_fetcher=lambda addr: get_recent_tx(addr),
    wallet_fetcher=lambda addr: get_top_holders(addr)
)

print(f"Processed: {summary['processed']}, Upgraded: {summary['upgraded']}")
```

---

## Telegram Alerts

### SNIPER Upgrade Alert Format:
```
🎯 AUTO-UPGRADE: TRADE → SNIPER 🎯
[SOL]

🟥 TRADE → 🔥 SNIPER MODE

Token: Example Token (EXAMPLE)
Chain: [SOL]
Address: ExAmPlE1AbC123DeF456

📊 Score Evolution:
72 (base) + 20 (priority) + 40 (smart wallet) = *95*

🚨 Upgrade Triggers:
• Priority fee: 0.000050 SOL
• ELITE wallet: abc12345... (12/15 wins, 80.0%)

📈 Metrics:
• Age: 5.2 min
• Liquidity: $125,000
• Final Score: 95/95

🛡️ Signals:
• ✅ Momentum confirmed
• ⚡ Priority TX signals detected
• 🐋 Smart money detected

Verdict: SNIPER - High Priority Signal

⚠️ READ-ONLY: Manual analysis required. NO execution.
```

---

## Logging Prefixes

- `[PRIORITY]` - Priority detector logs
- `[SMART_WALLET]` - Smart wallet detector logs
- `[AUTO-UPGRADE]` - Auto-upgrade engine logs
- `[SNIPER]` - Sniper alert logs (existing)
- `[UPGRADE_INTEGRATION]` - Integration module logs

---

## Safety Features

✅ **Read-only informational system**  
✅ **No private keys**  
✅ **No automated trading**  
✅ **Persistent cooldowns** (survive restarts)  
✅ **Score caps** (max 95 to indicate informational nature)  
✅ **Clear Telegram warnings** about manual analysis requirements  

---

## Testing

### 1. Test Priority Detector:
```python
from solana.priority_detector import SolanaPriorityDetector

detector = SolanaPriorityDetector()
result = detector.analyze_transaction(tx_data)
print(f"Priority Score: {result['priority_score']}/50")
print(f"Reasons: {result['priority_reasons']}")
```

### 2. Test Smart Wallet Detector:
```python
from solana.smart_wallet_detector import SmartWalletDetector

detector = SmartWalletDetector()
result = detector.analyze_wallets(['wallet1', 'wallet2'])
print(f"Smart Wallet Score: {result['smart_wallet_score']}/40")
print(f"Tier: {result['highest_tier']}")
```

### 3. Test Full Integration:
```python
from upgrade_integration import UpgradeIntegration

integration = UpgradeIntegration(config)
summary = integration.get_monitoring_summary()
print(f"Monitoring: {summary['monitored_tokens']} tokens")
print(f"Smart Wallets: {summary['smart_wallets']} total, {summary['tier1_wallets']} tier-1")
```

---

## File Structure

```
bot-meme/
├── solana/
│   ├── priority_detector.py          # TX priority detection
│   └── smart_wallet_detector.py      # Smart wallet clustering
├── sniper/
│   └── auto_upgrade.py                # Auto-upgrade engine
├── data/
│   ├── smart_wallets.json             # Wallet database
│   └── auto_upgrade_state.json        # Persistent state
├── upgrade_integration.py             # Unified integration
├── telegram_alerts_ext.py             # SNIPER upgrade alerts
├── config.py                          # Updated with new configs
├── chains.yaml                        # Updated Solana section
└── AUTO_UPGRADE_README.md             # This file
```

---

## Troubleshooting

### Issue: Priority detection not working
**Solution**: Ensure Solana RPC supports transaction details with `meta` and `computeUnitsConsumed`.

### Issue: Smart wallet scores always 0
**Solution**: Check `data/smart_wallets.json` exists and contains wallet data.

### Issue: Upgrades not triggering
**Solution**: 
1. Verify `AUTO_UPGRADE_ENGINE_CONFIG['enabled'] = True`
2. Check final_score >= 85
3. Ensure priority_score > 0 OR smart_wallet_score > 0
4. Check cooldown hasn't expired monitoring window (30 min default)

### Issue: Telegram alerts not sending
**Solution**: Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in `.env` file.

---

## Production Deployment

1. **Populate smart wallet database**:
   - Add known profitable wallets to `data/smart_wallets.json`
   - Use real historical performance data
   - Start with small database, expand over time

2. **Tune thresholds**:
   - Adjust `upgrade_threshold` based on your risk tolerance
   - Modify score weights in config
   - Test with different `max_monitoring_minutes` values

3. **Monitor logs**:
   - Watch for `[AUTO-UPGRADE]` messages
   - Track upgrade success rate
   - Adjust configuration as needed

4. **Backup state**:
   - Regularly backup `data/auto_upgrade_state.json`
   - Backup `data/smart_wallets.json`
   - State persists across restarts

---

## Future Enhancements

- [ ] On-chain wallet performance tracking (auto-populate database)
- [ ] Multi-tier priority levels (beyond elite/good/average)
- [ ] Machine learning for wallet reputation scoring
- [ ] Cross-chain smart wallet detection
- [ ] Historical pattern matching for priority TX sequences
- [ ] API endpoint for querying upgrade status

---

## License & Disclaimer

**READ-ONLY INFORMATIONAL SYSTEM**

This bot is for monitoring and analysis purposes only. It does NOT:
- Hold private keys
- Execute trades automatically
- Provide financial advice
- Guarantee profitability

All alerts require manual review and decision-making. Use at your own risk.
