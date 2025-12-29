import time
from enum import Enum

class HeatState(Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"

class MarketHeatEngine:
    """
    Tracks market activity to gate RPC calls during low-volume periods.
    """
    def __init__(self, decay_rate: float = 0.5):
        self.heat_score = 50  # Start neutral
        self.last_update = time.time()
        self.decay_rate = decay_rate # Points lost per minute
        
    _instances = {}
    
    @classmethod
    def get_instance(cls, chain: str) -> 'MarketHeatEngine':
        if chain not in cls._instances:
            cls._instances[chain] = cls()
        return cls._instances[chain]
        
    def record_activity(self, weight: int = 10):
        """Record market activity (new pair, trade, etc)"""
        self._update_decay()
        self.heat_score = min(100, self.heat_score + weight)
        
    def _update_decay(self):
        now = time.time()
        elapsed_minutes = (now - self.last_update) / 60
        decay_amount = elapsed_minutes * self.decay_rate * 5 # 5 points per 10 mins approx if rate is 1
        self.heat_score = max(0, self.heat_score - decay_amount)
        self.last_update = now
        
    @property
    def status(self) -> HeatState:
        self._update_decay()
        if self.heat_score < 30:
            return HeatState.COLD
        elif self.heat_score < 70:
            return HeatState.WARM
        else:
            return HeatState.HOT
            
    def is_cold(self) -> bool:
        return self.status == HeatState.COLD

    def get_status_str(self) -> str:
        s = self.status
        return f"{s.value} ({int(self.heat_score)}%)"

    def record_shortlisted_candidate(self):
        """Record a high-potential candidate detection"""
        self.record_activity(weight=5)

    def record_alert_triggered(self):
        """Record a successful alert generation"""
        self.record_activity(weight=15)

    def set_liquidity_spike_flag(self):
        """Record a massive liquidity injection event"""
        self.record_activity(weight=30)
