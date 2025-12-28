# V3 Debug Investigation - Deploy & Monitor

## Changes Deployed (Commit: a821975)

Added detailed V3 debug logging to show:
- Factory address being queried
- Event signature being used
- Topics array format
- Block range

## Deploy Commands

```bash
# SSH to VPS
ssh hakim@38.47.176.142

# Deploy
cd /home/hakim/bot-meme
git pull origin main
sudo systemctl restart bot-meme

# Monitor V3 debug output
journalctl -u bot-meme -f | grep -E "(V3 DEBUG|UNISWAP_V3)"
```

## Expected Debug Output

### If Everything is Correct:
```
🔍 [V3 DEBUG] BASE: Querying V3 factory
   Factory: 0x33128a8fC17869897dcE68Ed026d694621f6FDfD ← BASE V3 factory
   Signature: 0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718
   Topics: ['0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718']
   From block: 40084461 (0x263d06d)
   To block: 40087461 (0x263db65)
🔍 [SECONDARY] BASE: Found 15 UNISWAP_V3 pairs ← Should be > 0!
```

### If Still 0:
```
🔍 [V3 DEBUG] BASE: Querying V3 factory
   Factory: 0x... ← Check this address
   Signature: 0x... ← Verify signature
   Topics: [...] ← Check format
🔍 [SECONDARY] BASE: Found 0 UNISWAP_V3 pairs ← Still 0, investigate why
```

## What to Check in Debug Output

1. ✅ **Factory Address**
   - BASE: Should be `0x33128a8fC17869897dcE68Ed026d694621f6FDfD`
   - ETHEREUM: Should be `0x1F98431c8aD98523631AE4a59f267346ea31F984`

2. ✅ **Event Signature**
   - Should be: `0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718`
   - This is PoolCreated(address,address,uint24,int24,address)

3. ✅ **Topics Format**
   - Should be: `['0x783cca...']` (array with signature)
   - NOT: `'0x783cca...'` (string)

4. ✅ **Block Range**
   - Should be reasonable range (3000 blocks for BASE, 1800 for ETH)

## Possible Issues & Solutions

### Issue 1: Wrong Factory Address
**Symptom**: Factory shows wrong address in debug
**Solution**: Verify chains.yaml has correct addresses

### Issue 2: Event Signature Mismatch
**Symptom**: Signature doesn't match 0x783cca...
**Solution**: Recalculate with Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)")

### Issue 3: V3 Has Low Activity
**Symptom**: Everything looks correct but still 0 events
**Solution**: Try wider block range (10,000+ blocks)

### Issue 4: RPC Error (Silent Failure)
**Symptom**: No error message, just 0 events
**Solution**: Check if RPC call is throwing exception that's being caught

## Next Steps After Getting Debug Output

1. **Share the debug output** - especially the V3 DEBUG lines
2. **Compare BASE vs ETHEREUM** - see if both have same issue
3. **Verify factory addresses** - cross-check with block explorers:
   - BASE: https://basescan.org/address/0x33128a8fC17869897dcE68Ed026d694621f6FDfD
   - ETHEREUM: https://etherscan.io/address/0x1F98431c8aD98523631AE4a59f267346ea31F984

## Manual Test on VPS (Optional)

```bash
# Test V3 factory directly on VPS
cd /home/hakim/bot-meme
python3 diagnose_v3.py
```

This will test:
- Factory contract existence
- Event queries with various parameters
- Compare with V2 (which works)
