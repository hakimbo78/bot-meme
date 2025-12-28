"""
QUICK START: Using the New Solana Metadata + LP Detection Modules

This guide shows how to integrate the new modules in your scanning/execution pipeline.
"""

# ============================================================================
# SETUP: Initialize Scanner with New Modules
# ============================================================================

from modules.solana.solana_scanner import SolanaScanner
from config import CHAIN_CONFIGS

# Get Solana config from chains.yaml
solana_config = CHAIN_CONFIGS['chains'].get('solana', {})

# Create scanner (automatically initializes resolver, detector, state machine)
scanner = SolanaScanner(solana_config)
connected = scanner.connect()

if not connected:
    print("Failed to connect to Solana")
    exit(1)

print("✅ Scanner connected with metadata resolver, LP detector, and state machine")
print(f"  - Metadata Cache TTL: {solana_config.get('metadata_cache_ttl', 1800)}s")
print(f"  - Min LP SOL: {solana_config.get('min_lp_sol', 10.0)}")
print(f"  - Sniper Score Threshold: {solana_config.get('sniper_score_threshold', 70)}")
print(f"  - Safe Mode: {solana_config.get('safe_mode', True)}")


# ============================================================================
# USAGE 1: Scan for New Tokens (with state machine)
# ============================================================================

def scan_tokens():
    """Scan for new tokens and create initial state records."""
    tokens = scanner.scan_new_pairs()
    
    for token in tokens:
        print(f"\n🎯 New Token Detected: {token['symbol']}")
        print(f"   Mint: {token['address'][:8]}...")
        print(f"   State: {token.get('state', 'DETECTED')}")
        print(f"   Age: {token.get('age_seconds', 0):.1f}s")
        print(f"   SOL Inflow: {token.get('sol_inflow', 0):.2f}")
    
    return tokens


# ============================================================================
# USAGE 2: Resolve Metadata for a Token (ASYNC)
# ============================================================================

import asyncio

async def resolve_metadata_async(token_mint):
    """Resolve token metadata from Metaplex."""
    print(f"\n📊 Resolving metadata for {token_mint[:8]}...")
    
    metadata = await scanner.resolve_token_metadata(token_mint)
    
    if metadata:
        print(f"   ✅ Name: {metadata.get('name')}")
        print(f"   ✅ Symbol: {metadata.get('symbol')}")
        print(f"   ✅ Decimals: {metadata.get('decimals')}")
        print(f"   ✅ Supply: {metadata.get('supply'):,}")
        return metadata
    else:
        print(f"   ❌ Metadata resolution failed")
        return None


# ============================================================================
# USAGE 3: Detect Raydium LP (ASYNC)
# ============================================================================

async def detect_lp_async(token_mint, txid=None):
    """Detect Raydium LP for a token."""
    print(f"\n💧 Detecting Raydium LP for {token_mint[:8]}...")
    
    lp_info = await scanner.detect_token_lp(token_mint, txid=txid)
    
    if lp_info:
        print(f"   ✅ Pool: {lp_info.get('pool_address', 'unknown')[:8]}...")
        print(f"   ✅ Quote Liquidity: {lp_info.get('quote_liquidity', 0):.2f} SOL")
        print(f"   ✅ USD Value: ${lp_info.get('quote_liquidity_usd', 0):.2f}")
        return lp_info
    else:
        print(f"   ❌ LP not found or liquidity too low")
        return None


# ============================================================================
# USAGE 4: Update Score and Check Readiness
# ============================================================================

def update_score(token_mint, score):
    """Update token score and check if armed for sniper."""
    print(f"\n📈 Updating score for {token_mint[:8]}: {score:.1f}")
    
    state = scanner.update_token_score(token_mint, score)
    
    if state:
        print(f"   State: {state.get('state')}")
        print(f"   Metadata OK: {state.get('metadata_resolved')}")
        print(f"   LP Valid: {state.get('lp_valid')}")
        
        # Check if ready for execution
        can_execute, reason = scanner.can_execute_sniper(token_mint)
        if can_execute:
            print(f"   ✅ READY FOR SNIPER EXECUTION!")
        else:
            print(f"   ❌ {reason}")
        
        return state
    
    return None


# ============================================================================
# USAGE 5: Complete Async Pipeline
# ============================================================================

async def complete_pipeline(token_mint):
    """
    Complete pipeline:
    1. Resolve metadata
    2. Detect LP
    3. Calculate score
    4. Update state
    5. Check execution readiness
    """
    print(f"\n{'='*60}")
    print(f"COMPLETE PIPELINE FOR {token_mint[:8]}...")
    print(f"{'='*60}")
    
    # Step 1: Resolve metadata
    metadata = await resolve_metadata_async(token_mint)
    if not metadata:
        print("❌ Failed to resolve metadata, skipping token")
        return False
    
    # Step 2: Detect LP
    lp_info = await detect_lp_async(token_mint)
    if not lp_info:
        print("❌ LP not detected or too low, skipping token")
        return False
    
    # Step 3: Calculate score (from other signals)
    # This would come from your scoring engine
    score = 75.5  # Example score
    
    # Step 4: Update score
    state = update_score(token_mint, score)
    
    # Step 5: Check execution readiness
    if state and state['state'] == 'SNIPER_ARMED':
        print("\n✅ TOKEN IS READY FOR SNIPER EXECUTION")
        return True
    else:
        print("\n❌ Token not ready for execution")
        return False


# ============================================================================
# USAGE 6: Get Execution-Ready Tokens
# ============================================================================

def get_armed_tokens():
    """Get all tokens ready for sniper execution."""
    print("\n🔫 Armed Tokens (ready for execution):")
    
    armed = scanner.get_armed_tokens()
    
    if not armed:
        print("   (none)")
        return []
    
    for token in armed:
        print(f"   - {token.get('symbol')} | {token.get('mint')[:8]}...")
        print(f"     Score: {token.get('score'):.1f}")
        print(f"     LP SOL: {token.get('lp_info', {}).get('quote_liquidity_sol', 0):.2f}")
    
    return armed


# ============================================================================
# USAGE 7: Monitor and Execute
# ============================================================================

async def monitor_and_execute(token_mint, scoring_engine):
    """
    Continuous monitoring until sniper-armed or timeout.
    
    Args:
        token_mint: Token to monitor
        scoring_engine: Function that returns score for token
    """
    print(f"\n⏱️  Monitoring {token_mint[:8]}... (timeout: 2 minutes)")
    
    start_time = asyncio.get_event_loop().time()
    max_wait = 120  # 2 minutes
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Get current state
        state_record = scanner.state_machine.get_token(token_mint)
        if not state_record:
            print("❌ Token not found")
            return False
        
        print(f"\n  [{elapsed:.0f}s] State: {state_record.current_state.value}")
        
        # Check each stage
        if not state_record.metadata_resolved:
            metadata = await resolve_metadata_async(token_mint)
            if metadata:
                print("  ✅ Metadata resolved")
            else:
                print("  ❌ Metadata resolution failed")
                return False
        
        if not state_record.lp_detected:
            lp = await detect_lp_async(token_mint)
            if lp:
                print("  ✅ LP detected")
            else:
                print("  ⏳ LP not found yet (will retry)")
        
        # Check score
        if state_record.metadata_resolved and state_record.lp_detected:
            score = scoring_engine(token_mint)
            update_score(token_mint, score)
            
            # Check if armed
            can_exec, reason = scanner.can_execute_sniper(token_mint)
            if can_exec:
                print(f"  ✅ SNIPER ARMED! Ready to execute.")
                return True
        
        # Check timeout
        if elapsed > max_wait:
            print(f"  ⏱️  Timeout ({max_wait}s), stopping monitor")
            return False
        
        # Wait before next check
        await asyncio.sleep(5)


# ============================================================================
# USAGE 8: Get Statistics
# ============================================================================

def print_stats():
    """Print scanner and state machine statistics."""
    stats = scanner.get_stats()
    
    print("\n📊 SCANNER STATISTICS:")
    print(f"  Connected: {stats.get('connected')}")
    print(f"  Cached Tokens: {stats.get('cached_tokens')}")
    
    if 'metadata_resolver' in stats:
        meta_stats = stats['metadata_resolver']
        print(f"\n  Metadata Resolver:")
        print(f"    - Cached: {meta_stats.get('cached_tokens')}")
        print(f"    - TTL: {meta_stats.get('cache_ttl_seconds')}s")
    
    if 'lp_detector' in stats:
        lp_stats = stats['lp_detector']
        print(f"\n  LP Detector:")
        print(f"    - Detected Pools: {lp_stats.get('detected_pools')}")
        print(f"    - Tokens with LP: {lp_stats.get('tokens_with_lp')}")
    
    if 'state_machine' in stats:
        sm_stats = stats['state_machine']
        print(f"\n  State Machine:")
        print(f"    - Total Tokens: {sm_stats.get('total_tokens')}")
        print(f"    - Armed: {sm_stats.get('armed_tokens')}")
        by_state = sm_stats.get('by_state', {})
        for state, count in by_state.items():
            print(f"    - {state}: {count}")


# ============================================================================
# FULL EXAMPLE: Main Loop
# ============================================================================

async def main():
    """Example main loop."""
    
    # Initialize scanner
    scanner.connect()
    print_stats()
    
    # Example token to monitor
    example_mint = "TokenMintAddressHere"
    
    # Example scoring function (replace with your actual scorer)
    def score_token(mint):
        return 75.0  # Simplified
    
    # Run complete pipeline
    try:
        success = await complete_pipeline(example_mint)
        if success:
            print("\n✅ Token passed all validations!")
            armed = get_armed_tokens()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())


# ============================================================================
# KEY LOGGING OUTPUT (What You'll See)
# ============================================================================

"""
✅ Scanner connected with metadata resolver, LP detector, and state machine
  - Metadata Cache TTL: 1800s
  - Min LP SOL: 10.0
  - Sniper Score Threshold: 70
  - Safe Mode: True

🎯 New Token Detected: DGAI
   Mint: TokenMi...
   State: DETECTED
   Age: 2.5s
   SOL Inflow: 15.25

📊 Resolving metadata for TokenMi...
[SOLANA][META] Resolved token DOGEAI (DGAI) decimals=9 supply=1B
   ✅ Name: DOGEAI
   ✅ Symbol: DGAI
   ✅ Decimals: 9
   ✅ Supply: 1,000,000,000

💧 Detecting Raydium LP for TokenMi...
[SOLANA][LP] Raydium LP detected | SOL=18.7 | LP=OK
   ✅ Pool: PoolAddr...
   ✅ Quote Liquidity: 18.70 SOL
   ✅ USD Value: $3740.00

📈 Updating score for TokenMi: 75.5
   State: SNIPER_ARMED
   Metadata OK: True
   LP Valid: True
   ✅ READY FOR SNIPER EXECUTION!

✅ TOKEN IS READY FOR SNIPER EXECUTION
"""
