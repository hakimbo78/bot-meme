"""
OFF-CHAIN SCHEDULER

CU-saving scheduler that coordinates scanning intervals:
- DexScreener: every 30-60s
- DEXTools: every 90-180s
- No idle polling - event-driven when possible

Target: < 5k RPC calls/day ($5/month budget)
"""

import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime
import random


class OffChainScheduler:
    """
    Intelligent scheduler for off-chain screeners.
    
    Manages scan intervals to minimize API calls while maximizing signal detection.
    
    Features:
    - Adaptive intervals based on market activity
    - Jitter to avoid thundering herd
    - Emergency backoff on rate limits
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize scheduler.
        
        Args:
            config: Scheduler configuration dict
        """
        self.config = config or {}
        
        # Scan intervals (seconds)
        self.dexscreener_interval_min = self.config.get('dexscreener_interval_min', 30)
        self.dexscreener_interval_max = self.config.get('dexscreener_interval_max', 60)
        
        self.dextools_interval_min = self.config.get('dextools_interval_min', 90)
        self.dextools_interval_max = self.config.get('dextools_interval_max', 180)
        
        # Adaptive scaling
        self.adaptive_scaling = self.config.get('adaptive_scaling', True)
        self.activity_threshold = self.config.get('activity_threshold', 5)  # Pairs/scan to consider "active"
        
        # Emergency backoff
        self.backoff_multiplier = 2.0
        self.backoff_active = False
        self.backoff_until = None
        
        # Stats
        self.scans_performed = {
            'dexscreener': 0,
            'dextools': 0,
        }
        self.last_scan_time = {
            'dexscreener': None,
            'dextools': None,
        }
        self.pairs_found = {
            'dexscreener': 0,
            'dextools': 0,
        }
    
    async def schedule_dexscreener(self, scan_callback: Callable, chains: List[str] = None):
        """
        Schedule periodic DexScreener scans.
        
        Args:
            scan_callback: Async function to call for scanning
            chains: List of chains to scan
        """
        chains = chains or ['base']
        
        print(f"[SCHEDULER] DexScreener task started (chains: {chains})")
        
        while True:
            try:
                # Calculate interval with jitter
                interval = self._calculate_interval('dexscreener')
                
                # Check for backoff
                if self.backoff_active and self.backoff_until:
                    now = datetime.now()
                    if now < self.backoff_until:
                        wait_time = (self.backoff_until - now).total_seconds()
                        print(f"[SCHEDULER] DexScreener in backoff, waiting {wait_time:.0f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        self.backoff_active = False
                        self.backoff_until = None
                
                # Perform scan
                scan_start = datetime.now()
                pairs_found = await scan_callback(chains)
                
                # Update stats
                self.scans_performed['dexscreener'] += 1
                self.last_scan_time['dexscreener'] = scan_start
                self.pairs_found['dexscreener'] += len(pairs_found) if pairs_found else 0
                
                # Log
                print(f"[SCHEDULER] DexScreener scan complete: {len(pairs_found) if pairs_found else 0} pairs, next in {interval}s")
                
                # Adaptive interval adjustment
                if self.adaptive_scaling and pairs_found:
                    if len(pairs_found) >= self.activity_threshold:
                        # High activity - scan more frequently
                        interval = max(self.dexscreener_interval_min, interval * 0.8)
                    else:
                        # Low activity - scan less frequently
                        interval = min(self.dexscreener_interval_max, interval * 1.2)
                
                # Wait for next scan
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"[SCHEDULER] DexScreener error: {e}")
                await asyncio.sleep(60)  # Error backoff
    
    async def schedule_dextools(self, scan_callback: Callable, chains: List[str] = None):
        """
        Schedule periodic DEXTools scans.
        
        Args:
            scan_callback: Async function to call for scanning
            chains: List of chains to scan
        """
        chains = chains or ['base']
        
        print(f"[SCHEDULER] DEXTools task started (chains: {chains})")
        
        while True:
            try:
                # Calculate interval with jitter
                interval = self._calculate_interval('dextools')
                
                # Check for backoff
                if self.backoff_active and self.backoff_until:
                    now = datetime.now()
                    if now < self.backoff_until:
                        wait_time = (self.backoff_until - now).total_seconds()
                        print(f"[SCHEDULER] DEXTools in backoff, waiting {wait_time:.0f}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        self.backoff_active = False
                        self.backoff_until = None
                
                # Perform scan
                scan_start = datetime.now()
                pairs_found = await scan_callback(chains)
                
                # Update stats
                self.scans_performed['dextools'] += 1
                self.last_scan_time['dextools'] = scan_start
                self.pairs_found['dextools'] += len(pairs_found) if pairs_found else 0
                
                # Log
                print(f"[SCHEDULER] DEXTools scan complete: {len(pairs_found) if pairs_found else 0} pairs, next in {interval}s")
                
                # Wait for next scan
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"[SCHEDULER] DEXTools error: {e}")
                await asyncio.sleep(120)  # Longer error backoff for DEXTools
    
    def _calculate_interval(self, source: str) -> float:
        """
        Calculate scan interval with jitter.
        
        Args:
            source: 'dexscreener' or 'dextools'
            
        Returns:
            Interval in seconds
        """
        if source == 'dexscreener':
            min_interval = self.dexscreener_interval_min
            max_interval = self.dexscreener_interval_max
        elif source == 'dextools':
            min_interval = self.dextools_interval_min
            max_interval = self.dextools_interval_max
        else:
            return 60.0
        
        # Add jitter (random between min and max)
        interval = random.uniform(min_interval, max_interval)
        
        # Apply backoff if active
        if self.backoff_active:
            interval *= self.backoff_multiplier
        
        return interval
    
    def trigger_backoff(self, duration_seconds: int = 300):
        """
        Trigger emergency backoff due to rate limiting.
        
        Args:
            duration_seconds: How long to back off (default 5 minutes)
        """
        from datetime import datetime, timedelta
        
        self.backoff_active = True
        self.backoff_until = datetime.now() + timedelta(seconds=duration_seconds)
        
        print(f"[SCHEDULER] EMERGENCY BACKOFF: {duration_seconds}s")
    
    def clear_backoff(self):
        """Clear backoff state."""
        self.backoff_active = False
        self.backoff_until = None
        print("[SCHEDULER] Backoff cleared")
    
    def get_stats(self) -> Dict:
        """
        Get scheduler statistics.
        
        Returns:
            Dict with scheduler stats
        """
        return {
            'scans_performed': self.scans_performed.copy(),
            'pairs_found': self.pairs_found.copy(),
            'last_scan_time': {
                k: v.isoformat() if v else None
                for k, v in self.last_scan_time.items()
            },
            'backoff_active': self.backoff_active,
            'intervals': {
                'dexscreener': f"{self.dexscreener_interval_min}-{self.dexscreener_interval_max}s",
                'dextools': f"{self.dextools_interval_min}-{self.dextools_interval_max}s",
            },
        }
