# Secondary Scanner Debug Guide

## Latest Deploy: Commit 79fdc4a
**Added comprehensive debug logging to identify parsing bottleneck**

---

## What to Look For in Logs

### 1. Processing Start
```
🔍 [SECONDARY DEBUG] BASE: Processing 52 UNISWAP_V2 events...
```
**This confirms**: Events are being processed

### 2. First Event Details
```
🔍 [SECONDARY DEBUG] First event - data type: <class 'HexBytes'>, topics count: 3
🔍 [SECONDARY DEBUG] token0: 0x4200000000000000000000000000000000000006
🔍 [SECONDARY DEBUG] token1: 0xabcd1234...
🔍 [SECONDARY DEBUG] pair_address: 0x1234abcd...
```
**This shows**: Event data structure and token extraction

### 3. WETH Check (CRITICAL!)
```
🔍 [SECONDARY DEBUG] WETH address: 0x4200000000000000000000000000000000000006
🔍 [SECONDARY DEBUG] token0 == WETH: True
🔍 [SECONDARY DEBUG] token1 == WETH: False
```
**This reveals**: Whether WETH filtering is working

### 4. Summary Statistics
```
📊 [SECONDARY DEBUG] BASE UNISWAP_V2: Parsed 15/52 pairs
   ├─ Skipped (no WETH): 37
   ├─ Skipped (invalid data): 0
   └─ Skipped (parse errors): 0
```
**This explains**: Why pairs are being filtered

---

## Expected Scenarios

### ✅ **SUCCESS** (Pairs Parsed)
```
🔍 [SECONDARY DEBUG] BASE: Processing 52 UNISWAP_V2 events...
🔍 [SECONDARY DEBUG] First event - data type: <class 'HexBytes'>, topics count: 3
🔍 [SECONDARY DEBUG] token0: 0x4200000000000000000000000000000000000006  ← WETH
🔍 [SECONDARY DEBUG] token1: 0xTokenAddress...
🔍 [SECONDARY DEBUG] pair_address: 0xPairAddress...
🔍 [SECONDARY DEBUG] WETH address: 0x4200000000000000000000000000000000000006
🔍 [SECONDARY DEBUG] token0 == WETH: True   ← Match!
📊 [SECONDARY DEBUG] BASE UNISWAP_V2: Parsed 15/52 pairs  ← Success!
   ├─ Skipped (no WETH): 37
✅ [SECONDARY] BASE: Monitoring 15 pairs
```

### ⚠️ **ISSUE: All Pairs Skipped (No WETH)**
```
🔍 [SECONDARY DEBUG] BASE: Processing 52 UNISWAP_V2 events...
🔍 [SECONDARY DEBUG] WETH address: 0x4200000000000000000000000000000000000006
🔍 [SECONDARY DEBUG] token0 == WETH: False  ← No match
🔍 [SECONDARY DEBUG] token1 == WETH: False  ← No match
📊 [SECONDARY DEBUG] BASE UNISWAP_V2: Parsed 0/52 pairs
   ├─ Skipped (no WETH): 52  ← All filtered!
⚠️  [SECONDARY] BASE: No pairs found
```
**Solution**: Need to check WETH address format or broaden filtering

### ⚠️ **ISSUE: Parse Errors**
```
🔍 [SECONDARY DEBUG] BASE: Processing 52 UNISWAP_V2 events...
⚠️  [SECONDARY DEBUG] Error parsing log #0: string index out of range
⚠️  [SECONDARY DEBUG] Error parsing log #1: invalid address checksum
📊 [SECONDARY DEBUG] BASE UNISWAP_V2: Parsed 0/52 pairs
   └─ Skipped (parse errors): 52  ← All failed!
```
**Solution**: Fix address extraction logic

### ⚠️ **ISSUE: Invalid Data**
```
📊 [SECONDARY DEBUG] BASE UNISWAP_V2: Parsed 0/52 pairs
   ├─ Skipped (invalid data): 52  ← Data too short
```
**Solution**: Check data format expectations

---

## Deploy & Monitor Commands

### Deploy
```bash
ssh hakim@38.47.176.142
cd /home/hakim/bot-meme
git pull origin main
sudo systemctl restart bot-meme
```

### Monitor (All Debug)
```bash
journalctl -u bot-meme -f | grep "SECONDARY DEBUG"
```

### Monitor (Summary Only)
```bash
journalctl -u bot-meme -f | grep "📊.*SECONDARY DEBUG"
```

### Monitor (Errors Only)
```bash
journalctl -u bot-meme -f | grep "⚠️.*SECONDARY DEBUG"
```

---

## Next Actions Based on Results

### If "Skipped (no WETH): 52"
➡️ **All pairs filtered out** - Need to:
1. Verify WETH address format matches
2. Consider broadening filter (e.g., also accept USDC pairs)
3. Check if token addresses are extracted correctly

### If "Skipped (parse errors): 52"
➡️ **Address extraction broken** - Need to:
1. Check the error messages
2. Fix hex slicing logic
3. Handle edge cases

### If "Parsed 15/52 pairs"
➡️ **PARTIAL SUCCESS** - Should see:
```
✅ [SECONDARY] BASE: Monitoring 15 pairs
```

---

## V3 Investigation

Currently V3 always shows 0 pairs. After fixing V2, we'll investigate:
1. Are V3 factories correct?
2. Is PoolCreated signature correct?
3. Is data parsing different for V3?

**V3 Factories (from chains.yaml)**:
- BASE: `0x1F98431c8aD98523631AE4a59f267346ea31F984`
- ETHEREUM: `0x1F98431c8aD98523631AE4a59f267346ea31F984`

These are official Uniswap V3 factories, should be correct.
