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
                    
                    # Build event contract to let Web3.py craft topics payload correctly
                    logs = []
                    event_contract = None
                    if dex_type == 'uniswap_v2':
                        event_contract = self.web3.eth.contract(address=factory_address, abi=self.v2_factory_abi).events.PairCreated
                    elif dex_type == 'uniswap_v3':
                        event_contract = self.web3.eth.contract(address=factory_address, abi=self.v3_factory_abi).events.PoolCreated
                    else:
                        continue

                    # Query using Web3.py helpers (handles topics array internally). Try snake_case then camelCase for compatibility.
                    try:
                        logs = event_contract.get_logs(from_block=from_block, to_block=latest_block)
                    except TypeError:
                        # Some nodes/web3 versions expect camelCase
                        logs = event_contract.getLogs(fromBlock=from_block, toBlock=latest_block)

                    print(f"🔍 [SECONDARY] {self.chain_name.upper()}: Found {len(logs)} {dex_type.upper()} pairs in last {self.lookback_blocks} blocks")

                    # Update last scanned block
                    self.last_scanned_block[dex_type] = latest_block
                    
                    # Process last 100 pairs (most recent)
                    for log in logs[-100:]:
                        try:
                            # Use decoded args from Web3 instead of manual topic slicing
                            args = log.get('args', {})
                            token0 = args.get('token0')
                            token1 = args.get('token1')

                            if dex_type == 'uniswap_v2':
                                pair_address = args.get('pair')
                            elif dex_type == 'uniswap_v3':
                                pair_address = args.get('pool')
                            else:
                                continue

                            if not (token0 and token1 and pair_address):
                                continue

                            weth_address = chain_config.get('weth_address', '').lower()
                            if token0.lower() == weth_address:
                                token_address = token1
                            elif token1.lower() == weth_address:
                                token_address = token0
                            else:
                                continue  # Non-WETH pairs skipped

                            pair_data = {
                                'pair_address': Web3.to_checksum_address(pair_address),
                                'token_address': Web3.to_checksum_address(token_address),
                                'dex_type': dex_type,
                                'token_decimals': 18,  # Assume 18 decimals
                                'block_number': log['blockNumber'],
                                'chain': self.chain_name,
                                'weth_address': chain_config.get('weth_address')
                            }

                            pairs.append(pair_data)

                        except Exception:
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
            
            if final_pairs:
                self.secondary_status = "ACTIVE"
                print(f"✅ [SECONDARY] {self.chain_name.upper()}: Monitoring {len(final_pairs)} pairs")
            else:
                print(f"⚠️  [SECONDARY] {self.chain_name.upper()}: No pairs found")
            
            return final_pairs
            
        except Exception as e:
            print(f"⚠️  [SECONDARY] Error discovering pairs: {e}")
            return []

    def add_pair_to_monitor(self, pair_address: str, token_address: str,
                           dex_type: str, token_decimals: int = 18,
                           weth_address: Optional[str] = None, **kwargs):
        """Add a pair to the monitoring list"""
        resolved_weth = (weth_address or self.config.get(
            'weth_address', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
        ))

        # Normalize addresses to checksum to avoid mismatches
        pair_addr_cs = Web3.to_checksum_address(pair_address)
        token_addr_cs = Web3.to_checksum_address(token_address)
        weth_addr_cs = Web3.to_checksum_address(resolved_weth)

        self.monitored_pairs[pair_addr_cs] = {
            'token_address': token_addr_cs,
            'dex_type': dex_type,
            'token_decimals': token_decimals,
            'last_scan': 0,
            'weth_address': weth_addr_cs
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

            # Use checksum address
            pair_address = Web3.to_checksum_address(pair_address)

            # Enforce topics list-of-list per eth_getLogs variadic rules
            assert isinstance(signature, str)
            assert isinstance(from_block, int)

            # Build payload with flat topics list (single signature) and hex blocks
            payload = {
                'address': pair_address,
                'topics': [signature],
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
                pair_data.get('weth_address') or self.config.get(
                    'weth_address', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
                ),
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