"""
Secondary Market Scanner
Main orchestrator for detecting existing tokens with breakout potential
"""
import asyncio
import time
from typing import Dict, List, Optional
from web3 import Web3
from .market_metrics import MarketMetrics
from .triggers import TriggerEngine
from .secondary_state import SecondaryStateManager, SecondaryState


class SecondaryScanner:
    """
    Main scanner for secondary market opportunities.
    Monitors existing pairs for breakout signals.
    """

    def __init__(self, web3_provider: Web3, chain_config: Dict):
        self.web3 = web3_provider
        self.config = chain_config
        self.chain_name = chain_config.get('chain_name', 'unknown')

        # Initialize components
        self.metrics = MarketMetrics(web3_provider, chain_config)
        self.triggers = TriggerEngine(chain_config.get('secondary_scanner', {}))
        self.state_manager = SecondaryStateManager()

        # Configuration
        self.scan_interval = 30  # seconds
        self.max_pairs_per_scan = 100
        self.min_liquidity_threshold = chain_config.get('secondary_scanner', {}).get('min_liquidity', 50000)

        # Known pairs to monitor: {pair_address: {'token_address': str, 'dex_type': str, 'last_scan': float}}
        self.monitored_pairs = {}

        # Swap event signatures
        self.swap_signatures = {
            'uniswap_v2': '0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822e',
            'uniswap_v3': '0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67b'
        }

        # Pair/Pool created event signatures
        self.pair_created_sigs = {
            'uniswap_v2': '0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28ed612',
            'uniswap_v3': '0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4ee871103'
        }

    def is_enabled(self) -> bool:
        """Check if secondary scanner is enabled"""
        return self.config.get('secondary_scanner', {}).get('enabled', False)

    def discover_pairs(self) -> List[Dict]:
        """
        Discover existing pairs to monitor by scanning recent PairCreated events.
        """
        try:
            pairs = []
            chain_config = self.config
            
            # Get factory addresses
            factories = chain_config.get('factories', {})
            
            for dex_type, factory_address in factories.items():
                if dex_type not in ['uniswap_v2', 'uniswap_v3']:
                    continue
                    
                try:
                    # Use lowercase address for RPC compatibility
                    factory_address = factory_address.lower()
                    
                    # Get recent blocks (last 100 blocks ~ 30 minutes)
                    latest_block = self.web3.eth.block_number
                    from_block = max(0, latest_block - 100)
                    
                    # PairCreated/PoolCreated event signature
                    pair_created_sig = self.pair_created_sigs.get(dex_type)
                    if not pair_created_sig:
                        continue
                    
                    # Query PairCreated/PoolCreated events
                    logs = self.web3.eth.get_logs({
                        'address': factory_address,
                        'topics': [pair_created_sig],
                        'fromBlock': hex(from_block),
                        'toBlock': hex(latest_block)
                    })
                    
                    print(f"🔍 [SECONDARY] {self.chain_name.upper()}: Found {len(logs)} {dex_type.upper()} pairs in last 10000 blocks")
                    
                    # Process last 100 pairs (most recent)
                    for log in logs[-100:]:
                        try:
                            # Decode event data
                            data = log['data']
                            topics = log['topics']
                            
                            if len(topics) >= 3:
                                # topics[1] = token0, topics[2] = token1
                                token0 = '0x' + topics[1].hex()[26:]  # Remove padding
                                token1 = '0x' + topics[2].hex()[26:]
                                
                                # Extract pair/pool address from data
                                if dex_type == 'uniswap_v2':
                                    # V2: data = pair_address (32 bytes) + liquidity (32 bytes)
                                    if len(data) >= 64:
                                        pair_address = '0x' + data[2:66]  # Skip 0x, take 64 chars (32 bytes)
                                    else:
                                        continue
                                elif dex_type == 'uniswap_v3':
                                    # V3: data = tickSpacing (32 bytes) + pool_address (32 bytes)
                                    if len(data) >= 128:
                                        pair_address = '0x' + data[66:130]  # After tickSpacing
                                    else:
                                        continue
                                
                                # For simplicity, assume token1 is the meme token (not WETH)
                                weth_address = chain_config.get('weth_address', '').lower()
                                if token0.lower() == weth_address:
                                    token_address = token1
                                elif token1.lower() == weth_address:
                                    token_address = token0
                                else:
                                    # Skip non-WETH pairs for now
                                    continue
                                
                                pair_data = {
                                    'pair_address': pair_address.lower(),
                                    'token_address': token_address.lower(),
                                    'dex_type': dex_type,
                                    'token_decimals': 18,  # Assume 18 decimals
                                    'block_number': log['blockNumber'],
                                    'chain': self.chain_name
                                }
                                
                                pairs.append(pair_data)
                                
                        except Exception as e:
                            continue  # Skip malformed logs
                    
                except Exception as e:
                    print(f"⚠️  [SECONDARY] Error scanning {dex_type} factory: {e}")
                    continue
            
            # Remove duplicates and limit to 50 pairs per chain
            seen_pairs = set()
            unique_pairs = []
            for pair in pairs:
                pair_key = (pair['pair_address'], pair['token_address'])
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    unique_pairs.append(pair)
            
            # Sort by block number (most recent first) and take top 50
            unique_pairs.sort(key=lambda x: x['block_number'], reverse=True)
            final_pairs = unique_pairs[:50]
            
            print(f"✅ [SECONDARY] {self.chain_name.upper()}: Monitoring {len(final_pairs)} pairs")
            
            return final_pairs
            
        except Exception as e:
            print(f"⚠️  [SECONDARY] Error discovering pairs: {e}")
            return []

    def add_pair_to_monitor(self, pair_address: str, token_address: str,
                           dex_type: str, token_decimals: int = 18):
        """Add a pair to the monitoring list"""
        self.monitored_pairs[pair_address] = {
            'token_address': token_address,
            'dex_type': dex_type,
            'token_decimals': token_decimals,
            'last_scan': 0,
            'weth_address': self.config.get('weth_address', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')
        }

    async def scan_pair_events(self, pair_address: str, pair_data: Dict) -> List[Dict]:
        """
        Scan recent events for a pair to update metrics.
        Returns list of swap events with volume data.
        """
        try:
            dex_type = pair_data['dex_type']
            signature = self.swap_signatures.get(dex_type)
            if not signature:
                return []

            # Get latest block
            latest_block = self.web3.eth.block_number
            from_block = max(0, latest_block - 100)  # Last ~5 minutes assuming 12s blocks

            # Use lowercase address
            pair_address = pair_address.lower()

            # Query events
            logs = self.web3.eth.get_logs({
                'address': pair_address,
                'topics': [signature],
                'fromBlock': hex(from_block),
                'toBlock': hex(latest_block)
            })

            events = []
            for log in logs:
                # Parse swap event (simplified)
                # In practice, you'd decode the event data properly
                events.append({
                    'block_number': log['blockNumber'],
                    'transaction_hash': log['transactionHash'].hex(),
                    'timestamp': self.web3.eth.get_block(log['blockNumber'])['timestamp'],
                    'volume_usd': 0  # Would calculate from event data
                })

            return events

        except Exception as e:
            print(f"⚠️  Error scanning events for {pair_address}: {e}")
            return []

    async def process_pair(self, pair_address: str) -> Optional[Dict]:
        """
        Process a single pair: update metrics, evaluate triggers.
        Returns signal data if secondary signal detected.
        """
        pair_data = self.monitored_pairs.get(pair_address)
        if not pair_data:
            return None

        try:
            # Update metrics from on-chain data
            current_data = self.metrics.update_pair_data(
                pair_address,
                pair_data['dex_type'],
                pair_data['token_address'],
                pair_data['weth_address'],
                pair_data['token_decimals']
            )

            if not current_data:
                return None

            # Scan recent swap events for volume
            swap_events = await self.scan_pair_events(pair_address, pair_data)

            # Add volume data (simplified - would sum actual volumes)
            total_volume = sum(event.get('volume_usd', 0) for event in swap_events)
            if total_volume > 0:
                self.metrics.add_swap_volume(pair_address, total_volume)

            # Get rolling metrics
            metrics = self.metrics.get_rolling_metrics(pair_address)
            if not metrics:
                return None

            # Evaluate triggers
            trigger_result = self.triggers.evaluate_triggers(metrics)

            # Update last scan time
            pair_data['last_scan'] = time.time()

            # Check for secondary signal
            if trigger_result['secondary_signal']:
                token_address = pair_data['token_address']

                # Initialize or update state
                current_state = self.state_manager.get_state(token_address)
                if current_state is None:
                    # New detection
                    new_state = self.state_manager.initialize_token(token_address, {
                        **trigger_result,
                        'timestamp': time.time(),
                        'pair_address': pair_address,
                        'dex_type': pair_data['dex_type']
                    })
                else:
                    # Check for auto-upgrade
                    new_state = self.state_manager.check_auto_upgrade(token_address)

                return {
                    'token_address': token_address,
                    'pair_address': pair_address,
                    'dex_type': pair_data['dex_type'],
                    'chain': self.chain_name,
                    'metrics': metrics,
                    'triggers': trigger_result,
                    'state': new_state or current_state,
                    'signal_type': 'secondary_market'
                }

        except Exception as e:
            print(f"⚠️  Error processing pair {pair_address}: {e}")

        return None

    async def scan_all_pairs(self) -> List[Dict]:
        """
        Scan all monitored pairs for signals.
        Returns list of detected signals.
        """
        signals = []

        # Limit concurrent processing
        semaphore = asyncio.Semaphore(10)

        async def process_with_limit(pair_addr):
            async with semaphore:
                result = await self.process_pair(pair_addr)
                if result:
                    signals.append(result)

        # Process pairs concurrently
        tasks = [process_with_limit(addr) for addr in self.monitored_pairs.keys()]
        await asyncio.gather(*tasks, return_exceptions=True)

        return signals

    async def run_continuous_scan(self):
        """Run continuous scanning loop"""
        print(f"🚀 Starting secondary market scanner for {self.chain_name}")

        while True:
            try:
                start_time = time.time()

                # Discover new pairs (if implemented)
                new_pairs = self.discover_pairs()
                for pair in new_pairs:
                    self.add_pair_to_monitor(**pair)

                # Scan existing pairs
                signals = await self.scan_all_pairs()

                # Process signals (would integrate with main pipeline)
                for signal in signals:
                    await self._handle_signal(signal)

                # Cleanup old data
                self.state_manager.cleanup_old_tokens()

                # Wait for next scan
                elapsed = time.time() - start_time
                sleep_time = max(0, self.scan_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                print(f"⚠️  Secondary scanner error: {e}")
                await asyncio.sleep(self.scan_interval)

    async def _handle_signal(self, signal: Dict):
        """Handle detected signal (integrate with main pipeline)"""
        # This would integrate with the main scanner's alert system
        # For now, just print
        print(f"🎯 Secondary signal: {signal['token_address']} - {signal['state'].value}")

    def get_stats(self) -> Dict:
        """Get scanner statistics"""
        return {
            'monitored_pairs': len(self.monitored_pairs),
            'state_stats': self.state_manager.get_stats(),
            'chain': self.chain_name
        }