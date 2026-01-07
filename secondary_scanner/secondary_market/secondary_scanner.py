"""
Secondary Market Scanner
Main orchestrator for detecting existing tokens with breakout potential
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
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
        self.max_pairs_per_scan = chain_config.get('secondary_scanner', {}).get('max_pairs', 50)
        self.max_pairs = self.max_pairs_per_scan # Add explicit alias for compatibility
        self.min_liquidity_threshold = chain_config.get('secondary_scanner', {}).get('min_liquidity', 50000)

        # Block range configuration (6 hours worth)
        self.lookback_blocks = {
            'ethereum': 1800,  # ~6 hours at 12s blocks
            'base': 3000,      # ~6 hours at 7.2s blocks
        }.get(self.chain_name, 1800)

        # Status tracking
        self.secondary_status = "ACTIVE"
        self.last_scanned_block = {}  # {dex_type: last_block}

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

        # Uniswap V2 Factory ABI (minimal for events)
        self.v2_factory_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
                    {"indexed": False, "internalType": "address", "name": "pair", "type": "address"},
                    {"indexed": False, "internalType": "uint256", "name": "", "type": "uint256"}
                ],
                "name": "PairCreated",
                "type": "event"
            }
        ]

        # Uniswap V3 Factory ABI (minimal for events)
        self.v3_factory_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "internalType": "address", "name": "token0", "type": "address"},
                    {"indexed": True, "internalType": "address", "name": "token1", "type": "address"},
                    {"indexed": True, "internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"indexed": False, "internalType": "int24", "name": "tickSpacing", "type": "int24"},
                    {"indexed": False, "internalType": "address", "name": "pool", "type": "address"}
                ],
                "name": "PoolCreated",
                "type": "event"
            }
        ]

    def is_enabled(self) -> bool:
        """Check if secondary scanner is enabled"""
        return self.config.get('secondary_scanner', {}).get('enabled', False)

    def resolve_secondary_block_range(self, lookback_blocks: int):
        """Resolve block range for secondary scanning"""
        latest = self.web3.eth.block_number
        from_block = max(latest - lookback_blocks, 0)
        return from_block, latest

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
                    # Checksum the factory address
                    factory_address = Web3.to_checksum_address(factory_address)
                    
                    # Resolve block range using configured lookback
                    from_block, latest_block = self.resolve_secondary_block_range(self.lookback_blocks)
                    
                    # Use cached last scanned block to avoid re-scanning
                    last_scanned = self.last_scanned_block.get(dex_type, 0)
                    from_block = max(from_block, last_scanned + 1)
                    
                    if from_block >= latest_block:
                        continue  # No new blocks to scan
                    
                    # PairCreated/PoolCreated event signature
                    pair_created_sig = self.pair_created_sigs.get(dex_type)
                    if not pair_created_sig:
                        continue
                    
                    try:
                        # Strategy 1: Use contract.events.get_logs with snake_case params (Web3.py v7 style)
                        # The previous error 'unexpected keyword fromBlock' suggests it enforces snake_case
                        
                        event_contract = None
                        if dex_type == 'uniswap_v2':
                            event_contract = self.web3.eth.contract(address=factory_address, abi=self.v2_factory_abi).events.PairCreated
                        elif dex_type == 'uniswap_v3':
                            event_contract = self.web3.eth.contract(address=factory_address, abi=self.v3_factory_abi).events.PoolCreated
                        
                        if event_contract:
                            try:
                                # Try standard v6/v7 get_logs with snake_case
                                logs = event_contract.get_logs(
                                    from_block=from_block,  # snake_case
                                    to_block=latest_block
                                )
                            except TypeError:
                                # Fallback: Try camelCase (older Web3.py)
                                logs = event_contract.get_logs(
                                    fromBlock=from_block,
                                    toBlock=latest_block
                                )
                            
                            print(f"🔍 [SECONDARY] {self.chain_name.upper()}: Found {len(logs)} {dex_type.upper()} pairs in last {self.lookback_blocks} blocks")
                            
                            # Update last scanned block
                            self.last_scanned_block[dex_type] = latest_block
                            
                    except Exception as e:
                        # Strategy 2: Raw eth_getLogs fallback (if Contract API fails)
                        # This is the lowest level and most robust if params are correct
                        try:
                            payload = {
                                'address': factory_address,
                                'topics': [pair_created_sig], # Array of 32-byte hex strings
                                'fromBlock': hex(from_block),
                                'toBlock': hex(latest_block)
                            }
                            logs = self.web3.eth.get_logs(payload)
                            print(f"🔍 [SECONDARY] {self.chain_name.upper()}: Found {len(logs)} {dex_type.upper()} pairs (RAW FALLBACK)")
                            self.last_scanned_block[dex_type] = latest_block
                            
                        except Exception as raw_e:
                            # If both fail, report but don't crash
                            print(f"⚠️  [SECONDARY] Error scanning {dex_type} factory: {e} | Raw: {raw_e}")
                            self.secondary_status = "DEGRADED"
                            continue
                    
                    # Process events
                    for log in logs[-100:]:  # Last 100 events
                        try:
                            # Extract data from event
                            event_data = dict(log['args'])
                            
                            if dex_type == 'uniswap_v2':
                                token0 = event_data.get('token0')
                                token1 = event_data.get('token1')
                                pair_address = event_data.get('pair')
                            elif dex_type == 'uniswap_v3':
                                token0 = event_data.get('token0')
                                token1 = event_data.get('token1')
                                pair_address = event_data.get('pool')
                            else:
                                continue
                            
                            # Determine meme token (not WETH)
                            weth_address = self.config.get('weth_address')
                            if not weth_address:
                                # Fallback WETH addresses
                                if self.chain_name == 'base':
                                    weth_address = '0x4200000000000000000000000000000000000006'
                                else:
                                    weth_address = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
                            
                            weth_address = weth_address.lower()
                            
                            if not token0 or not token1:
                                continue

                            if token0.lower() == weth_address:
                                token_address = token1
                            elif token1.lower() == weth_address:
                                token_address = token0
                            else:
                                # Both are not WETH? Might be stable pair or other.
                                # For safety, assume token0 is the token if token1 is stable, etc.
                                # But simpler to skip if we strictly want ETH pairs.
                                # Let's accept it and assume token0 is target for now to capture more pairs.
                                token_address = token0
                            
                            pair_data = {
                                'pair_address': Web3.to_checksum_address(pair_address),
                                'token_address': Web3.to_checksum_address(token_address),
                                'dex_type': dex_type,
                                'token_decimals': 18,
                                'block_number': log['blockNumber'],
                                'chain': self.chain_name,
                                'weth_address': weth_address # CRITICAL: Required for process_pair
                            }
                            
                            pairs.append(pair_data)
                            
                        except Exception as e:
                            # print(f"DEBUG: Malformed log: {e}") 
                            continue  # Skip malformed events
                    
                except Exception as e:
                    print(f"⚠️  [SECONDARY] Error scanning {dex_type} factory: {e}")
                    continue
            
            # Remove duplicates and limit to 50 pairs per chain
            seen_pairs = set()
            unique_pairs = []
            
            # Debug:
            # print(f"DEBUG: Raw pairs found: {len(pairs)}")
            
            for pair in pairs:
                pair_key = (pair['pair_address'], pair['token_address'])
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    unique_pairs.append(pair)
            
            # Sort by block number (most recent first) and take top 50
            unique_pairs.sort(key=lambda x: x['block_number'], reverse=True)
            final_pairs = unique_pairs[:50]
            
            if final_pairs:
                self.secondary_status = "ACTIVE"
                print(f"✅ [SECONDARY] {self.chain_name.upper()}: Monitoring {len(final_pairs)} pairs")
            else:
                print(f"⚠️  [SECONDARY] {self.chain_name.upper()}: No pairs found")
            
            return final_pairs
            
        except Exception as e:
            print(f"⚠️  [SECONDARY] Error discovering pairs: {e}")
            return []

    def add_pair_to_monitor(self, pair_address: str, token_address: str, dex_type: str, chain: str = 'base', token_decimals: int = 18, **kwargs):
        """
        Add a pair to monitoring list.
        
        Args:
            pair_address: Address of the pair/pool
            token_address: Address of the token we care about
            dex_type: 'uniswap_v2' or 'uniswap_v3'
            chain: Chain name (e.g. 'base')
            token_decimals: Token decimals (default 18)
            **kwargs: Additional arguments (like block_number)
        """
        try:
            # Check maximum pairs
            if len(self.monitored_pairs) >= self.max_pairs:
                return False
                
            # Add to monitored list
            # Use chain-prefixed ID to allow multi-chain monitoring
            pair_id = f"{chain}:{pair_address.lower()}"
            
            # Also support legacy lookups by raw address (for now)
            self.monitored_pairs[pair_address.lower()] = {
                'pair_address': pair_address,
                'token_address': token_address,
                'dex_type': dex_type,
                'chain': chain,
                'decimals': token_decimals,
                'block_number': kwargs.get('block_number', 0),
                'added_at': datetime.now().isoformat()
            }
            
            # Log success (first time only)
            pass
            
            return True
            
        except Exception as e:
            print(f"⚠️  [SECONDARY] Error adding pair: {e}")
            return False

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

            # Build valid payload with nested topics array
            payload = {
                'address': pair_address,
                'topics': [[signature]],  # Nested array for topic filtering
                'fromBlock': hex(from_block),
                'toBlock': hex(latest_block)
            }

            try:
                # Query events
                logs = self.web3.eth.get_logs(payload)
            except Exception as e:
                if hasattr(e, 'args') and len(e.args) > 0:
                    error_data = e.args[0]
                    if isinstance(error_data, dict) and error_data.get('code') == -32602:
                        print(f"❌ [SECONDARY_RPC_PAYLOAD_INVALID] {self.chain_name.upper()}: {payload}")
                        self.secondary_status = "DEGRADED"
                        return []
                raise e

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
            'chain': self.chain_name,
            'status': self.secondary_status,
            'last_scanned_blocks': self.last_scanned_block
        }