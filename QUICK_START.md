# Quick Start: Integrating Auto-Upgrade into main.py

## Option 1: Standalone Integration (Recommended)

Add this code to your `main.py`:

### Step 1: Add imports (after existing imports)
```python
from upgrade_integration import UpgradeIntegration
from config import PRIORITY_DETECTOR_CONFIG, SMART_WALLET_CONFIG, AUTO_UPGRADE_ENGINE_CONFIG
```

### Step 2: Initialize (after telegram_notifier initialization)
```python
# Initialize auto-upgrade system
upgrade_integration = UpgradeIntegration({
    'priority_detector': PRIORITY_DETECTOR_CONFIG,
    'smart_wallet': SMART_WALLET_CONFIG,
    'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
})

if upgrade_integration.enabled:
    print(f"{Fore.CYAN}🎯 AUTO-UPGRADE: ENABLED")
    print(f"{Fore.CYAN}    - Upgrade threshold: {AUTO_UPGRADE_ENGINE_CONFIG['upgrade_threshold']}")
    print(f"{Fore.CYAN}    - Monitoring window: {AUTO_UPGRADE_ENGINE_CONFIG['max_monitoring_minutes']} min\n")
```

### Step 3: Register TRADE alerts (in main loop, after sending TRADE alert)
```python
# After: if telegram.enabled and alert_level == "TRADE":
#            telegram.send_alert(analysis, score_result)

# Register TRADE alerts for upgrade monitoring
if upgrade_integration.enabled and alert_level == "TRADE":
    upgrade_integration.register_trade(analysis, score_result)
    print(f"{Fore.CYAN}[AUTO-UPGRADE] Registered {analysis.get('name', 'UNKNOWN')} for monitoring")
```

### Step 4: Process pending upgrades (periodically in main loop)
```python
# At end of main loop iteration, AFTER processing all new pairs

# Process auto-upgrade checks (every scan cycle)
if upgrade_integration.enabled:
    try:
        # Note: This requires transaction and wallet data fetchers
        # If you haven't implemented these yet, pass None and
        # manually call check_signals when you have the data
        
        summary = upgrade_integration.process_pending_upgrades(
            telegram_notifier=telegram
            # Uncomment when you have these functions:
            # transaction_fetcher=lambda addr: get_recent_transactions(addr),
            # wallet_fetcher=lambda addr: get_top_holders(addr)
        )
        
        if summary.get('upgraded', 0) > 0:
            print(f"{Fore.GREEN}[AUTO-UPGRADE] ✅ {summary['upgraded']} token(s) upgraded to SNIPER!")
    
    except Exception as e:
        print(f"{Fore.YELLOW}[AUTO-UPGRADE] Error: {e}")
        # Don't let auto-upgrade errors crash main loop
```

---

## Option 2: Manual Integration (More Control)

If you want more control over the upgrade process:

### Imports:
```python
from solana.priority_detector import SolanaPriorityDetector
from solana.smart_wallet_detector import SmartWalletDetector
from sniper.auto_upgrade import AutoUpgradeEngine
from telegram_alerts_ext import send_sniper_upgrade_alert
```

### Initialize:
```python
priority_detector = SolanaPriorityDetector(PRIORITY_DETECTOR_CONFIG)
smart_wallet_detector = SmartWalletDetector(SMART_WALLET_CONFIG)
auto_upgrade_engine = AutoUpgradeEngine(AUTO_UPGRADE_ENGINE_CONFIG)
```

### Use in main loop:
```python
# 1. Register TRADE alerts
if alert_level == "TRADE":
    auto_upgrade_engine.register_trade_alert(token_data, score_data)

# 2. Check for upgrade signals when you have new transaction/wallet data
if you_have_new_tx_data:
    priority_result = priority_detector.analyze_transaction(tx_data)
    smart_wallet_result = smart_wallet_detector.analyze_wallets(wallet_addresses)
    
    new_signals = {
        'priority_score': priority_result['priority_score'],
        'smart_wallet_score': smart_wallet_result['smart_wallet_score'],
        'priority_reasons': priority_result['priority_reasons'],
        'smart_wallet_reasons': smart_wallet_result['smart_wallet_reasons']
    }
    
    # Check if should upgrade
    upgrade_result = auto_upgrade_engine.check_upgrade(token_address, new_signals)
    
    if upgrade_result['should_upgrade']:
        # Send upgrade alert
        success = send_sniper_upgrade_alert(
            telegram,
            token_data,
            original_score_data,
            final_score_data,
            upgrade_result
        )
```

---

## Minimal Integration (No Transaction/Wallet Data Yet)

If you don't have transaction or wallet fetching implemented yet:

```python
# Just initialize and register TRADE alerts
from upgrade_integration import UpgradeIntegration
from config import AUTO_UPGRADE_ENGINE_CONFIG

upgrade_integration = UpgradeIntegration({
    'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
})

# In main loop:
if alert_level == "TRADE":
    upgrade_integration.register_trade(analysis, score_result)

# Monitoring summary (optional)
if upgrade_integration.enabled:
    summary = upgrade_integration.get_monitoring_summary()
    if summary['monitored_tokens'] > 0:
        print(f"[AUTO-UPGRADE] Monitoring {summary['monitored_tokens']} tokens")
```

**Note**: Without transaction/wallet data, upgrades won't trigger automatically. You'll need to implement fetchers or manually provide signal data.

---

## Testing Integration

After adding to main.py, test with:

```bash
# Run bot in test mode first
python main.py --simulate

# Check for auto-upgrade logs
grep -E '\[AUTO-UPGRADE\]|\[PRIORITY\]|\[SMART_WALLET\]' logs.txt

# Verify Telegram alerts (send test alert)
python -c "
from telegram_alerts_ext import send_sniper_upgrade_alert
from telegram_notifier import TelegramNotifier

notifier = TelegramNotifier()
# ... send test alert
"
```

---

## Full Example Integration

Here's a complete example of where to add code in main.py:

```python
# ============================================================
# IMPORTS SECTION (add new imports)
# ============================================================
from upgrade_integration import UpgradeIntegration
from config import (
    PRIORITY_DETECTOR_CONFIG, 
    SMART_WALLET_CONFIG, 
    AUTO_UPGRADE_ENGINE_CONFIG
)

# ============================================================
# INITIALIZATION SECTION (in main() function)
# ============================================================
def main():
    # ... existing initialization ...
    
    telegram = TelegramNotifier()
    scorer = TokenScorer()
    
    # NEW: Initialize auto-upgrade
    upgrade_integration = UpgradeIntegration({
        'priority_detector': PRIORITY_DETECTOR_CONFIG,
        'smart_wallet': SMART_WALLET_CONFIG,
        'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
    })
    
    if upgrade_integration.enabled:
        print(f"{Fore.CYAN}🎯 AUTO-UPGRADE: ENABLED")
        stats = upgrade_integration.get_monitoring_summary()
        print(f"{Fore.CYAN}    - Threshold: {AUTO_UPGRADE_ENGINE_CONFIG['upgrade_threshold']}")
        print(f"{Fore.CYAN}    - Smart Wallets: {stats['smart_wallets']} ({stats['tier1_wallets']} elite)")
    
    # ============================================================
    # MAIN LOOP
    # ============================================================
    try:
        while True:
            new_pairs = scanner.scan_all_chains()
            
            for pair_data in new_pairs:
                # ... existing token analysis ...
                
                score_result = scorer.score_token(analysis, chain_config)
                alert_level = score_result.get('alert_level')
                
                # Send Telegram alert
                if telegram.enabled and alert_level:
                    telegram.send_alert(analysis, score_result)
                    
                    # NEW: Register TRADE alerts for upgrade monitoring
                    if alert_level == "TRADE" and upgrade_integration.enabled:
                        upgrade_integration.register_trade(analysis, score_result)
                        token_name = analysis.get('name', 'UNKNOWN')
                        print(f"{Fore.CYAN}[AUTO-UPGRADE] Registered: {token_name}")
            
            # NEW: Process pending upgrades after all pairs processed
            if upgrade_integration.enabled:
                try:
                    summary = upgrade_integration.process_pending_upgrades(
                        telegram_notifier=telegram
                    )
                    
                    if summary.get('upgraded', 0) > 0:
                        upgraded = summary['upgraded']
                        print(f"{Fore.GREEN}[AUTO-UPGRADE] ✅ {upgraded} upgraded to SNIPER!")
                
                except Exception as upgrade_error:
                    # Don't crash main loop on upgrade errors
                    print(f"{Fore.YELLOW}[AUTO-UPGRADE] Error: {upgrade_error}")
            
            # Sleep before next scan
            time.sleep(3)
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitoring stopped.")
```

---

## Verifying It Works

After integration, you should see:

### Startup Logs:
```
🎯 AUTO-UPGRADE: ENABLED
    - Threshold: 85
    - Smart Wallets: 3 (1 elite)
```

### During Operation:
```
🟥 [BASE] TRADE ALERT
[AUTO-UPGRADE] Registered: PEPE Token
[AUTO-UPGRADE] Monitoring 1 tokens
```

### When Upgrade Triggers:
```
[PRIORITY] Priority Score: 35/50
[SMART_WALLET] ELITE wallet detected
[AUTO-UPGRADE] ✅ UPGRADE APPROVED: PEPE Token (74 → 95)
[AUTO-UPGRADE] ✅ 1 upgraded to SNIPER!
```

### Telegram:
You'll receive a `🎯 AUTO-UPGRADE: TRADE → SNIPER 🎯` alert.

---

## Troubleshooting

### No upgrades happening?
1. Check `AUTO_UPGRADE_ENGINE_CONFIG['enabled'] = True`
2. Verify you're registering TRADE alerts: look for `[AUTO-UPGRADE] Registered`
3. Check monitoring summary: `integration.get_monitoring_summary()`
4. Ensure priority or smart wallet scores > 0 (requires transaction/wallet data)

### Module import errors?
1. Ensure `solana/__init__.py` exists
2. Check `sniper/__init__.py` includes `AutoUpgradeEngine`
3. Verify all files are in correct directories

### Telegram alerts not sending?
1. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
2. Verify `telegram_alerts_ext.py` is imported correctly
3. Test with standalone script first

---

## Next Steps

1. ✅ Add integration code to main.py
2. ⚪ Implement transaction fetcher (optional)
3. ⚪ Implement wallet fetcher (optional)
4. ⚪ Populate smart wallet database with real wallets
5. ⚪ Deploy and test on VPS
6. ⚪ Monitor production logs
7. ⚪ Tune thresholds based on results

---

**Need Help?**
- See `AUTO_UPGRADE_README.md` for full documentation
- See `DEPLOYMENT_CHECKLIST.md` for deployment steps
- Run `python test_quick.py` to validate setup
