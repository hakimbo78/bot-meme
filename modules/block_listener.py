import asyncio
import time
from typing import Dict, List, Callable, Any
from web3 import Web3

class SharedBlockCache:
    """
    Global cache for latest block numbers to prevent duplicate RPC calls.
    Accessible by all modules to read latest block without fetching.
    """
    _cache: Dict[str, int] = {}
    
    @classmethod
    def update(cls, chain: str, block_number: int):
        cls._cache[chain] = block_number
        
    @classmethod
    def get(cls, chain: str) -> int:
        return cls._cache.get(chain, 0)

class GlobalBlockFeed:
    """
    Singleton-like block listener per chain.
    Polls eth_blockNumber efficiently and notifies subscribers.
    """
    _instances: Dict[str, 'GlobalBlockFeed'] = {}
    
    def __init__(self, chain: str, web3_provider: Web3, poll_interval: float = 6.0):
        self.chain = chain
        self.w3 = web3_provider
        self.poll_interval = poll_interval
        self.latest_block = 0
        self.subscribers: List[Callable[[int], Any]] = []
        self.is_running = False
        self._task = None
        
    @classmethod
    def get_instance(cls, chain: str, web3_provider: Web3 = None, poll_interval: float = 6.0) -> 'GlobalBlockFeed':
        if chain not in cls._instances:
            if web3_provider is None:
                raise ValueError(f"Web3 provider required for first initialization of {chain} block feed")
            cls._instances[chain] = cls(chain, web3_provider, poll_interval)
        return cls._instances[chain]
        
    def subscribe(self, callback: Callable[[int], Any]):
        """
        Subscribe to new block events.
        Callback signature: async def callback(block_number: int)
        """
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            print(f"🔗 [{self.chain.upper()}] New subscriber registered for block feed")

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._poll_loop(), name=f"block-feed-{self.chain}")
            print(f"🔗 [{self.chain.upper()}] Global Block Feed started (interval: {self.poll_interval}s)")
            
    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            
    async def _poll_loop(self):
        # Initial block fetch
        try:
            current = await asyncio.to_thread(self.w3.eth.get_block_number)
            self.latest_block = current
            SharedBlockCache.update(self.chain, current)
            print(f"🔗 [{self.chain.upper()}] Initial block: {current}")
        except Exception as e:
            print(f"⚠️  [{self.chain.upper()}] Failed initial block fetch: {e}")
            
        while self.is_running:
            try:
                await asyncio.sleep(self.poll_interval)
                
                # OPTIMIZATION: Simple lightweight call
                new_block = await asyncio.to_thread(self.w3.eth.get_block_number)
                
                if new_block > self.latest_block:
                    # Logs exactly as requested
                    print(f"🔥 [EVENT-DRIVEN] New block detected: {new_block}")
                    
                    self.latest_block = new_block
                    SharedBlockCache.update(self.chain, new_block)
                    
                    # Notify subscribers
                    for callback in self.subscribers:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                asyncio.create_task(callback(new_block))
                            else:
                                callback(new_block)
                        except Exception as cb_e:
                            print(f"⚠️  [{self.chain.upper()}] Subscriber error: {cb_e}")
                else:
                    # Log exactly as requested
                    # Only print if we have established a baseline block (don't spam on startup before first block)
                    if self.latest_block > 0:
                        print(f"🛑 [EVENT-DRIVEN] No new block → skipping all scans")
                    
            except Exception as e:
                print(f"⚠️  [{self.chain.upper()}] Block poll error: {e}")
                await asyncio.sleep(5)  # Backoff
