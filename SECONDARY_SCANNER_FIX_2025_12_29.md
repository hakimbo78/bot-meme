# Secondary Scanner RPC Fix - 2025-12-29

## Problem 1: Invalid Topics Type (FIXED)
Secondary scanner mengalami error RPC `-32602 Invalid params` karena topics dikirim sebagai string.

### Solution ✅
Mengubah `topics` dari string ke array:
```python
# Before: topics = signature  (❌ String)
# After:  topics = [signature] (✅ Array)
```

## Problem 2: Invalid Event Signatures (FIXED)
Setelah fix Problem 1, masih error dengan message berbeda:
```
'Invalid variadic value or array type: data did not match any variant of untagged enum Variadic'
```

### Root Cause
Event signatures memiliki **karakter ekstra** di akhir:
- Seharusnya: 32 bytes = 64 hex chars (+ `0x` = 66 total)
- Actual: 65-67 hex chars (+ `0x` = 67-69 total)

### Solution ✅
Menghapus karakter ekstra dari semua event signatures:

**BEFORE (WRONG - Extra Characters):**
```python
self.swap_signatures = {
    'uniswap_v2': '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822e',  # 67 chars
    'uniswap_v3': '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67b'   # 67 chars
}

self.pair_created_sigs = {
    'uniswap_v2': '0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612',  # 67 chars
    'uniswap_v3': '0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee871103'   # 67 chars
}
```

**AFTER (CORRECT - Proper Keccak-256 Hashes):**
```python
self.swap_signatures = {
    'uniswap_v2': '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822',  # 66 chars ✅
    'uniswap_v3': '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67'   # 66 chars ✅
}

self.pair_created_sigs = {
    'uniswap_v2': '0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9',  # 66 chars ✅
    'uniswap_v3': '0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718'   # 66 chars ✅
}
```

## Event Signature Reference

### Uniswap V2
| Event | Signature String | Keccak-256 Hash |
|-------|------------------|-----------------|
| PairCreated | `PairCreated(address,address,address,uint256)` | `0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9` |
| Swap | `Swap(address,uint256,uint256,uint256,uint256,address)` | `0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822` |

### Uniswap V3
| Event | Signature String | Keccak-256 Hash |
|-------|------------------|-----------------|
| PoolCreated | `PoolCreated(address,address,uint24,int24,address)` | `0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee71718` |
| Swap | `Swap(address,address,int256,int256,uint160,uint128,int24)` | `0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67` |

## Files Modified
- `secondary_scanner/secondary_market/secondary_scanner.py`
  - Line 137-139: Fixed topics to be array
  - Line 284: Fixed topics to be array  
  - Line 50-51: Fixed Swap event signatures
  - Line 56-57: Fixed PairCreated/PoolCreated event signatures

## Expected Results
Setelah deploy fix:
- ✅ No more `-32602 Invalid params` errors
- ✅ Secondary scanner dapat query `PairCreated`/`PoolCreated` events
- ✅ BASE dan ETHEREUM chains dapat menemukan pairs
- ✅ Status berubah dari `0 pairs` menjadi `Monitoring N pairs`

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

## How to Generate Event Signatures
```python
from web3 import Web3

# Format: EventName(type1,type2,...)
signature_string = "PairCreated(address,address,address,uint256)"
hash = Web3.keccak(text=signature_string).hex()
print(hash)  # Should be 66 chars (0x + 64 hex)
```

## References
- Ethereum JSON-RPC Specification: `eth_getLogs`
- Web3.py documentation: `web3.eth.get_logs()`
- Uniswap V2 Docs: https://docs.uniswap.org/contracts/v2/reference/smart-contracts/factory
- Uniswap V3 Docs: https://docs.uniswap.org/contracts/v3/reference/core/interfaces/IUniswapV3Factory
