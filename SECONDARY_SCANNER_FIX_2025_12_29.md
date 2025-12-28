# Secondary Scanner RPC Fix - 2025-12-29

## Problem
Secondary scanner mengalami error RPC `-32602 Invalid params`:
```
⚠️  [SECONDARY] Error scanning uniswap_v2 factory: {'code': -32602, 'message': 'Invalid params', 
'data': 'invalid type: string "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612", 
expected a sequence at line 1 column 136'}
```

## Root Cause
Parameter `topics` di `eth_getLogs` RPC call dikirim sebagai **string**, padahal seharusnya **array**.

### Error Detail:
- Message: `expected a sequence` → RPC mengharapkan array
- Current: `topics = "0x0d3648..."` → String
- Expected: `topics = ["0x0d3648..."]` → Array

## Solution
Mengubah format `topics` dari string ke array di 2 lokasi:

### 1. Method `discover_pairs()` (Line 135-150)
**Before:**
```python
# Set topics based on dex type
if dex_type == 'uniswap_v2':
    topics = pair_created_sig  # ❌ String
elif dex_type == 'uniswap_v3':
    topics = pair_created_sig  # ❌ String

# Enforce topics string guard
assert isinstance(topics, str), f"Topics must be string, got {type(topics)}"
```

**After:**
```python
# Set topics based on dex type (must be array for eth_getLogs)
if dex_type == 'uniswap_v2':
    topics = [pair_created_sig]  # ✅ Array
elif dex_type == 'uniswap_v3':
    topics = [pair_created_sig]  # ✅ Array

# Enforce topics array guard
assert isinstance(topics, list), f"Topics must be list, got {type(topics)}"
```

### 2. Method `scan_pair_events()` (Line 280-294)
**Before:**
```python
# Enforce topics string
topics = signature  # ❌ String
assert isinstance(topics, str)
```

**After:**
```python
# Enforce topics array (must be array for eth_getLogs)
topics = [signature]  # ✅ Array
assert isinstance(topics, list)
```

## Expected Result
Setelah fix:
- ✅ No more `-32602 Invalid params` errors
- ✅ Secondary scanner dapat query `PairCreated`/`PoolCreated` events
- ✅ BASE dan ETHEREUM chains dapat menemukan pairs
- ✅ Status berubah dari `0 pairs` menjadi `Monitoring N pairs`

## Files Modified
- `secondary_scanner/secondary_market/secondary_scanner.py`

## Testing
```bash
# Restart bot service untuk apply changes
sudo systemctl restart bot-meme

# Monitor logs untuk verify fix
journalctl -u bot-meme -f | grep SECONDARY
```

Expected log output:
```
🔍 [SECONDARY] BASE: Found X uniswap_v2 pairs in last 3000 blocks
🔍 [SECONDARY] BASE: Found Y uniswap_v3 pairs in last 3000 blocks
✅ [SECONDARY] BASE: Monitoring Z pairs
🚀 SECONDARY MARKET SCANNER: ENABLED
    - BASE: Monitoring Z pairs
    - ETHEREUM: Monitoring Z pairs
```

## Technical Notes
- `eth_getLogs` RPC method requires `topics` parameter as **array** type
- Single topic masih harus wrapped dalam array: `[topic]`
- Multiple topics: `[topic1, topic2, ...]`
- Null topics untuk any: `[null, topic2, ...]`

## References
- Ethereum JSON-RPC Specification: `eth_getLogs`
- Web3.py documentation: `web3.eth.get_logs()`
