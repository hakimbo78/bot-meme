"""
TRUE GLOBAL EVENT-DRIVEN BLOCK SERVICE
======================================
Implements strict single-source-of-truth block fetching.

Hard Constraints:
1. Only ONE service calls eth_blockNumber per chain
2. Shared BlockSnapshot distribution
3. Hardcoded chain_id (via config)
4. Event fan-out to all modules
"""

import asyncio
import time
from typing import Dict, List, Callable, Optional, Set, Any
from dataclasses import dataclass, field
from web3 import Web3

# -----------------------------------------------------------------------------
# 1. SHARED BLOCK SNAPSHOT
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class BlockSnapshot:
    """
    Immutable snapshot of a block event.
    Must be passed to ALL consumers.
    """
    chain_name: str
    chain_id: int            # HARDCODED from config, never fetched
    block_number: int        # From eth_blockNumber
    timestamp: int           # From eth_getBlock(header) or estimated
    block_hash: str = ""     # Optional, only if fetched
    
    # Metadata
    is_strict_mode: bool = False
    
    @property
    def key(self) -> str:
        return f"{self.chain_name}:{self.block_number}"

# -----------------------------------------------------------------------------
# 2. GLOBAL EVENT BUS
# -----------------------------------------------------------------------------

class EventBus:
    """
    Simple async event bus for fan-out.
    """
    _subscribers: Dict[str, List[Callable[[BlockSnapshot], Any]]] = {}
    
    @classmethod
    def subscribe(cls, topic: str, callback: Callable):
        if topic not in cls._subscribers:
            cls._subscribers[topic] = []
        cls._subscribers[topic].append(callback)
        
    @classmethod
    async def publish(cls, topic: str, snapshot: BlockSnapshot):
        if topic not in cls._subscribers:
            return
            
        tasks = []
        for cb in cls._subscribers[topic]:
            try:
                if asyncio.iscoroutinefunction(cb):
                    tasks.append(asyncio.create_task(cb(snapshot)))
                else:
                    # Run synchronous callbacks in thread pool to avoid blocking loop
                    tasks.append(asyncio.to_thread(cb, snapshot))
            except Exception as e:
                print(f"⚠️  [EVENT-BUS] Delivery error: {e}")
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# -----------------------------------------------------------------------------
# 3. GLOBAL BLOCK SERVICE
# -----------------------------------------------------------------------------

class GlobalBlockService:
    """
    Singleton service that owns the connection to the blockchain.
    Responsible for:
    - Polling eth_blockNumber (Strictly controlled interval)
    - Fetching block timestamp (Once per block)
    - Creating BlockSnapshot
    - Publishing to EventBus
    """
    _instances: Dict[str, 'GlobalBlockService'] = {}
    
    def __init__(self, chain_name: str, chain_id: int, w3: Web3, interval: float = 30.0):
        self.chain_name = chain_name
        self.chain_id = chain_id
        self.w3 = w3
        self.interval = interval
        self.latest_block = 0
        self.is_running = False
        self.strict_mode = False
        self._task = None
        
        # LRU Cache for processed blocks to prevent duplicates
        self._processed_blocks: Set[int] = set()
        
    @classmethod
    def get_instance(cls, chain_name: str, chain_id: int, w3: Web3, interval: float = 180.0):
        if chain_name not in cls._instances:
            cls._instances[chain_name] = cls(chain_name, chain_id, w3, interval)
        return cls._instances[chain_name]
        
    def set_strict_mode(self, enabled: bool):
        """Enable stricter polling (slower) for expensive chains like Mainnet"""
        self.strict_mode = enabled
        if enabled:
            self.interval = max(self.interval, 12.0) # Minimum 12s for strict mode
            print(f"🔒 [{self.chain_name.upper()}] STRICT MODE ENABLED (Interval: {self.interval}s)")
            
    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop(), name=f"global-block-{self.chain_name}")
            print(f"🌍 [{self.chain_name.upper()}] Global Block Service STARTED")
            
    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            
    async def _loop(self):
        # Initial sync
        await self._fetch_and_publish()
        
        while self.is_running:
            try:
                await asyncio.sleep(self.interval)
                await self._fetch_and_publish()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️  [{self.chain_name.upper()}] Block Loop Error: {e}")
                await asyncio.sleep(5)
                
    async def _fetch_and_publish(self):
        """
        The ONLY place eth_blockNumber is called.
        """
        # 1. Lightest call possible
        try:
            current_block = await asyncio.to_thread(self.w3.eth.get_block_number)
        except Exception as e:
            print(f"⚠️  [{self.chain_name.upper()}] RPC Error (get_block_number): {e}")
            return

        # 2. Dedup
        if current_block <= self.latest_block or current_block in self._processed_blocks:
            return

        self.latest_block = current_block
        self._processed_blocks.add(current_block)
        
        # Keep set small
        if len(self._processed_blocks) > 100:
            self._processed_blocks.pop()

        # 3. Fetch Timestamp (One call for everyone)
        timestamp = int(time.time())
        try:
            # We only need header, but web3.py overhead is low. 
            # Optimization: could use w3.eth.get_block(current_block, full_transactions=False)
            # This is the ONLY eth_getBlockByNumber call allowed.
            block_data = await asyncio.to_thread(self.w3.eth.get_block, current_block, False)
            timestamp = block_data['timestamp']
        except Exception as e:
            print(f"⚠️  [{self.chain_name.upper()}] Failed to fetch block time: {e}")
            
        # 4. Create Snapshot
        snapshot = BlockSnapshot(
            chain_name=self.chain_name,
            chain_id=self.chain_id,  # HARDCODED
            block_number=current_block,
            timestamp=timestamp,
            is_strict_mode=self.strict_mode
        )
        
        # 5. Fan-out
        print(f"⚡ [EVENT] New Block {current_block} on {self.chain_name.upper()}")
        await EventBus.publish(f"NEW_BLOCK_{self.chain_name.upper()}", snapshot)
        
        # Also publish generic topic
        await EventBus.publish("NEW_BLOCK", snapshot)
