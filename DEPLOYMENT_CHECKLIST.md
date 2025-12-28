# Auto-Upgrade System Deployment Checklist

## Pre-Deployment

- [ ] **Review all configuration**
  - [ ] `config.py` - PRIORITY_DETECTOR_CONFIG, SMART_WALLET_CONFIG, AUTO_UPGRADE_ENGINE_CONFIG
  - [ ] `chains.yaml` - Solana priority_detector, smart_wallet_detector, auto_upgrade sections
  
- [ ] **Populate smart wallet database**
  - [ ] Create/update `data/smart_wallets.json` with real profitable wallets
  - [ ] Verify wallet addresses are lowercase
  - [ ] Ensure performance metrics are accurate
  
- [ ] **Test system locally**
  - [ ] Run `python test_auto_upgrade.py`
  - [ ] Verify all 4 tests pass
  - [ ] Check log output for errors

## Module Files Created

### Core Modules
- [x] `solana/priority_detector.py` - TX priority detection
- [x] `solana/smart_wallet_detector.py` - Smart wallet clustering
- [x] `sniper/auto_upgrade.py` - Auto-upgrade engine
- [x] `upgrade_integration.py` - Unified integration
- [x] `telegram_alerts_ext.py` - SNIPER upgrade alerts

### Data & Config
- [x] `data/smart_wallets.json` - Wallet database (with examples)
- [x] `config.py` - Updated with new configs
- [x] `chains.yaml` - Updated Solana section

### Documentation
- [x] `AUTO_UPGRADE_README.md` - Full documentation
- [x] `DEPLOYMENT_CHECKLIST.md` - This file
- [x] `test_auto_upgrade.py` - Test script

## Configuration Validation

### Priority Detector Config
```python
# In config.py - PRIORITY_DETECTOR_CONFIG
✓ compute_threshold: 200000 (200k compute units)
✓ priority_fee_threshold: 10000 (0.00001 SOL)
✓ min_jito_tip: 10000 (0.00001 SOL)  
✓ Scoring weights (compute=15, priority=20, jito=15) = 50 max
```

### Smart Wallet Config
```python
# In config.py - SMART_WALLET_CONFIG
✓ db_path: "data/smart_wallets.json"
✓ Tier 1: 70% success, 10 trades → 40 points
✓ Tier 2: 50% success, 5 trades → 25 points
✓ Tier 3: any success, 3 trades → 15 points
```

### Auto-Upgrade Config
```python
# In config.py - AUTO_UPGRADE_ENGINE_CONFIG
✓ enabled: True
✓ upgrade_threshold: 85 (final score >= 85 triggers upgrade)
✓ max_monitoring_minutes: 30 (monitor for 30 min max)
✓ cooldown_seconds: 300 (5 min between upgrades)
✓ Weights (base=1.0, priority=1.0, smart_wallet=1.0)
```

## Deployment Steps

### 1. Install Dependencies (if needed)
```bash
# No new dependencies required - uses existing Solana SDK
```

### 2. Update Smart Wallet Database
```bash
# Edit data/smart_wallets.json
# Add real profitable wallet addresses with performance data
# Example format in file
```

### 3. Run Tests
```bash
python test_auto_upgrade.py
```

Expected output:
```
✅ Priority Detector: PASSED
✅ Smart Wallet Detector: PASSED
✅ Auto-Upgrade Engine: PASSED
✅ Integration Module: PASSED

🎉 ALL TESTS PASSED! System is ready for production.
```

### 4. Deploy to Production
```bash
# Deploy files to VPS (via rsync or git)
rsync -av --exclude='.venv' --exclude='__pycache__' \
  . hakim@38.47.176.142:/home/hakim/bot-meme/

# SSH to VPS and restart bot
ssh hakim@38.47.176.142
cd /home/hakim/bot-meme
sudo systemctl restart meme-bot
```

### 5. Monitor Logs
```bash
# Watch for auto-upgrade activity
sudo journalctl -u meme-bot -f | grep -E '\[PRIORITY\]|\[SMART_WALLET\]|\[AUTO-UPGRADE\]|\[SNIPER\]'
```

Expected log patterns:
```
[SMART_WALLET] Loaded 10 wallets from database
[AUTO-UPGRADE] Engine initialized (enabled=True, threshold=85)
[AUTO-UPGRADE] Registered: Example Token (ExAmP...)
[PRIORITY] Priority Score: 35/50
[SMART_WALLET] ELITE wallet detected
[AUTO-UPGRADE] ✅ UPGRADE APPROVED: Example Token (72 → 95)
```

## Integration with Main Loop

### Option 1: Standalone Integration (Recommended)
```python
# In main.py after existing imports
from upgrade_integration import UpgradeIntegration
from config import PRIORITY_DETECTOR_CONFIG, SMART_WALLET_CONFIG, AUTO_UPGRADE_ENGINE_CONFIG

# Initialize (after telegram_notifier)
upgrade_integration = UpgradeIntegration({
    'priority_detector': PRIORITY_DETECTOR_CONFIG,
    'smart_wallet': SMART_WALLET_CONFIG,
    'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
})

# In main loop, after TRADE alert is sent:
if alert_level == "TRADE":
    upgrade_integration.register_trade(token_data, score_data)

# Periodically check for upgrades (after processing new pairs):
if upgrade_integration.enabled:
    summary = upgrade_integration.process_pending_upgrades(
        telegram_notifier=telegram,
        # Optional fetchers - implement if you have transaction/wallet data available
        # transaction_fetcher=lambda addr: get_recent_tx(addr),
        # wallet_fetcher=lambda addr: get_top_holders(addr)
    )
    if summary['upgraded'] > 0:
        print(f"[AUTO-UPGRADE] {summary['upgraded']} tokens upgraded to SNIPER")
```

### Option 2: Manual Integration
```python
# For more control, use components individually
from solana.priority_detector import SolanaPriorityDetector
from solana.smart_wallet_detector import SmartWalletDetector
from sniper.auto_upgrade import AutoUpgradeEngine
from telegram_alerts_ext import send_sniper_upgrade_alert

# Initialize
priority_detector = SolanaPriorityDetector(PRIORITY_DETECTOR_CONFIG)
smart_wallet_detector = SmartWalletDetector(SMART_WALLET_CONFIG)
auto_upgrade = AutoUpgradeEngine(AUTO_UPGRADE_ENGINE_CONFIG)

# Use as needed in your workflow
```

## Monitoring & Maintenance

### Daily Checks
- [ ] Review upgrade alerts in Telegram
- [ ] Check upgrade success rate
- [ ] Monitor database size (`data/auto_upgrade_state.json`)
- [ ] Verify no errors in logs

### Weekly Maintenance
- [ ] Update smart wallet database with new profitable wallets
- [ ] Review and adjust thresholds if needed
- [ ] Clean old state files (auto-cleaned, but verify)
- [ ] Backup wallet database

### Performance Metrics
Track these metrics for tuning:
- **Upgrade Rate**: How many TRADE → SNIPER upgrades per day?
- **False Positive Rate**: How many SNIPER alerts were not actually profitable?
- **Smart Wallet Hit Rate**: How often are tier-1 wallets detected?
- **Priority TX Rate**: How often do priority signals appear?

## Troubleshooting

### No Upgrades Happening
1. Check `AUTO_UPGRADE_ENGINE_CONFIG['enabled'] = True`
2. Verify TRADE alerts are being registered (check logs for `[AUTO-UPGRADE] Registered`)
3. Ensure monitoring window hasn't expired (default 30 min)
4. Check if signals are being detected (priority_score or smart_wallet_score > 0)
5. Verify final_score >= 85

### Smart Wallet Scores Always 0
1. Check `data/smart_wallets.json` exists
2. Verify wallet addresses in database are lowercase
3. Ensure wallet performance data meets tier thresholds
4. Check logs for `[SMART_WALLET] Loaded X wallets from database`

### Priority Scores Always 0
1. Verify Solana RPC supports transaction details
2. Check transaction data includes `meta` field
3. Ensure `computeUnitsConsumed` is in meta
4. Test with mock data first

### Telegram Alerts Not Sending
1. Verify TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
2. Check telegram_notifier.enabled is True
3. Test with simple message first
4. Review any Telegram API errors in logs

## Success Criteria

System is working correctly if:
- ✅ Tests pass (`python test_auto_upgrade.py`)
- ✅ TRADE alerts are registered (see `[AUTO-UPGRADE] Registered` logs)
- ✅ Signals are detected when present (priority/smart wallet scores > 0)
- ✅ Upgrades trigger when score >= 85 (see `[AUTO-UPGRADE] ✅ UPGRADE APPROVED`)
- ✅ Telegram SNIPER alerts are sent (check Telegram channel)
- ✅ No errors in production logs

## Rollback Plan

If issues arise, rollback steps:
1. Set `AUTO_UPGRADE_ENGINE_CONFIG['enabled'] = False` in config.py
2. Restart bot: `sudo systemctl restart meme-bot`
3. System continues normal TRADE alerts without auto-upgrade
4. Fix issues and re-deploy
5. Re-enable: `AUTO_UPGRADE_ENGINE_CONFIG['enabled'] = True`

## Support & Further Reading

- See `AUTO_UPGRADE_README.md` for detailed documentation
- Run `python test_auto_upgrade.py` for system validation
- Check logs with: `grep -E '\[PRIORITY\]|\[SMART_WALLET\]|\[AUTO-UPGRADE\]' logs.txt`

---

**Last Updated**: 2025-12-27  
**System Status**: ✅ Ready for Production Deployment
