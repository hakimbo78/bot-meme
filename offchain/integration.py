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

# Import Telegram notifier for alerts
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram_notifier import TelegramNotifier


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
        # REPLACED: DexScreener -> GeckoTerminal (better API, time-based queries)
        from .geckoterminal_api import GeckoTerminalAPI
        self.geckoterminal = GeckoTerminalAPI(self.config.get('geckoterminal', {}))
        self.dextools = DexToolsAPI(self.config.get('dextools', {}))\r
        
        self.normalizer = PairNormalizer()
        self.filter = OffChainFilter(self.config.get('filters', {}))
        self.cache = OffChainCache(self.config.get('cache', {}))
        self.deduplicator = Deduplicator(self.config.get('deduplicator', {}))
        self.scheduler = OffChainScheduler(self.config.get('scheduler', {}))
        
        # Output queue for normalized pairs
        self.pair_queue = asyncio.Queue()
        
        # Telegram notifier for alerts
        self.telegram_notifier = TelegramNotifier()
        
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
        print(f"[OFFCHAIN] API: GeckoTerminal (time-based, no keywords)")
        print(f"[OFFCHAIN] Enabled chains: {self.enabled_chains}")
        print(f"[OFFCHAIN] DEXTools: {'ENABLED' if self.dextools_enabled else 'DISABLED'}")
    
    async def start(self):
        """
        Start all off-chain scanner tasks.
        
        Creates background tasks for GeckoTerminal and optionally DEXTools.
        """
        tasks = []
        
        # GeckoTerminal scanner task (MANDATORY - replaced DexScreener)
        geckoterminal_task = asyncio.create_task(
            self.scheduler.schedule_dexscreener(  # Reuse scheduler (rename later)
                self._scan_geckoterminal,
                self.enabled_chains
            ),
            name="offchain-geckoterminal"
        )
        tasks.append(geckoterminal_task)
        
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
    
    async def _scan_geckoterminal(self, chains: List[str]) -> List[Dict]:
        """
        Scan GeckoTerminal for new pools (TIME-BASED, NO KEYWORDS).
        
        This is the MAIN scanning method - gets recently created pools
        sorted by creation time, exactly what the user requested!
        
        Args:
            chains: List of chains to scan
            
        Returns:
            List of normalized pairs that passed filters
        """
        all_passed_pairs = []
        
        print(f"[OFFCHAIN DEBUG] _scan_geckoterminal called with chains: {chains}")
        
        for chain in chains:
            try:
                print(f"[OFFCHAIN DEBUG] Scanning chain: {chain}")
                
                # Fetch NEW pools (time-based, no keywords!)
                new_pools = await self.geckoterminal.fetch_new_pools(chain, limit=20)
                print(f"[OFFCHAIN DEBUG] New pools: {len(new_pools)}")
                
                # Optionally fetch trending pools too
                trending = await self.geckoterminal.fetch_trending_pools(chain, limit=20)
                print(f"[OFFCHAIN DEBUG] Trending pools: {len(trending)}")
                
                # Combine (deduplicate by pair_address)
                all_pairs = new_pools + trending
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
                        print(f"[OFFCHAIN DEBUG] [{idx}/{len(unique_pairs)}] Processing pool: {pair_addr[:10]}...")
                        
                        passed_pair = await self._process_pair(raw_pair, 'geckoterminal', chain)
                        if passed_pair:
                            all_passed_pairs.append(passed_pair)
                            processed += 1
                    except Exception as e:
                        print(f"[OFFCHAIN ERROR] Failed to process pair {idx}: {e}")
                        import traceback
                        traceback.print_exc()
                
                print(f"[OFFCHAIN DEBUG] Processed {processed} pairs that passed filters")
                
            except Exception as e:
                print(f"[OFFCHAIN ERROR] Failed to scan {chain}: {e}")
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
            # Silent drops are bad for debugging activity
            if pair_address and not token_address:
                print(f"[OFFCHAIN] Pair {pair_address[:10]}... dropped (Stable/Quote Pair)")
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
        
        # 3. TOKEN DEDUPLICATION (STRICT 15-MIN COOLDOWN)
        # Check cooldown BEFORE processing further
        if self.deduplicator.is_duplicate(token_address, chain):
             print(f"[OFFCHAIN] {token_address[:8]}... - TOKEN DUPLICATE (15m cooldown)")
             return None
        
        # 4. DETERMINE TIER
        tier = self._determine_tier(score)
        normalized['tier'] = tier
        
        # 5. SEND TELEGRAM ALERT (Tiered - LOW tier suppressed)
        print(f"[OFFCHAIN] ✅ {chain.upper()} | {pair_address[:10]}... | Score: {score:.1f} | Tier: {tier}")
        
        if tier in ['MID', 'HIGH']:
            await self._send_telegram_alert(normalized, chain)
        else:
            # LOW tier - log only, no Telegram
            print(f"[OFFCHAIN] 🔇 LOW TIER - Alert suppressed (logged only)")
        
        # 6. GATEKEEPER (HIGH tier only)
        if verdict == 'VERIFY' and tier == 'HIGH':
             self.cache.set(pair_address, normalized)
             await self.pair_queue.put(normalized)
             self.stats['passed_to_queue'] += 1
             return normalized
             
        return None
    
    def _determine_tier(self, score: float) -> str:
        """Determine alert tier based on score."""
        if score >= 70:
            return 'HIGH'
        elif score >= 50:
            return 'MID'
        else:
            return 'LOW'
    

    
    def _calculate_offchain_score(self, normalized_pair: Dict) -> float:
        """
        Calculate off-chain score (0-100) based on h1 metrics ONLY.
        
        Scoring weights (per config):
        - Liquidity: 30%
        - Volume (h1): 30%
        - Price Change (h1): 25%
        - Transactions (h1): 15%
        
        This score will be combined with on-chain score:
        FINAL_SCORE = (OFFCHAIN_SCORE × 0.6) + (ONCHAIN_SCORE × 0.4)
        
        Args:
            normalized_pair: Normalized pair event
            
        Returns:
            Off-chain score (0-100)
        """
        score = 0.0
        
        # Get scoring weights from config
        scoring_config = self.config.get('scoring', {})
        liq_weight = scoring_config.get('liquidity_weight', 0.30) * 100
        vol_weight = scoring_config.get('volume_1h_weight', 0.30) * 100
        price_weight = scoring_config.get('price_change_1h_weight', 0.25) * 100
        tx_weight = scoring_config.get('tx_1h_weight', 0.15) * 100
        
        # Liquidity score (0-30 points)
        liquidity = normalized_pair.get('liquidity', 0) or 0
        if liquidity >= 100000:
            score += liq_weight
        elif liquidity >= 50000:
            score += liq_weight * 0.7
        elif liquidity >= 20000:
            score += liq_weight * 0.5
        elif liquidity >= 10000:
            score += liq_weight * 0.3
        elif liquidity >= 5000:
            score += liq_weight * 0.2
        
        # Volume (h1) score (0-30 points)
        volume_1h = normalized_pair.get('volume_1h', 0) or 0
        if volume_1h >= 50000:
            score += vol_weight
        elif volume_1h >= 10000:
            score += vol_weight * 0.7
        elif volume_1h >= 5000:
            score += vol_weight * 0.5
        elif volume_1h >= 1000:
            score += vol_weight * 0.3
        elif volume_1h >= 500:
            score += vol_weight * 0.2
        
        # Price change (h1) score (0-25 points)
        price_change_1h = normalized_pair.get('price_change_1h', 0) or 0
        if price_change_1h >= 100:
            score += price_weight
        elif price_change_1h >= 50:
            score += price_weight * 0.7
        elif price_change_1h >= 20:
            score += price_weight * 0.5
        elif price_change_1h >= 10:
            score += price_weight * 0.3
        elif price_change_1h >= 5:
            score += price_weight * 0.2
        
        # Transaction (h1) score (0-15 points)
        tx_1h = normalized_pair.get('tx_1h', 0) or 0
        if tx_1h >= 200:
            score += tx_weight
        elif tx_1h >= 100:
            score += tx_weight * 0.7
        elif tx_1h >= 50:
            score += tx_weight * 0.5
        elif tx_1h >= 20:
            score += tx_weight * 0.3
        elif tx_1h >= 10:
            score += tx_weight * 0.2
        
        # Source confidence boost (up to 10 bonus points)
        confidence = normalized_pair.get('confidence', 0)
        score += confidence * 10
        
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
        print(f"  Level-2 filtered:    {filter_stats['level2_filtered']}")
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
