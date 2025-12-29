"""
OFF-CHAIN SCREENER INTEGRATION

Main integration module that orchestrates all off-chain components.
Provides a clean interface for the existing scanner pipeline.

ARCHITECTURE:
  DEXTools / DexScreener
          ↓
  OFF-CHAIN SCREENER (This Module)
          ↓
  NORMALIZED PAIR EVENT
          ↓
  EXISTING SCORE ENGINE
          ↓
  ON-CHAIN VERIFY (ON DEMAND ONLY)
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .base_screener import BaseScreener
from .dex_screener import DexScreenerAPI
from .dextools_screener import DexToolsAPI
from .normalizer import PairNormalizer
from .filters import OffChainFilter
from .cache import OffChainCache
from .deduplicator import Deduplicator
from .scheduler import OffChainScheduler


class OffChainScreenerIntegration:
    """
    Main off-chain screener integration class.
    
    Coordinates all off-chain components to filter ~95% noise before on-chain verification.
    
    Usage:
        screener = OffChainScreenerIntegration(config)
        async for normalized_pair in screener.stream_pairs():
            # Pass to existing score engine
            score = existing_scorer.score_token(normalized_pair)
            if score >= threshold:
                # Trigger on-chain verification
                on_chain_data = await verify_on_chain(normalized_pair)
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize off-chain screener integration.
        
        Args:
            config: Full configuration dict
        """
        self.config = config or {}
        
        # Initialize components
        self.dexscreener = DexScreenerAPI(self.config.get('dexscreener', {}))
        self.dextools = DexToolsAPI(self.config.get('dextools', {}))
        
        self.normalizer = PairNormalizer()
        self.filter = OffChainFilter(self.config.get('filters', {}))
        self.cache = OffChainCache(self.config.get('cache', {}))
        self.deduplicator = Deduplicator(self.config.get('deduplicator', {}))
        self.scheduler = OffChainScheduler(self.config.get('scheduler', {}))
        
        # Output queue for normalized pairs
        self.pair_queue = asyncio.Queue()
        
        # Enabled chains
        self.enabled_chains = self.config.get('enabled_chains', ['base'])
        
        # Feature flags
        self.dextools_enabled = self.config.get('dextools_enabled', False)
        
        # Stats
        self.stats = {
            'total_raw_pairs': 0,
            'normalized_pairs': 0,
            'filtered_out': 0,
            'deduplicated': 0,
            'passed_to_queue': 0,
        }
        
        print("[OFFCHAIN] OffChainScreenerIntegration initialized")
        print(f"[OFFCHAIN] Enabled chains: {self.enabled_chains}")
        print(f"[OFFCHAIN] DEXTools: {'ENABLED' if self.dextools_enabled else 'DISABLED'}")
    
    async def start(self):
        """
        Start all off-chain scanner tasks.
        
        Creates background tasks for DexScreener and optionally DEXTools.
        """
        tasks = []
        
        # DexScreener scanner task (MANDATORY)
        dexscreener_task = asyncio.create_task(
            self.scheduler.schedule_dexscreener(
                self._scan_dexscreener,
                self.enabled_chains
            ),
            name="offchain-dexscreener"
        )
        tasks.append(dexscreener_task)
        
        # DEXTools scanner task (OPTIONAL)
        if self.dextools_enabled and self.dextools.enabled:
            dextools_task = asyncio.create_task(
                self.scheduler.schedule_dextools(
                    self._scan_dextools,
                    self.enabled_chains
                ),
                name="offchain-dextools"
            )
            tasks.append(dextools_task)
        
        # Cleanup task (periodic cache/dedup cleanup)
        cleanup_task = asyncio.create_task(
            self._periodic_cleanup(),
            name="offchain-cleanup"
        )
        tasks.append(cleanup_task)
        
        print(f"[OFFCHAIN] Started {len(tasks)} background tasks")
        
        return tasks
    
    async def _scan_dexscreener(self, chains: List[str]) -> List[Dict]:
        """
        Scan DexScreener for new/trending pairs.
        
        Args:
            chains: List of chains to scan
            
        Returns:
            List of normalized pairs that passed filters
        """
        all_passed_pairs = []
        
        print(f"[OFFCHAIN DEBUG] _scan_dexscreener called with chains: {chains}")
        
        for chain in chains:
            try:
                print(f"[OFFCHAIN DEBUG] Scanning chain: {chain}")
                
                # Fetch trending pairs and new pairs
                trending = await self.dexscreener.fetch_trending_pairs(chain, limit=50)
                print(f"[OFFCHAIN DEBUG] Trending pairs: {len(trending)}")
                
                new_pairs = await self.dexscreener.fetch_new_pairs(chain, max_age_minutes=60)
                print(f"[OFFCHAIN DEBUG] New pairs: {len(new_pairs)}")
                
                # Combine (deduplicate by pair_address)
                all_pairs = trending + new_pairs
                print(f"[OFFCHAIN DEBUG] Combined (before dedup): {len(all_pairs)}")
                
                seen_addresses = set()
                unique_pairs = []
                
                for pair in all_pairs:
                    addr = pair.get('pairAddress', '')
                    if addr and addr not in seen_addresses:
                        seen_addresses.add(addr)
                        unique_pairs.append(pair)
                
                print(f"[OFFCHAIN DEBUG] Unique pairs: {len(unique_pairs)}")
                
                self.stats['total_raw_pairs'] += len(unique_pairs)
                
                # Process each pair
                processed = 0
                for idx, raw_pair in enumerate(unique_pairs, 1):
                    try:
                        pair_addr = raw_pair.get('pairAddress', 'UNKNOWN')
                        print(f"[OFFCHAIN DEBUG] [{idx}/{len(unique_pairs)}] Processing raw pair: {pair_addr[:10]}...")
                        
                        passed_pair = await self._process_pair(raw_pair, 'dexscreener', chain)
                        if passed_pair:
                            all_passed_pairs.append(passed_pair)
                            processed += 1
                    except Exception as e:
                        print(f"[OFFCHAIN ERROR] Failed to process pair {idx}: {e}")
                        import traceback
                        traceback.print_exc()
                
                print(f"[OFFCHAIN DEBUG] Processed {processed} pairs that passed filters")
                
            except Exception as e:
                print(f"[OFFCHAIN] DexScreener scan error for {chain}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"[OFFCHAIN DEBUG] Total passed pairs across all chains: {len(all_passed_pairs)}")
        return all_passed_pairs
    
    async def _scan_dextools(self, chains: List[str]) -> List[Dict]:
        """
        Scan DEXTools for top gainers.
        
        Args:
            chains: List of chains to scan
            
        Returns:
            List of normalized pairs that passed filters
        """
        all_passed_pairs = []
        
        for chain in chains:
            try:
                # Fetch top gainers
                top_gainers = await self.dextools.fetch_top_gainers(chain, limit=50)
                
                self.stats['total_raw_pairs'] += len(top_gainers)
                
                # Process each pair
                for raw_pair in top_gainers:
                    passed_pair = await self._process_pair(raw_pair, 'dextools', chain)
                    if passed_pair:
                        all_passed_pairs.append(passed_pair)
                
            except Exception as e:
                print(f"[OFFCHAIN] DEXTools scan error for {chain}: {e}")
        
        return all_passed_pairs
    
    async def _process_pair(self, raw_pair: Dict, source: str, chain: str) -> Optional[Dict]:
        """
        Process a single raw pair through the pipeline.
        
        Pipeline:
        1. Normalize
        2. Check deduplication
        3. Apply filters
        4. Cache
        5. Enqueue for downstream processing
        
        Args:
            raw_pair: Raw pair data from API
            source: Data source ('dexscreener' or 'dextools')
            chain: Chain identifier
            
        Returns:
            Normalized pair if passed all checks, None otherwise
        """
        # 1. NORMALIZE
        if source == 'dexscreener':
            normalized = self.normalizer.normalize_dexscreener(raw_pair, source)
        elif source == 'dextools':
            normalized = self.normalizer.normalize_dextools(raw_pair, source)
        else:
            return None
        
        self.stats['normalized_pairs'] += 1
        
        pair_address = normalized.get('pair_address', '')
        if not pair_address:
            return None
        
        # 2. DEDUPLICATION
        if self.deduplicator.is_duplicate(pair_address, chain):
            self.stats['deduplicated'] += 1
            print(f"[OFFCHAIN DEBUG] {pair_address[:10]}... - DUPLICATE (cooldown active)")
            return None
        
        # 3. FILTERING
        # DEBUG: Log pair data before filter (show ALL volume values)
        vol_5m = normalized.get('volume_5m', 0) or 0
        vol_1h = normalized.get('volume_1h', 0) or 0
        vol_24h = normalized.get('volume_24h', 0) or 0
        print(f"[OFFCHAIN DEBUG] Processing pair {pair_address[:10]}... | Liq: ${normalized.get('liquidity', 0):,.0f} | Vol5m: ${vol_5m:,.0f} | Vol1h: ${vol_1h:,.0f} | Vol24h: ${vol_24h:,.0f}")
        
        passed, reason = self.filter.apply_filters(normalized)
        if not passed:
            self.stats['filtered_out'] += 1
            print(f"[OFFCHAIN FILTER] {pair_address[:10]}... - {reason}")  # Enable logging
            return None
        
        # 4. CACHE (for future lookups)
        self.cache.set(pair_address, normalized)
        
        # 5. CALCULATE OFF-CHAIN SCORE
        offchain_score = self._calculate_offchain_score(normalized)
        normalized['offchain_score'] = offchain_score
        
        # 6. ENQUEUE
        await self.pair_queue.put(normalized)
        self.stats['passed_to_queue'] += 1
        
        print(f"[OFFCHAIN] ✅ {source.upper()} | {chain.upper()} | {pair_address[:10]}... | Score: {offchain_score:.1f} | {normalized.get('event_type')}")
        
        return normalized
    
    def _calculate_offchain_score(self, normalized_pair: Dict) -> float:
        """
        Calculate off-chain score (0-100) based on normalized data.
        
        This score will be combined with on-chain score:
        FINAL_SCORE = (OFFCHAIN_SCORE × 0.6) + (ONCHAIN_SCORE × 0.4)
        
        Args:
            normalized_pair: Normalized pair event
            
        Returns:
            Off-chain score (0-100)
        """
        score = 0.0
        
        # Price momentum (max 40 points)
        price_change_5m = normalized_pair.get('price_change_5m', 0) or 0
        price_change_1h = normalized_pair.get('price_change_1h', 0) or 0
        
        if price_change_5m >= 100:
            score += 20
        elif price_change_5m >= 50:
            score += 15
        elif price_change_5m >= 20:
            score += 10
        
        if price_change_1h >= 300:
            score += 20
        elif price_change_1h >= 150:
            score += 15
        elif price_change_1h >= 50:
            score += 10
        
        # Volume spike (max 30 points)
        volume_5m = normalized_pair.get('volume_5m', 0) or 0
        volume_24h = normalized_pair.get('volume_24h', 0) or 0
        
        if volume_5m >= 100000:
            score += 15
        elif volume_5m >= 50000:
            score += 10
        elif volume_5m >= 10000:
            score += 5
        
        if volume_24h >= 1000000:
            score += 15
        elif volume_24h >= 500000:
            score += 10
        elif volume_24h >= 100000:
            score += 5
        
        # Transaction acceleration (max 20 points)
        tx_5m = normalized_pair.get('tx_5m', 0) or 0
        
        if tx_5m >= 100:
            score += 20
        elif tx_5m >= 50:
            score += 15
        elif tx_5m >= 20:
            score += 10
        elif tx_5m >= 10:
            score += 5
        
        # Liquidity (max 10 points)
        liquidity = normalized_pair.get('liquidity', 0) or 0
        
        if liquidity >= 100000:
            score += 10
        elif liquidity >= 50000:
            score += 7
        elif liquidity >= 20000:
            score += 5
        elif liquidity >= 10000:
            score += 3
        
        # Source confidence boost
        confidence = normalized_pair.get('confidence', 0)
        score += confidence * 10  # Up to 10 bonus points
        
        # DEXTools top rank boost
        if normalized_pair.get('source') == 'dextools':
            rank = normalized_pair.get('dextools_rank', 9999)
            if rank <= 10:
                score += 20
            elif rank <= 30:
                score += 15
            elif rank <= 50:
                score += 10
        
        return min(100.0, score)
    
    async def stream_pairs(self):
        """
        Async generator that yields normalized pairs.
        
        Usage:
            async for pair in screener.stream_pairs():
                process(pair)
        
        Yields:
            Normalized pair dicts
        """
        while True:
            pair = await self.pair_queue.get()
            yield pair
    
    async def get_next_pair(self) -> Dict:
        """
        Get next pair from queue (blocking).
        
        Returns:
            Normalized pair dict
        """
        return await self.pair_queue.get()
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of cache and deduplicator."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                cache_removed = self.cache.cleanup_expired()
                dedup_removed = self.deduplicator.cleanup_expired()
                
                if cache_removed > 0 or dedup_removed > 0:
                    print(f"[OFFCHAIN] Cleanup: {cache_removed} cache, {dedup_removed} dedup entries removed")
                
            except Exception as e:
                print(f"[OFFCHAIN] Cleanup error: {e}")
                await asyncio.sleep(60)
    
    async def close(self):
        """Close all resources."""
        await self.dexscreener.close()
        await self.dextools.close()
        print("[OFFCHAIN] Resources closed")
    
    def get_stats(self) -> Dict:
        """
        Get comprehensive statistics.
        
        Returns:
            Dict with all component stats
        """
        return {
            'pipeline': self.stats.copy(),
            'filter': self.filter.get_stats(),
            'cache': self.cache.get_stats(),
            'deduplicator': self.deduplicator.get_stats(),
            'scheduler': self.scheduler.get_stats(),
            'dexscreener': self.dexscreener.get_stats(),
            'dextools': self.dextools.get_stats() if self.dextools_enabled else {},
        }
    
    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("OFF-CHAIN SCREENER STATISTICS")
        print("="*60)
        
        pipeline = stats['pipeline']
        print(f"\n📊 PIPELINE:")
        print(f"  Total raw pairs:     {pipeline['total_raw_pairs']}")
        print(f"  Normalized:          {pipeline['normalized_pairs']}")
        print(f"  Filtered out:        {pipeline['filtered_out']}")
        print(f"  Deduplicated:        {pipeline['deduplicated']}")
        print(f"  Passed to queue:     {pipeline['passed_to_queue']}")
        
        if pipeline['total_raw_pairs'] > 0:
            noise_reduction = (1 - pipeline['passed_to_queue'] / pipeline['total_raw_pairs']) * 100
            print(f"  Noise reduction:     {noise_reduction:.1f}%")
        
        filter_stats = stats['filter']
        print(f"\n🔍 FILTER:")
        print(f"  Filter rate:         {filter_stats['filter_rate_pct']:.1f}%")
        print(f"  Level-0 filtered:    {filter_stats['level0_filtered']}")
        print(f"  Level-1 filtered:    {filter_stats['level1_filtered']}")
        print(f"  DEXTools forced:     {filter_stats['dextools_forced']}")
        
        cache_stats = stats['cache']
        print(f"\n💾 CACHE:")
        print(f"  Size:                {cache_stats['size']} / {cache_stats['max_size']}")
        print(f"  Hit rate:            {cache_stats['hit_rate_pct']:.1f}%")
        print(f"  Evictions:           {cache_stats['evictions']}")
        
        dedup_stats = stats['deduplicator']
        print(f"\n🔄 DEDUPLICATOR:")
        print(f"  Dedup rate:          {dedup_stats['dedup_rate_pct']:.1f}%")
        print(f"  Currently tracked:   {dedup_stats['currently_tracked']}")
        
        scheduler_stats = stats['scheduler']
        print(f"\n⏰ SCHEDULER:")
        print(f"  Scans performed:     DexScreener={scheduler_stats['scans_performed']['dexscreener']}, DEXTools={scheduler_stats['scans_performed']['dextools']}")
        print(f"  Pairs found:         DexScreener={scheduler_stats['pairs_found']['dexscreener']}, DEXTools={scheduler_stats['pairs_found']['dextools']}")
        
        print("="*60 + "\n")
