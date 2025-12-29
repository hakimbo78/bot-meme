# ACTIVITY SCANNER - MAIN.PY INTEGRATION GUIDE

**Quick Reference for Adding Activity Scanner to main.py**

---

## STEP 1: Add Imports (Top of main.py)

Add after line 41-49 (where secondary scanner is imported):

```python
# Activity Scanner (2025-12-29)
ACTIVITY_SCANNER_AVAILABLE = False
try:
    from secondary_activity_scanner import SecondaryActivityScanner
    from activity_integration import ActivityIntegration
    ACTIVITY_SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Activity scanner not available: {e}")
```

---

## STEP 2: Initialize Activity Integration (In main() function)

Add after secondary scanner initialization (around line 200-250):

```python
# ================================================
# ACTIVITY SCANNER SETUP (2025-12-29)
# ================================================
activity_integration = None
if ACTIVITY_SCANNER_AVAILABLE:
    activity_integration = ActivityIntegration(enabled=True)
    
    # Register scanner for each enabled chain
    for chain_name in enabled_chains:
        chain_config = chain_configs.get('chains', {}).get(chain_name, {})
        
        # Check if secondary scanner enabled for this chain
        if chain_config.get('secondary_scanner', {}).get('enabled', False):
            try:
                # Get web3 provider for this chain
                adapter = chain_adapters.get(chain_name)
                if adapter and hasattr(adapter, 'web3'):
                    scanner = SecondaryActivityScanner(
                        web3=adapter.web3,
                        chain_name=chain_name,
                        chain_config=chain_config
                    )
                    activity_integration.register_scanner(chain_name, scanner)
                    print(f"✅ [ACTIVITY] Registered scanner for {chain_name.upper()}")
            except Exception as e:
                print(f"⚠️  [ACTIVITY] Failed to register {chain_name}: {e}")
    
    # Print status
    if activity_integration:
        print(f"\n🔥 ACTIVITY SCANNER: ENABLED")
        activity_integration.print_status()
else:
    print("❌ [ACTIVITY] Activity scanner not available")
```

---

## STEP 3: Add Producer Task (In main() function)

Add new async function inside main(), after run_secondary_producer() (around line 510):

```python
# ================================================
# ACTIVITY SCANNER PRODUCER TASK
# ================================================
async def run_activity_producer():
    """Scan for activity signals across all chains"""
    if not ACTIVITY_SCANNER_AVAILABLE or not activity_integration:
        return
    
    print(f"{Fore.BLUE}🔥 Activity scanner task started")
    
    while True:
        try:
            await asyncio.sleep(30)  # Scan every 30 seconds
            
            # Scan all registered chains
            signals = activity_integration.scan_all_chains()
            
            if signals:
                print(f"{Fore.BLUE}🎯 [ACTIVITY] {len(signals)} signals detected")
                
                for signal in signals:
                    # Check DEXTools guarantee rule
                    should_force = activity_integration.should_force_enqueue(signal)
                    
                    if should_force or signal.get('activity_score', 0) >= 60:
                        # Enrich signal with activity context
                        enriched_data = activity_integration.process_activity_signal(signal)
                        
                        # Add to main queue for processing
                        await queue.put(enriched_data)
                        
                        print(f"{Fore.CYAN}🔥 [ACTIVITY] Enqueued: {signal.get('pool_address', 'UNKNOWN')[:10]}... (score: {signal.get('activity_score', 0)})")
                        
                        # Send immediate activity alert (optional - can also wait for full analysis)
                        if telegram.enabled and should_force:
                            telegram.send_activity_alert(signal)
        
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Producer error: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(30)
```

---

## STEP 4: Add Consumer Handling (Modify consumer_task)

Add this section in consumer_task(), BEFORE the "EVM PROCESSING" section (around line 620):

```python
            # ================================================
            # ACTIVITY-DETECTED TOKEN PROCESSING
            # ================================================
            elif pair_data.get('activity_override') or pair_data.get('source') == 'secondary_activity':
                try:
                    chain_name = pair_data.get('chain', 'unknown')
                    chain_prefix = f"[{chain_name.upper()}]"
                    pool_address = pair_data.get('pool_address', pair_data.get('pair_address', 'UNKNOWN'))
                    
                    print(f"{Fore.CYAN}🔥 {chain_prefix} [ACTIVITY] Processing pool {pool_address[:10]}...")
                    
                    # Get chain config
                    chain_config = scanner.get_chain_config(chain_name)
                    
                    # Import activity integration helpers
                    from activity_integration import apply_activity_context_to_analysis
                    
                    # Analyze token (if we have token address)
                    token_address = pair_data.get('token_address')
                    
                    if token_address:
                        # Run full analysis
                        try:
                            analysis = analyzer.analyze_token(token_address, chain_config)
                            
                            # Apply activity context
                            enriched_analysis = apply_activity_context_to_analysis(
                                analysis,
                                pair_data
                            )
                            
                            # Score with activity overrides
                            score_data = scorer.score_token(enriched_analysis, chain_config)
                            
                            # Log result
                            print(f"{Fore.CYAN}   Score: {score_data.get('score', 0)} | Verdict: {score_data.get('verdict', 'UNKNOWN')}")
                            
                            # Send activity alert if qualifies
                            if score_data.get('alert_level'):
                                telegram.send_activity_alert(pair_data, score_data)
                                print(f"{Fore.GREEN}📨 {chain_prefix} [ACTIVITY] Alert sent!")
                        
                        except Exception as analyze_e:
                            print(f"{Fore.YELLOW}⚠️  {chain_prefix} [ACTIVITY] Analysis error: {analyze_e}")
                    
                    else:
                        # No token address yet - send initial activity alert
                        print(f"{Fore.YELLOW}   Token address not resolved - sending initial alert")
                        telegram.send_activity_alert(pair_data)
                
                except Exception as act_e:
                    print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Processing error: {act_e}")
                    import traceback
                    traceback.print_exc()
```

---

## STEP 5: Add to Task List (In main() function)

Add after line where tasks are created (around line 880-900):

```python
# Add activity producer task
if ACTIVITY_SCANNER_AVAILABLE and activity_integration:
    tasks.append(asyncio.create_task(run_activity_producer()))
    print(f"{Fore.GREEN}✅ Activity scanner producer added to task list")
```

---

## STEP 6: Test Locally

```bash
# Run bot
python main.py

# Look for:
# ✅ [ACTIVITY] Registered scanner for BASE
# ✅ [ACTIVITY] Registered scanner for ETHEREUM
# 🔥 ACTIVITY SCANNER: ENABLED
# 🔥 Activity scanner task started
# 🔍 [ACTIVITY] BASE: Scanning blocks...
# 🎯 [ACTIVITY] N signals detected
```

---

## VERIFICATION CHECKLIST

- [ ] Imports added (step 1)
- [ ] Activity integration initialized (step 2)
- [ ] Producer task added (step 3)
- [ ] Consumer handling added (step 4)
- [ ] Task added to list (step 5)
- [ ] Bot starts without errors
- [ ] Logs show activity scanner messages
- [ ] At least 1 chain registered

---

## ROLLBACK (If Needed)

If issues occur:

1. Comment out imports from Step 1
2. Comment out producer task from Step 3
3. Comment out consumer handling from Step 4
4. Restart bot

Bot will continue working with existing secondary scanner.

---

## EXPECTED OUTPUT

After successful integration:

```
✅ [ACTIVITY] Registered scanner for BASE
✅ [ACTIVITY] Registered scanner for ETHEREUM

🔥 ACTIVITY SCANNER: ENABLED
   ├─ Enabled: True
   ├─ Total signals: 0
   ├─ Active scanners: 2
   ├─ BASE: 0 signals, 0 pools monitored
   ├─ ETHEREUM: 0 signals, 0 pools monitored
   └─ Integration: ACTIVE ✅

🔥 Activity scanner task started
🔍 [ACTIVITY] BASE: Scanning blocks 12345678 to 12345680
🔍 [ACTIVITY] ETHEREUM: Scanning blocks 19876543 to 19876545
```

After 1-2 minutes:

```
🎯 [ACTIVITY] BASE: Monitoring 15 pools
🎯 [ACTIVITY] ETHEREUM: Monitoring 23 pools
🔥 [ACTIVITY] 2 signals detected
🔥 [ACTIVITY] Enqueued: 0x1234567890... (score: 75)
📨 [BASE] [V3 ACTIVITY] Alert sent!
```

---

## TROUBLESHOOTING

### Issue: "Activity scanner not available"

**Solution:**
```bash
# Verify files exist
ls -la secondary_activity_scanner.py
ls -la activity_integration.py

# Check for syntax errors
python -c "import secondary_activity_scanner"
python -c "import activity_integration"
```

### Issue: "No pools monitored"

**Possible causes:**
1. No Swap events in recent blocks (normal if market quiet)
2. RPC connection issues
3. Event signatures incorrect

**Solution:**
```bash
# Check logs for RPC errors
journalctl -u bot-meme -f | grep ACTIVITY

# Verify event signatures
python get_correct_signatures.py
```

### Issue: "Activity signals but no alerts"

**Possible causes:**
1. Activity score < threshold
2. Telegram disabled
3. Consumer not processing activity tokens

**Solution:**
- Check activity_score in logs (should be >= 70 for guarantee)
- Verify telegram.enabled == True
- Check consumer task has activity handling code

---

## PERFORMANCE MONITORING

After 24 hours, check:

```python
# In Python shell or add to dashboard
stats = activity_integration.get_integration_stats()

print(f"Total signals: {stats['total_signals']}")
print(f"Signals by chain: {stats['signals_by_chain']}")

for chain, scanner_stats in stats['scanner_stats'].items():
    print(f"\n{chain.upper()}:")
    print(f"  Blocks scanned: {scanner_stats['total_blocks_scanned']}")
    print(f"  Swaps detected: {scanner_stats['total_swaps_detected']}")
    print(f"  Pools tracked: {scanner_stats['total_pools_tracked']}")
    print(f"  Signals generated: {scanner_stats['signals_generated']}")
```

**Healthy metrics (24h):**
- Total signals: 20-100
- Pools tracked: 50-200
- Swaps detected: 500-2000
- CU increase: < 20%

---

*Integration time: ~30 minutes*  
*Risk level: LOW (zero breaking changes)*  
*Rollback time: <5 minutes*
