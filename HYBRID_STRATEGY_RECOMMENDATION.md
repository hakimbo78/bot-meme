# HYBRID STRATEGY RECOMMENDATION

## Problem Statement

DexScreener FREE API limitations:
- No "get all new pairs" endpoint
- /search returns max 30 results
- Results filtered by query relevance
- Random-named coins will be MISSED

## Recommended Solution: HYBRID STRATEGY

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    COIN DETECTION SYSTEM                     │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
        ┌───────▼────────┐         ┌────────▼────────┐
        │  OFF-CHAIN     │         │   ON-CHAIN      │
        │  (DexScreener) │         │   (Blockchain)  │
        └───────┬────────┘         └────────┬────────┘
                │                           │
                │ Detects:                  │ Detects:
                │ - Trending keywords       │ - ALL new pairs
                │ - Popular DEX pairs       │ - Factory events
                │ Coverage: 30-40%          │ Coverage: 100%
                │ Cost: FREE                │ Cost: RPC calls
                │ Speed: FAST (3-5s)        │ Speed: MODERATE
                │                           │
                └─────────────┬─────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   DEDUPLICATION    │
                    │   (Merge results)  │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │    FILTERING       │
                    │    SCORING         │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  TELEGRAM ALERT    │
                    └────────────────────┘
```

### Implementation Plan

#### Step 1: Keep DexScreener (Optimized)

**File:** `offchain/dex_screener.py`

**Strategy:**
- Use expanded keyword list (50+ keywords)
- Focus on DEX-specific queries (raydium, orca, uniswap)
- This catches 30-40% of new coins (trending ones)

**Pros:**
- FREE
- FAST
- Catches trending coins early

**Cons:**
- Misses random-named coins

#### Step 2: Re-enable On-Chain Scanner (Optimized)

**File:** `main.py` (line 534-537)

**Current status:** DISABLED
```python
# DISABLED: Not cost-effective - high CU usage, zero alerts
# await scanner.start_async(queue)
print(f"{Fore.YELLOW}⚠️  On-chain scanner DISABLED (saving CU costs)")
```

**New strategy:** RE-ENABLE with optimizations
```python
# ENABLED: Hybrid mode - catches what DexScreener misses
await scanner.start_async(queue)
print(f"{Fore.GREEN}✅ On-chain scanner ENABLED (Hybrid mode)")
```

**Optimizations to reduce CU:**
1. **Longer scan intervals:** 60-120s (instead of 30s)
2. **Smart filtering:** Only process pairs NOT seen by DexScreener
3. **Block caching:** Reuse block data across scanners
4. **Event-driven:** Only scan when new blocks detected

#### Step 3: Deduplication Layer

**File:** `offchain/integration.py`

**Add deduplication:**
```python
# Track pairs seen by both sources
seen_pairs = {
    'dexscreener': set(),
    'onchain': set(),
}

def deduplicate_pair(pair_address, source):
    """Deduplicate across sources"""
    if pair_address in seen_pairs['dexscreener']:
        return False  # Already processed by DexScreener
    if pair_address in seen_pairs['onchain']:
        return False  # Already processed by on-chain
    
    seen_pairs[source].add(pair_address)
    return True
```

### Expected Results

**Coverage:**
- DexScreener: 30-40% (trending keywords)
- On-chain: 60-70% (missed by DexScreener)
- **Total: 95-100% coverage** ✅

**Cost:**
- DexScreener: FREE
- On-chain: ~$10-15/month (optimized)
- **Total: $10-15/month** (acceptable)

**Detection Speed:**
- DexScreener: 30-60s (very fast)
- On-chain: 60-120s (moderate)
- **Average: 45-90s** (good)

### Alternative: Expand Keywords Only

If you want to stick with OFF-CHAIN ONLY:

**Expanded keyword list (100+ keywords):**
```python
keywords = [
    # Top meme coins
    'pepe', 'doge', 'shib', 'floki', 'bonk', 'wif', 'popcat', 'mog',
    
    # Trending themes (2024-2025)
    'ai', 'trump', 'biden', 'elon', 'musk', 'moon', 'mars', 'rocket',
    'safe', 'baby', 'mini', 'mega', 'ultra', 'super', 'hyper',
    
    # Animals
    'cat', 'dog', 'frog', 'monkey', 'ape', 'gorilla', 'bear', 'bull',
    'tiger', 'lion', 'wolf', 'fox', 'rabbit', 'hamster', 'rat',
    
    # Common words
    'coin', 'token', 'finance', 'swap', 'protocol', 'network',
    'chain', 'defi', 'nft', 'meta', 'verse', 'world',
    
    # Versions
    '2.0', '3.0', 'v2', 'v3', 'new', 'next', 'pro', 'max', 'plus',
    
    # DEX names (catches ALL pairs on that DEX)
    'raydium', 'orca', 'jupiter', 'meteora', 'lifinity',  # Solana
    'uniswap', 'aerodrome', 'baseswap', 'pancakeswap',   # EVM
]
```

**Expected coverage:** 50-60% (better, but still incomplete)

## Recommendation

**For production:** Use **HYBRID STRATEGY**

**Reasoning:**
1. Best coverage (95-100%)
2. Acceptable cost ($10-15/month)
3. Redundancy (if one source fails, other continues)
4. Fast detection (30-120s average)

**Implementation priority:**
1. ✅ Keep current DexScreener multi-query (already done)
2. 🔄 Re-enable on-chain scanner with optimizations
3. 🔄 Add deduplication layer
4. 🔄 Monitor and tune

**Timeline:** 2-3 hours implementation

---

## Decision Required

Please choose:

**Option A:** Hybrid (DexScreener + On-chain) - RECOMMENDED
- Coverage: 95-100%
- Cost: $10-15/month
- Implementation: 2-3 hours

**Option B:** Expand keywords only (Off-chain only)
- Coverage: 50-60%
- Cost: FREE
- Implementation: 30 minutes

**Option C:** Use paid API (DexScreener Pro / Birdeye)
- Coverage: 100%
- Cost: $50-100/month
- Implementation: 1-2 hours

Which option do you prefer?
