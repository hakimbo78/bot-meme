"""
Market Heat Engine for Adaptive Scan Speed

Computes market heat score using CU-cheap signals to dynamically adjust scan intervals.
"""
import time
from typing import Dict, List
from collections import deque
from dataclasses import dataclass


@dataclass
class HeatMetrics:
    """Container for heat calculation metrics"""
    factory_logs_5m: int = 0
    shortlisted_5m: int = 0
    alerts_10m: int = 0
    liquidity_spike_flag: int = 0


class MarketHeatEngine:
    """
    Computes market heat score for adaptive scanning.

    Heat score formula:
    heat_score = (factory_logs_5m * 10) + (shortlisted_5m * 20) + (alerts_10m * 30) + (liquidity_spike_flag * 20)
    Clamped to 0-100.
    """

    def __init__(self, chain_name: str):
        self.chain_name = chain_name

        # Rolling windows for metrics (timestamps)
        self.factory_logs_window: deque = deque(maxlen=1000)  # Last 5 min worth
        self.shortlisted_window: deque = deque(maxlen=1000)   # Last 5 min worth
        self.alerts_window: deque = deque(maxlen=1000)        # Last 10 min worth

        # Cached liquidity spike flag (resets periodically)
        self.liquidity_spike_flag = 0
        self.spike_reset_time = time.time() + 300  # Reset every 5 min

        # Heat zones
        self.HEAT_ZONES = {
            'COLD': (0, 20),
            'NORMAL': (21, 50),
            'HOT': (51, 80),
            'FRENZY': (81, 100)
        }

        # Scan intervals by chain and zone
        self.SCAN_INTERVALS = {
            'base': {
                'COLD': 60,
                'NORMAL': 25,
                'HOT': 12,
                'FRENZY': 6
            },
            'ethereum': {
                'COLD': 120,
                'NORMAL': 52,
                'HOT': 30,
                'FRENZY': 20
            }
        }

        # Safety guardrails
        self.MIN_INTERVAL = 5
        self.FRENZY_MAX_DURATION = 300  # 5 minutes
        self.frenzy_start_time = None

    def record_factory_log(self):
        """Record a new factory log event"""
        self.factory_logs_window.append(time.time())

    def record_shortlisted_candidate(self):
        """Record a shortlisted candidate"""
        self.shortlisted_window.append(time.time())

    def record_alert_triggered(self):
        """Record an alert being triggered"""
        self.alerts_window.append(time.time())

    def set_liquidity_spike_flag(self):
        """Set liquidity spike flag (cached, no eth_call)"""
        self.liquidity_spike_flag = 1
        self.spike_reset_time = time.time() + 300  # Reset in 5 min

    def _cleanup_old_events(self):
        """Remove events older than their respective windows"""
        now = time.time()

        # Clean factory logs (5 min window)
        while self.factory_logs_window and now - self.factory_logs_window[0] > 300:
            self.factory_logs_window.popleft()

        # Clean shortlisted (5 min window)
        while self.shortlisted_window and now - self.shortlisted_window[0] > 300:
            self.shortlisted_window.popleft()

        # Clean alerts (10 min window)
        while self.alerts_window and now - self.alerts_window[0] > 600:
            self.alerts_window.popleft()

        # Reset liquidity spike flag if expired
        if time.time() > self.spike_reset_time:
            self.liquidity_spike_flag = 0

    def _calculate_heat_score(self) -> int:
        """Calculate current heat score (0-100)"""
        self._cleanup_old_events()

        metrics = HeatMetrics(
            factory_logs_5m=len(self.factory_logs_window),
            shortlisted_5m=len(self.shortlisted_window),
            alerts_10m=len(self.alerts_window),
            liquidity_spike_flag=self.liquidity_spike_flag
        )

        # Heat score formula
        heat_score = (
            metrics.factory_logs_5m * 10 +
            metrics.shortlisted_5m * 20 +
            metrics.alerts_10m * 30 +
            metrics.liquidity_spike_flag * 20
        )

        # Clamp to 0-100
        return max(0, min(100, heat_score))

    def get_heat_zone(self) -> str:
        """Get current heat zone"""
        score = self._calculate_heat_score()

        for zone, (min_val, max_val) in self.HEAT_ZONES.items():
            if min_val <= score <= max_val:
                return zone

        return 'NORMAL'  # Fallback

    def get_adaptive_scan_interval(self) -> int:
        """
        Get adaptive scan interval based on current heat.

        Includes safety guardrails:
        - Minimum 5s interval
        - Frenzy max 5 minutes duration
        - Cooldown to NORMAL when heat < 50
        """
        zone = self.get_heat_zone()
        score = self._calculate_heat_score()

        # Get base interval for chain and zone
        chain_intervals = self.SCAN_INTERVALS.get(self.chain_name.lower(), self.SCAN_INTERVALS['base'])
        interval = chain_intervals.get(zone, chain_intervals['NORMAL'])

        # Safety: Minimum interval
        interval = max(interval, self.MIN_INTERVAL)

        # Frenzy duration limit
        if zone == 'FRENZY':
            if self.frenzy_start_time is None:
                self.frenzy_start_time = time.time()
            elif time.time() - self.frenzy_start_time > self.FRENZY_MAX_DURATION:
                # Force cooldown to NORMAL
                interval = chain_intervals['NORMAL']
                zone = 'NORMAL'
        else:
            # Reset frenzy timer when not in frenzy
            self.frenzy_start_time = None

        # Cooldown: If heat drops below 50, ensure we're not stuck in HOT/FRENZY
        if score < 50 and zone in ['HOT', 'FRENZY']:
            interval = chain_intervals['NORMAL']
            zone = 'NORMAL'

        return interval

    def get_heat_status(self) -> Dict:
        """Get current heat status for logging"""
        score = self._calculate_heat_score()
        zone = self.get_heat_zone()
        interval = self.get_adaptive_scan_interval()

        return {
            'score': score,
            'zone': zone,
            'interval': interval,
            'metrics': {
                'factory_logs_5m': len(self.factory_logs_window),
                'shortlisted_5m': len(self.shortlisted_window),
                'alerts_10m': len(self.alerts_window),
                'liquidity_spike': bool(self.liquidity_spike_flag)
            }
        }