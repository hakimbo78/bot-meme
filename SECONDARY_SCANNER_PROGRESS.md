# Secondary Scanner Fix Progress - 2025-12-29

## Status: IN PROGRESS ⚠️

Log menunjukkan progress yang baik, tapi masih ada issue parsing.

## ✅ Yang Sudah Fixed:

### 1. RPC Error -32602 (FIXED ✅)
**Problem**: Topics parameter invalid
```
Error: 'Invalid params', 'data': 'invalid type: string "0x0d36...", expected a sequence'
```
**Solution**: Changed `topics = signature` → `topics = [signature]`

### 2. Event Signatures (FIXED ✅)
**Problem**: Extra characters in Keccak-256 hashes (67 chars instead of 66)
```
Error: 'Invalid variadic value or array type'
```
**Solution**: Removed extra chars from all event signatures

### 3. Event Query Success (FIXED ✅)
```
✅ BASE: Found 54 UNISWAP_V2 pairs
✅ ETHEREUM: Found 59 UNISWAP_V2 pairs
```

## ❌ Current Issue: Event Data Parsing

### Problem
Events ditemukan (54 + 59 pairs), tapi tidak masuk monitoring:
```
⚠️  [SECONDARY] BASE: No pairs found      ← Found 54 but parsed 0
⚠️  [SECONDARY] ETHEREUM: No pairs found  ← Found 59 but parsed 0
- BASE: Monitoring 0 pairs
- ETHEREUM: Monitoring 0 pairs
```

### Root Cause
Event data parsing gagal karena:
1. `log['data']` dan `log['topics']` adalah `HexBytes` objects
2. Original code mencoba string slicing langsung: `data[2:66]`
3. Pair address extraction logic salah

### Latest Fix (Commit d557c4d)
**Improvements:**
1. ✅ Added `HexBytes` to hex string conversion
2. ✅ Fixed pair address extraction:
   - V2: Extract last 40 chars (20 bytes address)
   - V3: Extract from correct position
3. ✅ Added debug logging untuk tracking:
   ```python
   print(f"✅ [SECONDARY] {chain}: Parsed {parsed_count}/{total} {dex_type} pairs")
   print(f"⚠️  [SECONDARY DEBUG] Error parsing log: {e}")  # First 3 errors only
   ```

## Expected Next Log Output

### Success Case:
```
🔍 [SECONDARY] BASE: Found 54 UNISWAP_V2 pairs in last 3000 blocks
✅ [SECONDARY] BASE: Parsed 15/54 UNISWAP_V2 pairs  ← NEW: Shows parsing success
✅ [SECONDARY] BASE: Monitoring 15 pairs             ← Should have pairs now
```

### Debug Case (if still failing):
```
🔍 [SECONDARY] BASE: Found 54 UNISWAP_V2 pairs
⚠️  [SECONDARY DEBUG] Error parsing log: invalid address checksum
⚠️  [SECONDARY DEBUG] Error parsing log: string index out of range
⚠️  [SECONDARY DEBUG] Error parsing log: ...
⚠️  [SECONDARY] BASE: No pairs found
```

## Next Steps

1. **Deploy latest fix**:
   ```bash
   cd /home/hakim/bot-meme
   git pull origin main
   sudo systemctl restart bot-meme
   ```

2. **Check new logs**:
   ```bash
   journalctl -u bot-meme -n 100 | grep SECONDARY
   ```

3. **If still failing**:
   - Look for `[SECONDARY DEBUG]` messages
   - Share the debug error messages
   - May need to inspect actual event data structure

## Commits History
```
d557c4d - fix: improve event data parsing with proper HexBytes handling and debug logging
c01ead3 - fix: correct event signatures - remove extra chars from Keccak-256 hashes  
d7b1f91 - fix: secondary scanner RPC -32602 error - topics parameter must be array not string
```

## Technical Details

### Uniswap V2 PairCreated Event Structure
```solidity
event PairCreated(
    address indexed token0,    // topics[1]
    address indexed token1,    // topics[2]
    address pair,              // data (padded to 32 bytes)
    uint256                    // data (counter)
);
```

### Data Parsing Logic
```python
# Before (WRONG):
pair_address = '0x' + data[2:66]  # Assumes string with 0x prefix

# After (CORRECT):
data_hex = data.hex() if hasattr(data, 'hex') else data  # Convert HexBytes
pair_address = '0x' + data_hex[-40:]  # Last 20 bytes = 40 hex chars
```

## Files Modified
- `secondary_scanner/secondary_market/secondary_scanner.py`
  - Line 175-227: Improved event data parsing with HexBytes support
  - Added debug logging for troubleshooting
  - Fixed address extraction logic

## Monitoring Commands
```bash
# Full secondary scanner logs
journalctl -u bot-meme -f | grep SECONDARY

# Only debug messages (if parsing fails)
journalctl -u bot-meme -f | grep "SECONDARY DEBUG"

# Only success messages
journalctl -u bot-meme -f | grep "Parsed.*pairs"
```
