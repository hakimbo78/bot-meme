"""
Trigger Engine for Secondary Market Scanner
Evaluates market conditions against trigger thresholds
"""
from typing import Dict, List, Set


class TriggerEngine:
    """
    Evaluates market metrics against trigger conditions.
    Returns active triggers and combined signal.
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_volume_5m = self.config.get('min_volume_5m', 20000)
        self.min_liquidity = self.config.get('min_liquidity', 50000)
        self.min_holders = self.config.get('min_holders', 200)
        self.min_risk_score = self.config.get('min_risk_score', 70)

    def evaluate_triggers(self, metrics: Dict, risk_score: int = 0) -> Dict:
        """
        Evaluate all triggers against metrics.
        Returns dict with trigger states and combined signal.
        """
        triggers = {}

        # Volume Spike Trigger
        volume_5m = metrics.get('volume_5m', 0)
        volume_1h_avg = metrics.get('volume_1h', 0) / 60 * 5  # Rough 5m average from 1h
        if volume_1h_avg > 0:
            volume_ratio = volume_5m / volume_1h_avg
        else:
            volume_ratio = float('inf') if volume_5m > 0 else 0

        triggers['volume_spike'] = (
            volume_ratio >= 5 and volume_5m >= self.min_volume_5m
        )

        # Liquidity Growth Trigger
        liquidity_delta = metrics.get('liquidity_delta_1h', 0)
        effective_liq = metrics.get('effective_liquidity', 0)
        triggers['liquidity_growth'] = (
            liquidity_delta >= 30 and effective_liq >= self.min_liquidity
        )

        # Price Breakout Trigger
        price_change_1h = metrics.get('price_change_1h', 0)
        high_24h = metrics.get('high_24h', 0)
        current_price = metrics.get('price', 0)

        price_breakout = False
        if high_24h > 0:
            price_ratio = current_price / high_24h
            price_breakout = price_ratio >= 1.02
        if price_change_1h >= 25:
            price_breakout = True

        triggers['price_breakout'] = price_breakout

        # Holder Acceleration Trigger
        holder_growth_rate = metrics.get('holder_growth_rate', 0)
        holders_now = metrics.get('holders_now', 0)
        triggers['holder_acceleration'] = (
            holder_growth_rate >= 3 and holders_now >= self.min_holders
        )

        # Count active triggers
        active_triggers = [k for k, v in triggers.items() if v]
        trigger_count = len(active_triggers)

        # Combined signal
        secondary_signal = (
            trigger_count >= 2 and risk_score >= self.min_risk_score
        )

        # Retroactive momentum detection
        token_age = metrics.get('token_age_minutes', 0)
        volume_1h = metrics.get('volume_1h', 0)
        price_change_1h = metrics.get('price_change_1h', 0)

        momentum_type = "normal"
        if (token_age >= 60 and volume_1h >= 100000 and price_change_1h >= 30):
            momentum_type = "retroactive"

        return {
            'triggers': triggers,
            'active_triggers': active_triggers,
            'trigger_count': trigger_count,
            'secondary_signal': secondary_signal,
            'momentum_type': momentum_type,
            'risk_score_threshold': risk_score >= self.min_risk_score
        }

    def get_trigger_icons(self, active_triggers: List[str]) -> str:
        """Get dashboard trigger icons for active triggers"""
        icons = {
            'volume_spike': '📈',
            'liquidity_growth': '💰',
            'price_breakout': '🚀',
            'holder_acceleration': '👥'
        }

        return ''.join(icons.get(t, '') for t in active_triggers)

    def format_trigger_list(self, active_triggers: List[str]) -> str:
        """Format active triggers for alerts"""
        names = {
            'volume_spike': 'Volume',
            'liquidity_growth': 'Liquidity',
            'price_breakout': 'Price',
            'holder_acceleration': 'Holders'
        }

        return ', '.join(names.get(t, t) for t in active_triggers)