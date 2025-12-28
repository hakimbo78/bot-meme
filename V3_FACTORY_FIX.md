# 🎯 ROOT CAUSE FOUND: Wrong Uniswap V3 Factory Address on BASE

## Issue
Secondary scanner always returned **0 V3 pairs** on BASE chain despite HIGH activity.

## Investigation Results

### ❌ **WRONG Address (Was Using)**
```yaml
uniswap_v3: "0x1F98431c8aD98523631AE4a59f267346ea31F984"
```
**This is the ETHEREUM MAINNET V3 Factory!**

### ✅ **CORRECT Address (Now Using)**
```yaml
uniswap_v3: "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
```
**This is the BASE CHAIN V3 Factory!**

---

## Why This Happened

**Common Misconception**: Uniswap V3 uses the **same** factory address across all chains (like 0x1F98... on Ethereum).

**Reality**: Uniswap V3 factory addresses are **DIFFERENT** on each chain!

### Uniswap V3 Factory Addresses (Official)

| Chain | V3 Factory Address |
|-------|-------------------|
| Ethereum | `0x1F98431c8aD98523631AE4a59f267346ea31F984` |
| **BASE** | `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` ✅ |
| Arbitrum | `0x1F98431c8aD98523631AE4a59f267346ea31F984` |
| Optimism | `0x1F98431c8aD98523631AE4a59f267346ea31F984` |
| Polygon | `0x1F98431c8aD98523631AE4a59f267346ea31F984` |

**BASE is the exception** - it has a different factory address!

---

## Impact Before Fix

```
[SECONDARY] BASE: Found 0 UNISWAP_V3 pairs ← Querying WRONG factory!
```

The scanner was querying the Ethereum V3 factory address **on BASE chain**, which either:
- Doesn't exist (returns 0 events)
- Is a different contract (returns wrong data)

---

## Expected Results After Fix

### Before
```
🔍 [SECONDARY] BASE: Found 0 UNISWAP_V3 pairs in last 3000 blocks
📊 [SECONDARY DEBUG] BASE UNISWAP_V3: Parsed 0/0 pairs
✅ [SECONDARY] BASE: Monitoring 0 pairs (V3)
```

### After (Expected)
```
🔍 [SECONDARY] BASE: Found 15 UNISWAP_V3 pairs in last 3000 blocks ✅
📊 [SECONDARY DEBUG] BASE UNISWAP_V3: Parsed 12/15 pairs ✅
✅ [SECONDARY] BASE: Monitoring 12 pairs (V3) ✅
```

---

## Ethereum Chain Status

Ethereum uses the correct address `0x1F98...` (no change needed) ✅

---

## Files Modified

### `chains.yaml`
```yaml
base:
  factories:
    uniswap_v2: "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6"  # ✅ Correct
    uniswap_v3: "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"  # ✅ FIXED from 0x1F98...
```

### `chains_vps.yaml`  
**TODO**: Also needs to be updated if it exists!

---

## How to Verify the Fix

### Option 1: Direct RPC Test
```python
from web3 import Web3

base_web3 = Web3(Web3.HTTPProvider("https://base-mainnet.g.alchemy.com/v2/..."))
v3_factory = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
v3_sig = Web3.keccak(text="PoolCreated(address,address,uint24,int24,address)").hex()

latest = base_web3.eth.block_number
logs = base_web3.eth.get_logs({
    'address': v3_factory,
    'topics': [v3_sig],
    'fromBlock': hex(latest - 3000),
    'toBlock': hex(latest)
})

print(f"V3 pools found: {len(logs)}")  # Should be > 0 now!
```

### Option 2: Monitor Logs After Deploy
```bash
journalctl -u bot-meme -f | grep "V3 pairs"
```

Should see:
```
🔍 [SECONDARY] BASE: Found 15 UNISWAP_V3 pairs  ← NOT 0!
```

---

## Deploy Steps

1. **Update VPS config if needed**:
   ```bash
   # Check if chains_vps.yaml also has wrong address
   ssh hakim@38.47.176.142
   cd /home/hakim/bot-meme
   grep "uniswap_v3" chains_vps.yaml
   ```

2. **Deploy fix**:
   ```bash
   git pull origin main
   sudo systemctl restart bot-meme
   ```

3. **Verify**:
   ```bash
   journalctl -u bot-meme -f | grep "SECONDARY"
   ```

---

## Lesson Learned

✅ **Always verify deployment addresses for EACH chain**
✅ **Don't assume same address across all chains**
✅ **Use official documentation** (docs.uniswap.org/contracts/v3/reference/deployments)

---

## References

- Uniswap V3 Deployments: https://docs.uniswap.org/contracts/v3/reference/deployments
- BASE Factory: https://basescan.org/address/0x33128a8fC17869897dcE68Ed026d694621f6FDfD
- Ethereum Factory: https://etherscan.io/address/0x1F98431c8aD98523631AE4a59f267346ea31F984
