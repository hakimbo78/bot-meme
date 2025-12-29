# OFF-CHAIN SCREENER - QUICK REFERENCE

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# The off-chain screener uses aiohttp (should already be installed)
pip install aiohttp colorama
```

### 2. Configure
Edit `offchain_config.py`:
```python
OFFCHAIN_SCREENER_CONFIG = {
    'enabled': True,
    'enabled_chains': ['base'],  # Your chains
    'dextools_enabled': False,   # Optional
}
```

### 3. Test
```bash
# Basic tests (no network required)
python test_offchain_screener.py

# Full integration test (requires network)
python test_offchain_screener.py --full
```

### 4. Integrate into main.py
See `offchain/INTEGRATION_EXAMPLE.py` for detailed code.

---

## 📋 Key Concepts

### Data Flow
```
API → Normalize → Deduplicate → Filter → Score → Queue → Consumer
```

### Filtering Levels
- **Level-0**: Basic (liquidity, volume, tx, age)
- **Level-1**: Momentum (price change OR volume spike OR tx acceleration)
- **DEXTools**: Top 50 bypass all filters

### Scoring Weights
```python
FINAL_SCORE = (OFFCHAIN_SCORE × 0.6) + (ONCHAIN_SCORE × 0.4)
```

### On-Chain Trigger
```python
if FINAL_SCORE >= verify_threshold:  # Default: 60
    trigger_on_chain_verification()
```

---

## 🔧 Common Tasks

### Monitor Filter Effectiveness
```python
from offchain.integration import OffChainScreenerIntegration

screener = OffChainScreenerIntegration(config)
# ... after running ...
screener.print_stats()
```

Look for **Noise reduction: ~95%**

### Adjust Filter Strictness
```python
# In offchain_config.py
'filters': {
    'min_liquidity': 10000,  # Stricter (was 5000)
    'min_price_change_5m': 30.0,  # Stricter (was 20.0)
}
```

### Change Scan Frequency
```python
# In offchain_config.py
'scheduler': {
    'dexscreener_interval_min': 60,  # Slower (was 30)
    'dexscreener_interval_max': 120,  # Slower (was 60)
}
```

### Adjust Score Threshold
```python
# In offchain_config.py
'scoring': {
    'verify_threshold': 70,  # Higher = fewer on-chain calls (was 60)
}
```

---

## 🐛 Troubleshooting

### Issue: No pairs detected
**Check:**
1. Is market active? Try during peak hours.
2. Are filters too strict? Lower thresholds temporarily.
3. Check API status: DexScreener might be down.

**Solution:**
```python
# Temporarily relax filters
'filters': {
    'min_liquidity': 1000,  # Very loose
    'min_price_change_5m': 10.0,  # Very loose
}
```

### Issue: Too many false positives
**Check:**
1. Filter rate in stats (should be ~95%)
2. Off-chain score distribution

**Solution:**
```python
# Tighten filters
'filters': {
    'min_liquidity': 20000,  # Stricter
    'min_price_change_5m': 50.0,  # Stricter
}

# Or raise threshold
'scoring': {
    'verify_threshold': 75,  # Higher bar
}
```

### Issue: Rate limits
**Check:**
- DexScreener: Self-imposed limit (300/min)
- DEXTools: API key plan limit

**Solution:**
```python
# Slow down scans
'scheduler': {
    'dexscreener_interval_min': 60,
    'dexscreener_interval_max': 120,
}
```

### Issue: High RPC usage
**Check:**
1. Verify filter rate is ~95%
2. Check how many pairs trigger on-chain verify

**Solution:**
```python
# Raise verify threshold
'scoring': {
    'verify_threshold': 70,  # Only verify high-confidence pairs
}
```

---

## 📊 Interpreting Statistics

### Expected Values

```
Noise reduction:     95-98%  ✅
Filter rate:         95%+    ✅
Dedup rate:          1-5%    ✅
Cache hit rate:      20-40%  ✅
```

### Red Flags

```
Noise reduction:     < 90%   ⚠️  Filters too loose
Filter rate:         < 90%   ⚠️  Filters not working
Dedup rate:          > 20%   ⚠️  Too slow, increase scan interval
Passed to queue:     > 100/h ⚠️  Too many false positives
```

---

## 🎯 Optimization Guide

### Goal: Maximize Signal Quality
```python
'filters': {
    'min_liquidity': 50000,       # Only established pairs
    'min_price_change_5m': 50.0,  # Only strong momentum
}
'scoring': {
    'verify_threshold': 75,       # High bar
}
```

### Goal: Maximize Signal Quantity
```python
'filters': {
    'min_liquidity': 5000,        # Lower barrier
    'min_price_change_5m': 15.0,  # Catch more signals
}
'scoring': {
    'verify_threshold': 55,       # Lower bar
}
```

### Goal: Minimize RPC Costs
```python
'filters': {
    'min_liquidity': 20000,       # Strict
}
'scoring': {
    'verify_threshold': 80,       # Very high bar
}
'scheduler': {
    'dexscreener_interval_min': 90,  # Slower scans
}
```

---

## 🔐 Security Best Practices

### 1. API Keys
```python
# Don't commit API keys to git
# Use environment variables
import os
'dextools': {
    'api_key': os.getenv('DEXTOOLS_API_KEY', ''),
}
```

### 2. Rate Limiting
```python
# Always respect rate limits
# Use backoff on 429 errors
# Built-in emergency backoff
```

### 3. Error Handling
```python
# All API calls have try-except
# Graceful degradation if source unavailable
# No crashes from bad API responses
```

---

## 📚 Reference

### Module Files
- `base_screener.py` - Abstract interface
- `dex_screener.py` - DexScreener client
- `dextools_screener.py` - DEXTools client
- `normalizer.py` - Data normalization
- `filters.py` - Multi-level filtering
- `cache.py` - TTL cache
- `deduplicator.py` - Duplicate prevention
- `scheduler.py` - Scan scheduling
- `integration.py` - Main orchestrator

### Config File
- `offchain_config.py` - All tunable parameters

### Documentation
- `OFFCHAIN_SCREENER_README.md` - Full documentation
- `INTEGRATION_EXAMPLE.py` - Integration guide

### Testing
- `test_offchain_screener.py` - Test suite

---

## 🆘 Support

### Common Questions

**Q: Do I need a DEXTools API key?**  
A: No, it's optional. DexScreener is free and sufficient.

**Q: Does this replace on-chain scanning?**  
A: No, it filters BEFORE on-chain verification to save RPC calls.

**Q: Will this slow down detection?**  
A: Detection latency: 30-90s (vs immediate). Trade-off for 95% cost savings.

**Q: Can I disable it?**  
A: Yes, set `'enabled': False` in `offchain_config.py`.

**Q: Does it work with existing scanners?**  
A: Yes, fully backward compatible. Existing scanners unaffected.

---

**Last Updated**: 2025-12-29  
**Version**: 1.0.0  
**Status**: Production Ready
