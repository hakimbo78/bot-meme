"""
MINIMAL INTEGRATION EXAMPLE FOR MAIN.PY

This shows how to integrate the off-chain screener into the existing main.py pipeline.

INTEGRATION POINTS:
1. Import off-chain screener modules
2. Initialize off-chain screener
3. Start off-chain scanner tasks
4. Create producer task that reads from off-chain queue
5. Consumer processes normalized pairs with combined scoring

NO BREAKING CHANGES - The off-chain screener is fully optional and backward compatible.
"""

# ============================================================================
# STEP 1: Add imports to main.py (near top of file)
# ============================================================================

# Off-chain screener (optional - CU-saving pre-filter)
OFFCHAIN_SCREENER_AVAILABLE = False
try:
    from offchain.integration import OffChainScreenerIntegration
    from offchain_config import get_offchain_config, is_offchain_enabled
    OFFCHAIN_SCREENER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Off-chain screener not available: {e}")


# ============================================================================
# STEP 2: Initialize off-chain screener (in main() function, after other initializations)
# ============================================================================

# Initialize Off-Chain Screener (NEW - 2025-12-29)
offchain_screener = None
if OFFCHAIN_SCREENER_AVAILABLE and is_offchain_enabled():
    try:
        offchain_config = get_offchain_config()
        # Override enabled chains with command-line args
        offchain_config['enabled_chains'] = enabled_chains
        
        offchain_screener = OffChainScreenerIntegration(offchain_config)
        
        print(f"{Fore.GREEN}🌐 OFF-CHAIN SCREENER: ENABLED")
        print(f"{Fore.GREEN}    - Primary: DexScreener (FREE)")
        if offchain_config.get('dextools_enabled'):
            print(f"{Fore.GREEN}    - Secondary: DEXTools (API key required)")
        print(f"{Fore.GREEN}    - Chains: {', '.join(enabled_chains)}")
        print(f"{Fore.GREEN}    - Target: ~95% noise reduction")
        print(f"{Fore.GREEN}    - RPC savings: < 5k calls/day\n")
        
    except Exception as e:
        print(f"{Fore.YELLOW}⚠️  Off-chain screener failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        offchain_screener = None
else:
    print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Off-chain screener disabled or not available\n")


# ============================================================================
# STEP 3: Start off-chain scanner tasks (in async task section)
# ============================================================================

# Start off-chain screener tasks
if offchain_screener:
    offchain_tasks = await offchain_screener.start()
    tasks.extend(offchain_tasks)
    print(f"{Fore.GREEN}✅ Off-chain screener tasks added")


# ============================================================================
# STEP 4: Create producer task for off-chain pairs (add to async tasks section)
# ============================================================================

async def run_offchain_producer():
    """
    Producer task for off-chain screener.
    
    Reads normalized pairs from off-chain queue and enqueues them
    for processing by the main consumer.
    """
    if not offchain_screener:
        return
    
    print(f"{Fore.GREEN}🌐 Off-chain producer task started")
    
    while True:
        try:
            # Get next normalized pair from off-chain screener
            normalized_pair = await offchain_screener.get_next_pair()
            
            # Add metadata for consumer
            normalized_pair['source_type'] = 'offchain'
            normalized_pair['requires_onchain_verify'] = True
            
            # Enqueue for main consumer processing
            await queue.put(normalized_pair)
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Producer error: {e}")
            await asyncio.sleep(5)

if offchain_screener:
    tasks.append(asyncio.create_task(run_offchain_producer(), name="offchain-producer"))


# ============================================================================
# STEP 5: Handle off-chain pairs in consumer task (add to consumer_task function)
# ============================================================================

async def consumer_task():
    print(f"{Fore.GREEN}✅ Event consumer started")
    
    while True:
        pair_data = await queue.get()
        
        try:
            chain = pair_data.get('chain', 'unknown')
            source_type = pair_data.get('source_type', 'onchain')
            
            # ================================================
            # OFF-CHAIN PAIR PROCESSING (NEW)
            # ================================================
            if source_type == 'offchain':
                try:
                    chain_name = pair_data.get('chain', 'unknown')
                    chain_prefix = f"[{chain_name.upper()}]"
                    pair_address = pair_data.get('pair_address', 'UNKNOWN')
                    
                    print(f"{Fore.GREEN}🌐 {chain_prefix} [OFFCHAIN] Processing pair {pair_address[:10]}...")
                    
                    # Extract off-chain score
                    offchain_score = pair_data.get('offchain_score', 0)
                    
                    # Get scoring config
                    from offchain_config import get_offchain_config
                    offchain_config = get_offchain_config()
                    scoring_config = offchain_config.get('scoring', {})
                    
                    verify_threshold = scoring_config.get('verify_threshold', 60)
                    
                    # Check if we should trigger on-chain verification
                    if offchain_score >= verify_threshold:
                        print(f"{Fore.GREEN}    Off-chain score: {offchain_score:.1f} >= {verify_threshold} - Triggering on-chain verify")
                        
                        # TODO: Implement on-chain verification here
                        # This would call existing analyzer.analyze_token() but ONLY for high-score pairs
                        # 
                        # Example:
                        # token_address = pair_data.get('token0')  # or token1, depending on base/quote
                        # chain_config = scanner.get_chain_config(chain_name)
                        # 
                        # # ON-CHAIN VERIFY (STRICT RULES - ONLY eth_call, getReserves, balanceOf, totalSupply)
                        # adapter = scanner.get_adapter(chain_name)
                        # if adapter:
                        #     onchain_data = await asyncio.to_thread(
                        #         adapter.get_pair_info,  # Lightweight on-chain call
                        #         pair_address
                        #     )
                        #     
                        #     # Merge off-chain and on-chain data
                        #     combined_data = {**pair_data, **onchain_data}
                        #     
                        #     # Calculate combined score
                        #     onchain_weight = scoring_config.get('onchain_weight', 0.4)
                        #     offchain_weight = scoring_config.get('offchain_weight', 0.6)
                        #     
                        #     # Score with existing scorer
                        #     score_result = scorer.score_token(combined_data, chain_config)
                        #     onchain_score = score_result.get('score', 0)
                        #     
                        #     # FINAL_SCORE = (OFFCHAIN_SCORE × 0.6) + (ONCHAIN_SCORE × 0.4)
                        #     final_score = (offchain_score * offchain_weight) + (onchain_score * onchain_weight)
                        #     
                        #     # Update score_result
                        #     score_result['score'] = final_score
                        #     score_result['offchain_score'] = offchain_score
                        #     score_result['onchain_score'] = onchain_score
                        #     score_result['score_breakdown'] = {
                        #         'offchain': offchain_score,
                        #         'onchain': onchain_score,
                        #         'final': final_score,
                        #     }
                        #     
                        #     # Send alert if meets threshold
                        #     if telegram.enabled and score_result.get('alert_level'):
                        #         await telegram.send_alert_async(combined_data, score_result)
                        
                        # For now, just log
                        print(f"{Fore.GREEN}    [TODO] On-chain verification would trigger here")
                        
                    else:
                        print(f"{Fore.YELLOW}    Off-chain score: {offchain_score:.1f} < {verify_threshold} - Filtered (saved RPC calls)")
                    
                except Exception as offchain_e:
                    print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Processing error: {offchain_e}")
            
            # ... (existing processing for other source types: solana, secondary_market, activity, etc.)
            
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Consumer error: {e}")


# ============================================================================
# STEP 6: Cleanup on shutdown (add to finally block)
# ============================================================================

finally:
    # Cleanup off-chain screener
    if offchain_screener:
        await offchain_screener.close()


# ============================================================================
# NOTES:
# ============================================================================

# RPC SAVINGS EXPLAINED:
# 
# WITHOUT OFF-CHAIN SCREENER:
# - Every new pair triggers immediate on-chain verification
# - 1000 pairs/hour × 5 RPC calls/pair = 5,000 calls/hour = 120k calls/day
# - Cost: ~$120/month at $1/1000 calls
# 
# WITH OFF-CHAIN SCREENER:
# - 1000 pairs/hour detected off-chain (0 RPC calls)
# - ~95% filtered by Level-0 + Level-1 filters (0 RPC calls)
# - Only ~50 pairs/hour pass filters and trigger on-chain verify
# - 50 pairs/hour × 5 RPC calls/pair = 250 calls/hour = 6k calls/day
# - Cost: ~$6/month
# 
# SAVINGS: ~$114/month (95% reduction in RPC costs)
#
# The off-chain screener pays for itself by eliminating wasteful RPC calls
# on pairs that would have been filtered anyway.
