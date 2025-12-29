"""
Multi-chain scanner orchestrator
Manages scanning across multiple blockchain networks

Enhanced with Safety Audit Features:
- Validation for incomplete adapters
- Warning logs for disabled chains
- Explicit skip for audit-enforced disabled chains
"""
import asyncio
import time
from typing import List, Dict, Optional
from chain_adapters import get_adapter_for_chain
import traceback

# EVENT-DRIVEN IMPORTS
from modules.block_listener import GlobalBlockFeed, SharedBlockCache
from modules.market_heat import MarketHeatEngine, HeatState



class MultiChainScanner:
    """Orchestrates scanning across multiple chains"""
    
    def __init__(self, enabled_chains: List[str], chain_configs: Dict, error_monitor=None):
        """
        Initialize scanners for all enabled chains.
        
        Includes safety validation for incomplete/disabled adapters.
        
        Args:
            enabled_chains: List of chain names to enable (e.g., ['base', 'ethereum'])
            chain_configs: Dict of chain configurations from chains.yaml
            error_monitor: Optional ErrorMonitor instance for critical error alerts
        """
        self.adapters = {}
        self.chain_configs = chain_configs
        self.skipped_chains = {}
        self.error_monitor = error_monitor
        self.heartbeats = {} # Last successful scan timestamp
        self.tasks = []
        self.is_running = False
        
        # EVENT-DRIVEN STATE
        self.heat_engines = {}
        self.block_feeds = {}
        
        # Filter out Solana if it's handled by dedicated module in main.py
        # We do this to avoid redundant RPC calls and timeouts
        enabled_chains = [c for c in enabled_chains if c.lower() != 'solana']
        
        print(f"\n🔗 Initializing multi-chain scanner...")
        print(f"📡 Target chains: {', '.join([c.upper() for c in enabled_chains])}\n")
        
        for chain_name in enabled_chains:
            if chain_name not in chain_configs:
                print(f"❌ [{chain_name.upper()}] Configuration not found in chains.yaml")
                continue
            
            config = chain_configs[chain_name]
            
            # SAFETY CHECK: Skip explicitly disabled chains
            if not config.get('enabled', False):
                disabled_reason = config.get('disabled_reason', 'Disabled in config')
                print(f"⚠️  [{chain_name.upper()}] SKIPPED - {disabled_reason}")
                self.skipped_chains[chain_name] = disabled_reason
                continue
            
            # SAFETY CHECK: Validate required adapter configuration
            adapter = get_adapter_for_chain(chain_name, config)
            
            if adapter is None:
                print(f"⚠️  [{chain_name.upper()}] No adapter available for this chain type")
                self.skipped_chains[chain_name] = "No adapter implementation"
                continue
            
            if adapter and adapter.connect():
                self.adapters[chain_name] = adapter
            else:
                print(f"⚠️  [{chain_name.upper()}] Skipped due to connection failure\n")
                self.skipped_chains[chain_name] = "Connection failed"
        
        if not self.adapters:
            print("❌ No chains connected! Check your configuration and RPC endpoints.\n")
        else:
            print(f"✅ Successfully connected to {len(self.adapters)} chain(s)")
            if self.skipped_chains:
                print(f"⚠️  Skipped {len(self.skipped_chains)} chain(s): {', '.join(self.skipped_chains.keys())}")
            print("")
    
    def scan_all_chains(self) -> List[Dict]:
        """Legacy blocking scanner (Deprecated)"""
        return []

    async def start_async(self, output_queue: asyncio.Queue):
        """
        Start isolated async tasks for all chains + health monitor.
        Entries are put into output_queue.
        """
        self.is_running = True
        print(f"🚀 Starting async chain scanners...")
        
        # 1. Start chain loops
        for chain_name in self.adapters:
            task = asyncio.create_task(
                self._chain_loop(chain_name, output_queue),
                name=f"scanner-{chain_name}"
            )
            self.tasks.append(task)
            print(f"   ➤ Started task: scanner-{chain_name}")
            
        # 2. Start health monitor
        monitor_task = asyncio.create_task(
            self._health_monitor(),
            name="health-monitor"
        )
        self.tasks.append(monitor_task)
        
    async def _chain_loop(self, chain_name: str, queue: asyncio.Queue):
        """
        EVENT-DRIVEN SCAN LOOP
        Triggered by GlobalBlockFeed on new blocks only.
        Gated by MarketHeatEngine.
        """
        adapter = self.adapters[chain_name]
        print(f"✅ [{chain_name.upper()}] Event-driven scanner connected")
        
        # Initialize Market Heat Engine for this chain
        if chain_name not in self.heat_engines:
            self.heat_engines[chain_name] = MarketHeatEngine.get_instance(chain_name)
        
        # Inject heat engine into adapter for internal use
        adapter.heat_engine = self.heat_engines[chain_name]
        
        # Initialize Global Block Feed
        feed = GlobalBlockFeed.get_instance(chain_name, adapter.w3)
        self.block_feeds[chain_name] = feed
        
        # Define Event Handler
        async def on_block(block_number: int):
            try:
                # 1. MARKET HEAT GATE
                heat_engine = self.heat_engines[chain_name]
                if heat_engine.is_cold():
                    print(f"⏸️  [GATED][{chain_name.upper()}] Market COLD ({heat_engine.get_status_str()}) → factory scan skipped")
                    return # NO RPC
                
                # 2. RUN SCAN DELTA
                # Update heartbeat
                self.heartbeats[chain_name] = time.time()
                
                # Run scan (pass explicit block to avoid RPC)
                pairs = await adapter.scan_new_pairs_async(target_block=block_number)
                
                if pairs:
                    print(f"🔥 [EVENT-DRIVEN][{chain_name.upper()}] Found {len(pairs)} pairs in block {block_number}")
                    # Record activity -> Heat Up
                    heat_engine.record_activity()
                    
                    for pair in pairs:
                        await queue.put(pair)
                else:
                    # Optional: Print idle message (strictly requested: 🛑 [EVENT-DRIVEN] No new block... but this is 'on_block' so it IS a new block)
                    # The user requested: "🛑 [EVENT-DRIVEN] No new block → skipping all scans" - this is handled by BlockListener not calling us if no block.
                    # We are here implies new block.
                    pass
                    
            except Exception as e:
                print(f"⚠️  [{chain_name.upper()}] Block handler error: {e}")
                # traceback.print_exc()

        # Subscribe
        feed.subscribe(on_block)
        
        # Start Feed
        feed.start()
        
        # Keep task alive but idle (feed runs in background task)
        try:
            while self.is_running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            print(f"🛑 [{chain_name.upper()}] Task cancelled")
            feed.stop()

    async def _health_monitor(self):
        """Monitor chain heartbeats and flag stalls - CU-AWARE"""
        print("❤️  Health monitor active (CU-optimized)")
        while self.is_running:
            await asyncio.sleep(30) # Check every 30s (less frequent for CU optimization)
            
            now = time.time()
            for chain_name, last_beat in self.heartbeats.items():
                diff = now - last_beat
                
                # Get chain-specific scan interval from adapter (CU-optimized)
                adapter = self.adapters.get(chain_name)
                if adapter:
                    scan_interval = getattr(adapter, 'scan_interval', 30)
                else:
                    scan_interval = 30
                stall_threshold = scan_interval + 30  # Allow scan_interval + 30s buffer
                
                if diff > stall_threshold:
                    msg = f"CHAIN STALLED: No activity for {int(diff)}s (expected every {scan_interval}s)"
                    print(f"🔴 [{chain_name.upper()}] {msg}")
                    
                    if self.error_monitor:
                        try:
                            # Clean message for Telegram (avoid special chars that might break parsing)
                            clean_msg = f"No activity for {int(diff)}s, expected every {scan_interval}s"
                            await self.error_monitor.send_error_alert(
                                error_type="CHAIN_STALLED",
                                error_message=clean_msg,
                                chain=chain_name
                            )
                        except Exception as e:
                            print(f"⚠️  Failed to send error alert: {e}")
    
    def get_adapter(self, chain_name: str):
        """Get adapter for a specific chain"""
        return self.adapters.get(chain_name)
    
    def get_chain_config(self, chain_name: str) -> Dict:
        """Get configuration for a specific chain"""
        return self.chain_configs.get(chain_name, {})

