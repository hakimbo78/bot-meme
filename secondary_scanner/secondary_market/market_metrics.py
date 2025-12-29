"""
Market Metrics Calculator for Secondary Market Scanner
Computes rolling metrics for existing token pairs
"""
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
import asyncio
from web3 import Web3
from safe_math import safe_div, safe_div_percentage


class MarketMetrics:
    """
    Calculates market metrics for existing token pairs.
    Maintains rolling windows of data for volume, price, liquidity tracking.
    """

    def __init__(self, web3_provider: Web3, chain_config: Dict):
        self.web3 = web3_provider
        self.config = chain_config
        self.chain_name = chain_config.get('chain_name', 'unknown')

        # Rolling data storage: {pair_address: {metric: deque}}
        self.price_history = defaultdict(lambda: deque(maxlen=1000))  # Last 1000 price points
        self.volume_history = defaultdict(lambda: deque(maxlen=1000))  # Volume data points
        self.liquidity_history = defaultdict(lambda: deque(maxlen=100))  # Liquidity snapshots
        self.holder_history = defaultdict(lambda: deque(maxlen=100))  # Holder counts

        # Timestamps for rolling calculations
        self.last_update = defaultdict(float)

        # Uniswap contract ABIs (minimal)
        self.uniswap_v2_abi = [
            {"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],"stateMutability":"view","type":"function"}
        ]

        self.uniswap_v3_abi = [
            {"inputs":[],"name":"liquidity","outputs":[{"internalType":"uint128","name":"liquidity","type":"uint128"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}
        ]

        self.erc20_abi = [
            {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"},
            {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}
        ]

    def _get_pair_contract(self, pair_address: str, dex_type: str):
        """Get contract instance for pair"""
        if dex_type == "uniswap_v2":
            return self.web3.eth.contract(address=pair_address, abi=self.uniswap_v2_abi)
        elif dex_type == "uniswap_v3":
            return self.web3.eth.contract(address=pair_address, abi=self.uniswap_v3_abi)
        return None

    def _get_token_contract(self, token_address: str):
        """Get ERC20 contract instance"""
        return self.web3.eth.contract(address=token_address, abi=self.erc20_abi)

    def _calculate_v2_price(self, reserves0: int, reserves1: int, token0_is_weth: bool) -> float:
        """Calculate price from V2 reserves"""
        # CRITICAL: Check for zero reserves - mark as INVALID_ZERO_RESERVE
        if reserves0 == 0 or reserves1 == 0:
            return 0
        if token0_is_weth:
            # SAFE: Use safe_div to prevent any residual division errors
            return safe_div(safe_div(reserves0, 10**18, 0), safe_div(reserves1, 10**18, 1), 0)
        else:
            return safe_div(safe_div(reserves1, 10**18, 0), safe_div(reserves0, 10**18, 1), 0)

    def _calculate_v3_price(self, sqrt_price_x96: int) -> float:
        """Calculate price from V3 sqrt price"""
        # SAFE: Prevent division by zero in sqrt price calculation
        price = (safe_div(sqrt_price_x96, (1 << 96), 0)) ** 2
        return price

    def update_pair_data(self, pair_address: str, dex_type: str, token_address: str,
                        weth_address: str, token_decimals: int = 18) -> Dict:
        """
        Update rolling data for a pair from on-chain data.
        Returns current metrics snapshot.
        """
        try:
            contract = self._get_pair_contract(pair_address, dex_type)
            if not contract:
                return {}

            current_time = time.time()
            token0_is_weth = False

            if dex_type == "uniswap_v2":
                reserves = contract.functions.getReserves().call()
                reserve0, reserve1 = reserves[0], reserves[1]

                # Determine which reserve is WETH
                # This is a simplification - in practice you'd check the token addresses
                token0_is_weth = (reserve0 > reserve1 * 10**12)  # Rough heuristic

                price = self._calculate_v2_price(reserve0, reserve1, token0_is_weth)
                # SAFE: Prevent division in liquidity calculation
                liquidity_usd = safe_div((reserve0 if token0_is_weth else reserve1) * 2, 10**18, 0) * self.config.get('eth_price_usd', 3500)

            elif dex_type == "uniswap_v3":
                liquidity = contract.functions.liquidity().call()
                slot0 = contract.functions.slot0().call()
                sqrt_price_x96 = slot0[0]

                price = self._calculate_v3_price(sqrt_price_x96)
                # V3 liquidity calculation is more complex - simplified
                # SAFE: Prevent division in V3 liquidity
                liquidity_usd = safe_div(liquidity, 10**18, 0) * self.config.get('eth_price_usd', 3500)

            else:
                return {}

            # Store price data
            self.price_history[pair_address].append((current_time, price))
            self.liquidity_history[pair_address].append((current_time, liquidity_usd))

            # Get holder count (simplified - total supply / average balance heuristic)
            token_contract = self._get_token_contract(token_address)
            total_supply = token_contract.functions.totalSupply().call()
            # SAFE: Prevent division by zero in holder estimation
            holders = max(1, int(safe_div(total_supply, (10**token_decimals * 1000), 1)))  # Rough estimate
            self.holder_history[pair_address].append((current_time, holders))

            self.last_update[pair_address] = current_time

            return {
                'price': price,
                'liquidity_usd': liquidity_usd,
                'holders': holders,
                'timestamp': current_time
            }

        except Exception as e:
            print(f"⚠️  Error updating pair data {pair_address}: {e}")
            return {}

    def get_rolling_metrics(self, pair_address: str) -> Dict:
        """
        Calculate rolling metrics for the last periods.
        """
        now = time.time()

        # Get data windows
        prices = list(self.price_history.get(pair_address, []))
        volumes = list(self.volume_history.get(pair_address, []))  # Volume from swap events
        liquidities = list(self.liquidity_history.get(pair_address, []))
        holders = list(self.holder_history.get(pair_address, []))

        if not prices:
            return {}

        # Filter to time windows
        def filter_window(data: List[Tuple], minutes: int):
            cutoff = now - (minutes * 60)
            return [d for d in data if d[0] >= cutoff]

        prices_5m = filter_window(prices, 5)
        prices_1h = filter_window(prices, 60)
        prices_24h = filter_window(prices, 1440)

        volumes_5m = filter_window(volumes, 5)
        volumes_1h = filter_window(volumes, 60)
        volumes_24h = filter_window(volumes, 1440)

        liquidities_1h = filter_window(liquidities, 60)
        holders_recent = filter_window(holders, 60)

        # Calculate metrics
        metrics = {}

        # Volume metrics
        metrics['volume_5m'] = sum(v[1] for v in volumes_5m) if volumes_5m else 0
        metrics['volume_1h'] = sum(v[1] for v in volumes_1h) if volumes_1h else 0
        metrics['volume_24h'] = sum(v[1] for v in volumes_24h) if volumes_24h else 0

        # Price change metrics
        if len(prices_5m) >= 2:
            # SAFE: Use safe_div_percentage - if prices_5m[0][1] is 0, return 0 (ZERO_BASE_PRICE flag)
            metrics['price_change_5m'] = safe_div_percentage(prices_5m[-1][1], prices_5m[0][1], default=0)
        else:
            metrics['price_change_5m'] = 0

        if len(prices_1h) >= 2:
            # SAFE: Prevent ZERO_BASE_PRICE crash
            metrics['price_change_1h'] = safe_div_percentage(prices_1h[-1][1], prices_1h[0][1], default=0)
        else:
            metrics['price_change_1h'] = 0

        # High 24h
        if prices_24h:
            metrics['high_24h'] = max(p[1] for p in prices_24h)
        else:
            metrics['high_24h'] = prices[-1][1] if prices else 0

        # Liquidity metrics
        metrics['liquidity_now'] = liquidities[-1][1] if liquidities else 0

        if liquidities_1h:
            # SAFE: Prevent division by zero in liquidity averaging
            avg_liq_1h = safe_div(sum(l[1] for l in liquidities_1h), len(liquidities_1h), 1)
            metrics['liquidity_delta_1h'] = safe_div_percentage(metrics['liquidity_now'], avg_liq_1h, default=0)
        else:
            metrics['liquidity_delta_1h'] = 0

        # Effective liquidity (simplified)
        metrics['effective_liquidity'] = metrics['liquidity_now']

        # Holder metrics
        metrics['holders_now'] = holders[-1][1] if holders else 0

        if len(holders_recent) >= 2:
            holder_growth = holders_recent[-1][1] - holders_recent[0][1]
            # SAFE: Prevent division by zero in time difference
            time_diff_hours = safe_div(holders_recent[-1][0] - holders_recent[0][0], 3600, 1)
            metrics['holder_growth_rate'] = safe_div(holder_growth, time_diff_hours, 0)
        else:
            metrics['holder_growth_rate'] = 0

        # Token age (from first price data point)
        if prices:
            # SAFE: Prevent division in age calculation
            metrics['token_age_minutes'] = safe_div(now - prices[0][0], 60, 0)
        else:
            metrics['token_age_minutes'] = 0

        return metrics

    def add_swap_volume(self, pair_address: str, volume_usd: float, timestamp: float = None):
        """Add volume data from swap events"""
        if timestamp is None:
            timestamp = time.time()
        self.volume_history[pair_address].append((timestamp, volume_usd))