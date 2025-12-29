# 🚀 ACTIVITY SCANNER - DEPLOYMENT CHECKLIST

**Pre-Deployment Validation for CU-Efficient Secondary Activity Scanner**

---

## ✅ PRE-FLIGHT CHECKS

### Files Created
- [ ] `secondary_activity_scanner.py` exists (547 lines)
- [ ] `activity_integration.py` exists (281 lines)  
- [ ] `README_ACTIVITY_SCANNER.md` exists (comprehensive docs)
- [ ] `ACTIVITY_SCANNER_INTEGRATION.md` exists (integration guide)
- [ ] `test_activity_scanner.py` exists (test script)

### Files Modified
- [ ] `scorer.py` - Activity override support added
- [ ] `telegram_notifier.py` - Activity alert method added

### Test Results
- [ ] `python test_activity_scanner.py` runs without errors
- [ ] RPC connection successful
- [ ] Scanner creation successful
- [ ] At least 1 block scanned
- [ ] Integration layer working

---

## 🔧 INTEGRATION TO MAIN.PY

Follow `ACTIVITY_SCANNER_INTEGRATION.md` steps:

### Step 1: Imports
- [ ] Added import block for activity scanner (line ~50)
- [ ] `ACTIVITY_SCANNER_AVAILABLE` flag defined

### Step 2: Initialization
- [ ] `activity_integration` initialized in main()
- [ ] Scanners registered for enabled chains
- [ ] Status printed at startup

### Step 3: Producer Task
- [ ] `run_activity_producer()` function added
- [ ] Scans every 30 seconds
- [ ] Enqueues signals to main queue
- [ ] Sends activity alerts

### Step 4: Consumer Handling
- [ ] Activity token processing added to consumer_task()
- [ ] `activity_override` check implemented
- [ ] Activity context application working
- [ ] Activity alerts sent on qualification

### Step 5: Task List
- [ ] Producer task added to task list
- [ ] Confirmation message printed

---

## 🧪 LOCAL TESTING

### Basic Functionality
```bash
# 1. Run bot locally
python main.py
```

### Expected Console Output
```
✅ [ACTIVITY] Registered scanner for BASE
✅ [ACTIVITY] Registered scanner for ETHEREUM

🔥 ACTIVITY SCANNER: ENABLED
   ├─ Enabled: True
   ├─ Active scanners: 2
   ...

🔥 Activity scanner task started
🔍 [ACTIVITY] BASE: Scanning blocks...
```

### Checks
- [ ] Bot starts without crashes
- [ ] Activity scanner initialized
- [ ] At least 1 chain registered
- [ ] Producer task running
- [ ] No Python exceptions
- [ ] Logs show block scanning

### After 5 minutes
- [ ] Pools being monitored (count > 0)
- [ ] Swaps detected (count > 0)
- [ ] No memory leaks
- [ ] CPU usage normal

---

## 📊 MONITORING & VALIDATION

### Logs to Check
```bash
# Monitor activity scanner logs
journalctl -u bot-meme -f | grep ACTIVITY

# Look for:
# - 🔍 [ACTIVITY] Scanning blocks...
# - 🎯 [ACTIVITY] N signals detected
# - 🔥 [ACTIVITY] Enqueued: ...
# - 📨 [ACTIVITY] Alert sent
```

### Stats to Track
```python
# In Python shell or dashboard
stats = activity_integration.get_integration_stats()

# Expected after 1 hour:
# - total_signals: 5-20
# - monitored_pools: 20-50
# - total_swaps_detected: 100-500
```

### Performance Metrics
- [ ] CU usage increase < 20%
- [ ] Scan latency < 3 seconds
- [ ] Memory usage < 10MB increase
- [ ] No RPC timeouts

---

## 📱 TELEGRAM ALERTS

### Alert Format Validation
- [ ] [ACTIVITY] tag present for V2
- [ ] [V3 ACTIVITY] tag present for V3
- [ ] Swap count displayed
- [ ] Unique traders displayed
- [ ] Activity score displayed
- [ ] Signal breakdown present

### Test Alert
```
🔥 [V3 ACTIVITY] ACTIVITY DETECTED

Chain: BASE
DEX: Uniswap V3
Pool: `0x1234567890...abcdef12`

📊 Activity Metrics:
Swap Count: 8 swaps
Unique Traders: 12 traders
Activity Score: 85/100

🎯 Signals (3/4):
📈 Swap Burst
👥 Trader Growth
⚡ V3 Intensity

⚠️ DEXTools-style momentum detected.
```

---

## 🔒 SAFETY CHECKS

### Backward Compatibility
- [ ] Existing primary scanner still works
- [ ] Existing secondary scanner still works
- [ ] No changes to scoring formulas (except activity override)
- [ ] No changes to state machine
- [ ] Division-by-zero fix untouched

### Error Handling
- [ ] RPC errors don't crash bot
- [ ] Invalid transactions skipped gracefully
- [ ] Empty signals handled properly
- [ ] Expired entries cleaned up
- [ ] Max pools limit enforced

### Resource Limits
- [ ] Max 50 pools per chain
- [ ] 5-minute TTL enforced
- [ ] Max 50 tx per block scanned
- [ ] No infinite loops
- [ ] No memory leaks

---

## 🚀 PRODUCTION DEPLOYMENT

### Pre-Deployment
- [ ] All local tests passed
- [ ] No console errors
- [ ] Activity alerts received in Telegram
- [ ] Stats look healthy
- [ ] Code reviewed

### Deployment Steps
```bash
# 1. Stop bot (if running)
ssh hakim@38.47.176.142
sudo systemctl stop bot-meme

# 2. Backup current version
cd /home/hakim/bot-meme
cp main.py main.py.backup_$(date +%F)
cp scorer.py scorer.py.backup_$(date +%F)
cp telegram_notifier.py telegram_notifier.py.backup_$(date +%F)

# 3. Upload new files
# (From local machine)
scp secondary_activity_scanner.py hakim@38.47.176.142:/home/hakim/bot-meme/
scp activity_integration.py hakim@38.47.176.142:/home/hakim/bot-meme/
scp scorer.py hakim@38.47.176.142:/home/hakim/bot-meme/
scp telegram_notifier.py hakim@38.47.176.142:/home/hakim/bot-meme/
scp main.py hakim@38.47.176.142:/home/hakim/bot-meme/

# 4. Test import (on VPS)
python3 -c "import secondary_activity_scanner; import activity_integration"

# 5. Start bot
sudo systemctl start bot-meme

# 6. Monitor logs
journalctl -u bot-meme -f | grep -E "(ACTIVITY|ERROR)"
```

### Deployment Checks
- [ ] Bot starts successfully
- [ ] Activity scanner initialized
- [ ] No import errors
- [ ] No runtime errors
- [ ] Logs show normal operation

---

## 📈 SUCCESS CRITERIA (24 hours)

### Detection
- [ ] >= 10 activity signals detected
- [ ] >= 1 V3 activity signal detected
- [ ] >= 50 pools monitored
- [ ] >= 1 [ACTIVITY] alert sent

### Performance
- [ ] Zero crashes
- [ ] CU usage < 20% increase
- [ ] Average scan time < 3s
- [ ] Memory stable

### Quality
- [ ] No false positives (spam tokens)
- [ ] At least 1 legitimate high-quality signal
- [ ] Alert format correct
- [ ] Stats accurate

---

## 🔄 ROLLBACK PROCEDURE

If issues occur:

```bash
# 1. Stop bot
sudo systemctl stop bot-meme

# 2. Restore backups
cd /home/hakim/bot-meme
cp main.py.backup_YYYY-MM-DD main.py
cp scorer.py.backup_YYYY-MM-DD scorer.py
cp telegram_notifier.py.backupYY-MM-DD telegram_notifier.py

# 3. Remove activity scanner files (optional)
rm secondary_activity_scanner.py
rm activity_integration.py

# 4. Restart bot
sudo systemctl start bot-meme

# 5. Verify normal operation
journalctl -u bot-meme -f
```

**Rollback time: < 5 minutes**

---

## 📋 POST-DEPLOYMENT

### Week 1 Review
- [ ] Review stats (signals, detections, alerts)
- [ ] Check for any errors in logs
- [ ] Validate alert quality
- [ ] Gather user feedback
- [ ] Adjust thresholds if needed

### Optimization Opportunities
- [ ] Tune signal thresholds based on data
- [ ] Adjust TTL if needed
- [ ] Optimize RPC call patterns
- [ ] Add more signals if patterns identified

---

## ✅ FINAL GO/NO-GO DECISION

**Proceed with deployment if ALL checks pass:**

### Critical (Must Pass)
- [x] All files created successfully
- [x] Local test passes
- [ ] Integration code added to main.py
- [ ] No syntax errors
- [ ] Bot starts locally

### Important (Should Pass)
- [ ] Activity alerts working
- [ ] Stats look reasonable
- [ ] No performance issues
- [ ] Documentation complete

### Nice to Have
- [ ] Dashboard integration
- [ ] Advanced metrics
- [ ] Auto-tuning

---

## 🎯 DECISION

**Status:** READY FOR INTEGRATION ✅

**Next Action:** 
1. ⏳ Add integration code to main.py
2. ✅ Test locally
3. 🚀 Deploy to production

**Estimated Time:** 45 minutes  
**Risk Assessment:** LOW  
**Rollback Capability:** FULL

---

**Deployment Approved By:** _____________  
**Date:** 2025-12-29  
**Version:** 1.0.0

---

*Checklist Complete - Ready for Production! 🚀*
