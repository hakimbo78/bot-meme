# MODE C (DEGEN SNIPER) PATCH - APPLIED

## Modified Functions

### 1. `offchain/filters.py`

#### `apply_filters()`
```python
def apply_filters(self, pair: Dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Apply V3 filters and calculate score.
    
    Returns:
        (passed: bool, reason: str or None, metadata: dict or None)
    """
    self.stats['total_evaluated'] += 1
    
    pair_addr = pair.get('pair_address', 'UNKNOWN')[:10]
    
    # 1. Level-0 Filter (Ultra Loose)
    passed_l0, l0_reason = self._check_level0_filter(pair)
    if not passed_l0:
        self.stats['level0_rejected'] += 1
        self._log_drop(pair, f"LEVEL-0: {l0_reason}")
        return False, f"LEVEL-0: {l0_reason}", None
        
    # 2. Level-1 Filter (Momentum) & Revival Rule
    passed_l1, l1_reason = self._check_level1_and_revival(pair)
    if not passed_l1:
        self.stats['level1_rejected'] += 1
        self._log_drop(pair, f"LEVEL-1: {l1_reason}")
        return False, f"LEVEL-1: {l1_reason}", None
        
    # 3. Calculate Score (DOES NOT BLOCK PROCESSING)
    score = self._calculate_score_v3(pair)
    pair['offchain_score'] = score
    
    # Score is used ONLY for tier assignment, NOT for filtering
    self.stats['passed'] += 1
    self.stats['scores'].append(score)
    
    # Determine Verdict
    verdict = "ALERT_ONLY"
    thresholds = self.scoring_config.get('thresholds', {})
    verify_threshold = thresholds.get('verify', 65)
    
    if score >= verify_threshold:
        verdict = "VERIFY"
         
    metadata = {
        'score': score,
        'verdict': verdict,
        'verify_threshold': verify_threshold
    }
    
    return True, None, metadata
```

#### `_check_level1_and_revival()`
```python
def _check_level1_and_revival(self, pair: Dict) -> Tuple[bool, Optional[str]]:
    """
    LEVEL-1 FILTER + REVIVAL RULE
    
    CRITICAL: Uses OR logic for momentum (NOT AND)
    """
    age_days = pair.get('age_days', 0)
    if age_days is None: 
        age_days = 0.0
        
    price_change_5m = pair.get('price_change_5m', 0) or 0
    price_change_1h = pair.get('price_change_1h', 0) or 0
    tx_5m = pair.get('tx_5m', 0)
    
    # REVIVAL RULE: If age > 30 days
    if age_days > 30:
        # Require fresh activity: (price_change_5m >= 5 OR tx_5m >= 5)
        is_revival = (abs(price_change_5m) >= 5) or (tx_5m >= 5)
        if not is_revival:
            return False, f"Old pair ({age_days:.1f}d) no revival momentum"
        return True, None
        
    # MOMENTUM FILTER (OR LOGIC - CRITICAL)
    # Pass if ANY condition is true:
    momentum = (
        abs(price_change_5m) >= 5
        or abs(price_change_1h) >= 15
        or tx_5m >= 5
    )
    
    if not momentum:
        return False, "No momentum (p5m<5, p1h<15, tx5m<5)"
        
    return True, None
```

#### `_log_drop()` (NEW)
```python
def _log_drop(self, pair: Dict, reason: str):
    """Log pair drop with full context (MANDATORY Debug Logging)."""
    print(
        f"[MODE C DROP]\n"
        f"  pair={pair.get('pair_address', 'UNKNOWN')[:10]}...\n"
        f"  pc5m={pair.get('price_change_5m', 0):.2f}\n"
        f"  pc1h={pair.get('price_change_1h', 0):.2f}\n"
        f"  tx5m={pair.get('tx_5m', 0)}\n"
        f"  liquidity=${pair.get('liquidity', 0):,.0f}\n"
        f"  age_days={pair.get('age_days', 0):.2f}\n"
        f"  reason={reason}"
    )
```

---

### 2. `offchain/integration.py`

#### `_process_pair()`
```python
async def _process_pair(self, raw_pair: Dict, source: str, chain: str) -> Optional[Dict]:
    """
    Process a single raw pair through the V3 pipeline.
    
    Pipeline:
    1. Normalize
    2. Filter & Score
    3. Pair Deduplication (Strict 15m cooldown - enforced BEFORE token dedup)
    4. Determine Tier
    5. Telegram Alert (MID/HIGH only - LOW tier suppressed)
    6. Enqueue for On-Chain Verify
    """
    # 1. NORMALIZE
    if source == 'dexscreener':
        normalized = self.normalizer.normalize_dexscreener(raw_pair, source)
    else:
        return None
    
    self.stats['normalized_pairs'] += 1
    
    pair_address = normalized.get('pair_address', '')
    token_address = normalized.get('token_address', '')
    
    if not pair_address or not token_address:
        return None
        
    # 2. FILTERING & SCORING
    passed, reason, metadata = self.filter.apply_filters(normalized)
    
    if not passed:
        self.stats['filtered_out'] += 1
        return None
        
    score = metadata.get('score', 0)
    verdict = metadata.get('verdict', 'ALERT_ONLY')
    normalized['offchain_score'] = score
    normalized['verdict'] = verdict
    
    # 3. PAIR DEDUPLICATION (STRICT 15-MIN COOLDOWN)
    # Check cooldown BEFORE processing further
    if self.deduplicator.is_duplicate(pair_address, chain):
         print(f"[OFFCHAIN] {pair_address[:8]}... - PAIR DUPLICATE (15m cooldown)")
         return None
    
    # 4. DETERMINE TIER
    tier = self._determine_tier(score)
    normalized['tier'] = tier
    
    # 5. MOMENTUM CHECK (ensure fresh activity)
    has_momentum = self._has_momentum(normalized)
    if not has_momentum:
        print(f"[OFFCHAIN] {pair_address[:8]}... - NO MOMENTUM (suppressed)")
        return None
    
    # 6. SEND TELEGRAM ALERT (Tiered - LOW tier suppressed)
    print(f"[OFFCHAIN] ✅ {chain.upper()} | {pair_address[:10]}... | Score: {score:.1f} | Tier: {tier}")
    
    if tier in ['MID', 'HIGH']:
        await self._send_telegram_alert(normalized, chain)
    else:
        # LOW tier - log only, no Telegram
        print(f"[OFFCHAIN] 🔇 LOW TIER - Alert suppressed (logged only)")
    
    # 7. GATEKEEPER
    if verdict == 'VERIFY':
         self.cache.set(pair_address, normalized)
         await self.pair_queue.put(normalized)
         self.stats['passed_to_queue'] += 1
         return normalized
         
    return None
```

#### `_determine_tier()` (NEW)
```python
def _determine_tier(self, score: float) -> str:
    """Determine alert tier based on score."""
    if score >= 70:
        return 'HIGH'
    elif score >= 50:
        return 'MID'
    else:
        return 'LOW'
```

#### `_has_momentum()` (NEW)
```python
def _has_momentum(self, pair: Dict) -> bool:
    """Check if pair has valid momentum (OR logic)."""
    pc5m = abs(pair.get('price_change_5m', 0) or 0)
    pc1h = abs(pair.get('price_change_1h', 0) or 0)
    tx5m = pair.get('tx_5m', 0)
    
    return (pc5m >= 5) or (pc1h >= 15) or (tx5m >= 5)
```

#### `_send_telegram_alert()`
```python
async def _send_telegram_alert(self, normalized: Dict, chain: str):
    """
    Send Telegram alert for MID/HIGH tier pairs only.
    LOW tier is already filtered out in _process_pair.
    """
    try:
        score = normalized.get('offchain_score', 0)
        verdict = normalized.get('verdict', 'ALERT_ONLY')
        tier = normalized.get('tier', 'LOW')
        
        # Build Message
        pair_address = normalized.get('pair_address', 'UNKNOWN')
        token_symbol = normalized.get('token_symbol', 'UNKNOWN')
        
        # Emojis based on Tier
        emoji = "🟡" if tier == 'MID' else "🚨"
        
        message = f"{emoji} [MODE C V3] {tier} TIER {emoji}\n\n"
        message += f"Chain: {chain.upper()}\n"
        message += f"Score: {score:.1f}/100\n"
        message += f"Verdict: {verdict}\n\n"
        
        message += f"📊 Metrics:\n"
        message += f"• Liq: ${normalized.get('liquidity', 0):,.0f}\n"
        message += f"• Vol24: ${normalized.get('volume_24h', 0):,.0f}\n"
        message += f"• Tx5m: {normalized.get('tx_5m', 0)} | Tx24: {normalized.get('tx_24h', 0)}\n"
        message += f"• PC5m: {normalized.get('price_change_5m', 0):.1f}% | PC1h: {normalized.get('price_change_1h', 0):.1f}%\n"
        message += f"• Age: {normalized.get('age_days', 0):.2f} days\n\n"
        
        message += f"🔗 DexScreener: https://dexscreener.com/{chain}/{pair_address}\n"
        
        if verdict == 'VERIFY':
            message += "\n🔍 TRIGGERING ON-CHAIN VERIFICATION..."
        else:
            message += "\n💤 OFF-CHAIN ONLY (RPC Saved)"

        # Send
        await self.telegram_notifier.bot.send_message(
            chat_id=self.telegram_notifier.chat_id,
            text=message,
            parse_mode=None,
            disable_web_page_preview=False
        )
        print(f"[OFFCHAIN] 📱 Sent {tier} Tier Alert")
        
    except Exception as e:
        print(f"[OFFCHAIN] Error sending alert: {e}")
```

---

### 3. `offchain/normalizer.py`

#### `normalize_dexscreener()`
```python
def normalize_dexscreener(self, raw_pair: Dict, source: str = "dexscreener") -> Dict:
    """
    Normalize DexScreener pair data into STRICT V2 format.
    """
    # Extract core fields
    chain = self._normalize_chain(raw_pair.get('chainId', 'unknown'))
    pair_address = raw_pair.get('pairAddress', '')
    base_token = raw_pair.get('baseToken', {})
    token_address = base_token.get('address', '')
    
    # Metrics
    liquidity = self._safe_float(raw_pair.get('liquidity', {}).get('usd', 0))
    volume_24h = self._safe_float(raw_pair.get('volume', {}).get('h24', 0))
    
    price_change = raw_pair.get('priceChange', {})
    price_change_5m = self._safe_float(price_change.get('m5', 0))
    price_change_1h = self._safe_float(price_change.get('h1', 0))
    
    txns = raw_pair.get('txns', {})
    h24_txns = txns.get('h24', {})
    m5_txns = txns.get('m5', {})
    tx_24h = (h24_txns.get('buys', 0) + h24_txns.get('sells', 0)) if h24_txns else 0
    tx_5m = (m5_txns.get('buys', 0) + m5_txns.get('sells', 0)) if m5_txns else 0
    
    # Age
    created_at = raw_pair.get('pairCreatedAt')
    age_days = 0.0
    if created_at:
        try:
            age_ms = datetime.now().timestamp() * 1000 - created_at
            age_days = age_ms / (1000 * 60 * 60 * 24)
            if age_days < 0: age_days = 0
        except:
            pass
            
    # Event Type
    event_type = "SECONDARY_MARKET"
    if age_days < 1.0:
        event_type = "NEW_PAIR"
    
    return {
        "chain": chain,
        "pair_address": pair_address,
        "token_address": token_address,
        "token_name": base_token.get('name', 'UNKNOWN'),
        "token_symbol": base_token.get('symbol', 'UNKNOWN'),
        "liquidity": liquidity,
        "volume_24h": volume_24h,
        "price_change_5m": price_change_5m,
        "price_change_1h": price_change_1h,
        "tx_24h": tx_24h,
        "tx_5m": tx_5m,
        "age_days": age_days,
        "offchain_score": 0,
        "event_type": event_type,
        "source": source
    }
```

---

## Changes Summary

### ✅ Fixed Issues
1. **Momentum Logic**: Changed from AND to OR (any condition passes)
2. **Score Blocking**: Removed score threshold that was killing pairs during processing
3. **Revival Rule**: Fixed to use absolute values for price_change_5m
4. **Telegram Tiering**: LOW tier pairs no longer send Telegram alerts
5. **Deduplication**: Strict 15-min pair cooldown enforced
6. **Debug Logging**: Added mandatory logging before every drop

### ✅ Expected Results
- Pairs now pass filters (>0 processed)
- Telegram spam eliminated
- Only MID/HIGH quality momentum tokens alerted
- Old bluechip tokens suppressed
- MODE C remains aggressive but quality-aware
