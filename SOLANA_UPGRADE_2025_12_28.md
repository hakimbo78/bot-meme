# Solana Module Upgrade — Metadata Resolution + Raydium LP Detection

**Date**: 2025-12-28  
**Version**: 2.0.0  
**Status**: ✅ COMPLETE

## 🎯 Objective

Upgrade Solana sniper module to:
1. **Resolve SPL Token Metadata** (name, symbol, decimals, supply)
2. **Detect Raydium Liquidity Pool Creation** in real-time
3. **Auto-upgrade Token State** through validation pipeline
4. **Enforce Safe Mode** — no blind buys without LP + metadata

---

## 📦 New Modules

### 1. `metadata_resolver.py`

**Purpose**: Resolve SPL token metadata via Metaplex protocol

**Key Classes**:
- `TokenMetadata`: Dataclass for resolved metadata
- `MetadataResolver`: Main resolver with caching

**Features**:
- Fetches mint account (decimals, supply)
- Derives Metaplex metadata PDA
- Parses metadata account (name, symbol, URI)
- 30-minute TTL cache by default
- Handles failures gracefully with skip list

**Example Usage**:
```python
resolver = MetadataResolver(client, cache_ttl=1800)
metadata = await resolver.resolve("TokenMintAddress")

# Output:
# TokenMetadata(
#   mint="...",
#   name="DOGEAI",
#   symbol="DGAI", 
#   decimals=9,
#   supply=1000000000,
#   uri="...",
#   metadata_status="RESOLVED"
# )
```

**Logging**:
```
[SOLANA][META] Resolved token DOGEAI (DGAI) decimals=9 supply=1B
[SOLANA][META][WARN] Metadata not found for mint <pubkey>
```

---

### 2. `raydium_lp_detector.py`

**Purpose**: Detect Raydium liquidity pool creation for tokens

**Key Classes**:
- `RaydiumLPInfo`: Dataclass for detected LP
- `RaydiumLPDetector`: Main detector with caching

**Features**:
- Monitors Raydium AMM program instructions
- Parses InitializePool / Initialize2 events
- Extracts pool address, mints, liquidity amounts
- Validates minimum liquidity threshold (10 SOL default)
- Caches detected pools with TTL

**Example Usage**:
```python
detector = RaydiumLPDetector(client, min_liquidity_sol=10.0)

# Detect from transaction
lp_info = await detector.detect_from_transaction(txid, token_mint)

# Check if token has LP
if detector.has_lp(token_mint):
    lp = detector.get_lp(token_mint)
    print(f"LP: {lp.quote_liquidity} SOL")
```

**Logging**:
```
[SOLANA][LP] Raydium LP detected | SOL=18.7 | LP=OK
[SOLANA][LP][SKIP] LP detected but liquidity too low (2.1 SOL)
```

---

### 3. `token_state.py`

**Purpose**: Manage token lifecycle through validation states

**Key Classes**:
- `TokenState`: Enum of possible states
- `TokenStateRecord`: State record for a token
- `TokenStateMachine`: State machine orchestrator

**State Transitions**:
```
DETECTED
   ↓ (metadata resolved)
METADATA_OK
   ↓ (LP detected & valid)
LP_DETECTED
   ↓ (score ≥ threshold)
SNIPER_ARMED
   ↓ (execution)
BOUGHT
   
OR → SKIPPED (validation failed)
```

**Safety Rules** (hardcoded, non-negotiable):
- ❌ NO BUY without metadata resolved
- ❌ NO BUY without LP detected
- ❌ NO BUY if LP < min_lp_sol
- ❌ NO BUY if score < sniper_score_threshold

**Example Usage**:
```python
sm = TokenStateMachine(
    min_lp_sol=10.0,
    sniper_score_threshold=70,
    safe_mode=True
)

# Track token
record = sm.create_token("MintAddress", "DGAI")

# Update with metadata
sm.set_metadata(
    mint="...",
    name="DOGEAI",
    symbol="DGAI",
    decimals=9,
    supply=1000000000
)

# Update with LP
sm.set_lp_detected(
    mint="...",
    pool_address="...",
    base_liquidity=100000000,
    quote_liquidity=18.7,
    quote_liquidity_usd=3740
)

# Update score
sm.update_score("...", 75.5)  # Auto-arms if ≥ threshold

# Check execution readiness
can_execute, reason = sm.can_execute("...")
```

**Logging**:
```
[SOLANA][STATE] DOGEAI upgraded → METADATA_OK
[SOLANA][STATE] DOGEAI upgraded → LP_DETECTED  
[SOLANA][STATE] DOGEAI upgraded → SNIPER_ARMED | score=75.0
[SOLANA][SNIPER] BUY EXECUTED | DOGEAI | amount=0.5 SOL
```

---

## 🔌 Integration Points

### Scanner Updates (`solana_scanner.py`)

**New Attributes**:
```python
self.metadata_resolver = MetadataResolver(client, cache_ttl)
self.lp_detector = RaydiumLPDetector(client, min_liquidity_sol)
self.state_machine = TokenStateMachine(min_lp_sol, sniper_score_threshold, safe_mode)
```

**New Methods**:
```python
# Async metadata resolution
metadata = await scanner.resolve_token_metadata(token_mint)

# Async LP detection
lp_info = await scanner.detect_token_lp(token_mint, txid=None)

# Update score and check state
state = scanner.update_token_score(token_mint, score)

# Check execution readiness
can_execute, reason = scanner.can_execute_sniper(token_mint)

# Get all armed tokens
armed = scanner.get_armed_tokens()
```

**Enhanced `_create_unified_event()`**:
Now includes:
- `state`: Current token state
- `metadata_resolved`: Boolean
- `lp_detected`: Boolean
- `lp_valid`: Boolean
- `token_state_record`: Full state record

---

## ⚙️ Configuration

### `config.py`

```python
SOLANA_SNIPER_CONFIG = {
    'metadata_cache_ttl': 1800,  # 30 minutes
    'min_lp_sol': 10.0,          # Minimum SOL liquidity
    'sniper_score_threshold': 70, # Score to arm sniper
    'safe_mode': True,            # Enforce strict validation
}
```

### `chains.yaml`

```yaml
solana:
  enabled: true
  rpc_url: "https://solana-mainnet.g.alchemy.com/v2/..."
  
  # Metadata Resolution
  metadata_cache_ttl: 1800
  
  # LP Detection
  min_lp_sol: 10.0
  
  # State Machine + Sniper
  sniper_score_threshold: 70
  safe_mode: true
```

---

## 📝 Logging Format

All logs follow this pattern:

### Metadata Resolution
```
[SOLANA][META] Resolved token DOGEAI (DGAI) decimals=9 supply=1B
[SOLANA][META][WARN] Metadata not found for mint <pubkey>
[SOLANA][META] Cache hit: DGAI (DOGEAI)
```

### LP Detection
```
[SOLANA][LP] Raydium LP detected | SOL=18.7 | LP=OK
[SOLANA][LP][SKIP] LP detected but liquidity too low (2.1 SOL < 10.0 min)
```

### State Transitions
```
[STATE] Token created: DGAI (...)
[SOLANA][STATE] DOGEAI upgraded → METADATA_OK
[SOLANA][STATE] DOGEAI upgraded → LP_DETECTED
[SOLANA][STATE] DOGEAI upgraded → SNIPER_ARMED | score=75.0
[STATE] DOGEAI skipped: LP < minimum liquidity
```

### Execution
```
[SOLANA][SNIPER] BUY EXECUTED | DOGEAI | amount=0.5 SOL
```

---

## 🔄 Typical Flow

### Example: Token `DOGEAI`

1. **Detection** (via Pump.fun)
   ```
   [STATE] Token created: DGAI (...)
   ```

2. **Metadata Resolution** (async)
   ```
   [SOLANA][META] Resolved token DOGEAI (DGAI) decimals=9 supply=1B
   [SOLANA][STATE] DOGEAI upgraded → METADATA_OK
   ```

3. **LP Detection** (async)
   ```
   [SOLANA][LP] Raydium LP detected | SOL=18.7 | LP=OK
   [SOLANA][STATE] DOGEAI upgraded → LP_DETECTED
   ```

4. **Scoring + Arming**
   ```
   Scanner calculates score: 75.0 ≥ 70.0 ✅
   [SOLANA][STATE] DOGEAI upgraded → SNIPER_ARMED | score=75.0
   ```

5. **Execution**
   ```
   [SOLANA][SNIPER] BUY EXECUTED | DOGEAI | amount=0.5 SOL
   ```

---

## ✅ Safety Guarantees

### Hard Rules (Non-Negotiable)

```python
# State machine enforces:
if not metadata_resolved:
    return "Cannot execute: metadata not resolved"

if not lp_detected or not lp_valid:
    return "Cannot execute: LP not detected or invalid"

if quote_liquidity < min_lp_sol:
    return f"Cannot execute: LP too low ({lp_sol:.2f} < {min})"

if score < sniper_score_threshold:
    return f"Cannot execute: score too low ({score} < {threshold})"

# Only SNIPER_ARMED tokens can execute
if current_state != TokenState.SNIPER_ARMED:
    return "Cannot execute: token not armed"
```

### Safe Mode

When `safe_mode=True`:
- Metadata must resolve BEFORE LP is recorded
- LP validation is strict
- Failed validations skip token permanently
- All RPC calls are async with rate limiting
- Caches prevent repeated failures

---

## 📊 Cache Strategy

### Metadata Resolver
- **TTL**: 30 minutes (configurable)
- **On Fail**: Skip list for 5 minutes
- **Size**: LRU cache, auto-evicts old entries

### LP Detector
- **TTL**: 1 hour (default)
- **Deduplication**: Processed txids tracked
- **State**: Valid/Invalid/Error status

### State Machine
- **Retention**: 24 hours (configurable cleanup)
- **Transitions**: Full history tracked per token

---

## 🚀 Performance Notes

- **Async Throughout**: All RPC calls are async (no blocking)
- **Rate Limiting**: 0.1s between RPC calls (configurable)
- **Caching**: Metadata and LP info cached aggressively
- **Non-Blocking**: Event loop safe, suitable for high-frequency scanning

---

## 🧪 Testing Checklist

- [x] Metadata resolution for valid tokens
- [x] Metadata caching and TTL expiration
- [x] Fallback handling for missing metadata
- [x] LP detection from transactions
- [x] Liquidity validation (min_lp_sol)
- [x] State machine transitions
- [x] Safe mode enforcement
- [x] Score-based sniper arming
- [x] Can-execute checks
- [x] Logging completeness
- [x] Error handling and graceful degradation

---

## 📖 Integration Examples

### In Scanner Module
```python
from modules.solana.solana_scanner import SolanaScanner

scanner = SolanaScanner(config)
scanner.connect()

# Manually resolve metadata
metadata = await scanner.resolve_token_metadata("TokenMint")

# Manually detect LP
lp = await scanner.detect_token_lp("TokenMint")

# Update score and auto-arm if ready
state = scanner.update_token_score("TokenMint", 75.5)

# Check if ready for execution
can_exec, reason = scanner.can_execute_sniper("TokenMint")

# Get all armed tokens
armed_tokens = scanner.get_armed_tokens()
```

### In External Orchestrator
```python
async def handle_token_detection(token_mint):
    # Resolve metadata
    metadata = await scanner.resolve_token_metadata(token_mint)
    if not metadata:
        return  # Metadata failed, skip
    
    # Detect LP (async, may take 1-2 seconds)
    lp_info = await scanner.detect_token_lp(token_mint)
    if not lp_info:
        return  # LP not found or too low
    
    # Calculate score from other signals
    score = calculate_score(token_mint)
    
    # Update score (may arm sniper)
    state = scanner.update_token_score(token_mint, score)
    
    # If armed, notify execution layer
    if state and state['state'] == 'SNIPER_ARMED':
        await execute_sniper_trade(token_mint, state)
```

---

## 🔐 Hard Rules Summary

```
🚫 WILL NOT BUY if:
  - Metadata not resolved
  - LP not detected
  - LP < min_lp_sol (10 SOL default)
  - Score < sniper_score_threshold (70 default)
  - State ≠ SNIPER_ARMED

✅ WILL BUY only if:
  - Metadata resolved ✓
  - LP detected & valid ✓
  - LP ≥ min_lp_sol ✓
  - Score ≥ sniper_score_threshold ✓
  - State = SNIPER_ARMED ✓
  - safe_mode allows execution
```

---

## 📞 Support

For issues:
1. Check logs for `[SOLANA][META]` and `[SOLANA][LP]` messages
2. Verify RPC connectivity via `scanner.get_stats()`
3. Check state machine status via `state_machine.get_stats()`
4. Verify configuration in `chains.yaml` and `config.py`

---

**Version**: 2.0.0  
**Last Updated**: 2025-12-28  
**Status**: ✅ Production Ready
