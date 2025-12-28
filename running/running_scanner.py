"""
Running Scanner - Main orchestration for post-launch rally detection

This is the entry point for the running token scanner.
It coordinates:
- Token eligibility checking
- Score calculation
- Cooldown management
- Alert dispatch

Usage in main.py:
    running_scanner = RunningScanner()
    result = running_scanner.process_token(token_data, score_data, chain_config)
"""
from typing import Dict, Optional
from .running_config import get_running_config, is_token_eligible, get_score_thresholds
from .running_score_engine import RunningScoreEngine
from .running_cooldown import RunningCooldown
from .running_alert import RunningAlert


class RunningScanner:
    """
    Main orchestration class for running token scanner.
    
    Coordinates eligibility checking, scoring, cooldown, and alerting.
    """
    
    def __init__(self):
        self.config = get_running_config()
        self.score_engine = RunningScoreEngine()
        self.cooldown = RunningCooldown()
        self.alert = RunningAlert()
        self.thresholds = get_score_thresholds()
    
    def is_enabled(self) -> bool:
        """Check if running scanner is enabled."""
        return self.config.get("enabled", False)
    
    def process_token(self, 
                       token_data: Dict, 
                       base_score_data: Dict,
                       chain_config: Dict = None) -> Dict:
        """
        Process a token through the running scanner pipeline.
        
        Args:
            token_data: Token analysis data
            base_score_data: Score data from main TokenScorer
            chain_config: Chain-specific configuration
            
        Returns:
            Dict with:
            - processed: bool (whether token was processed)
            - eligible: bool
            - alert_sent: bool
            - running_score: int (if processed)
            - alert_level: str (if processed)
            - skip_reason: str (if skipped)
        """
        result = {
            "processed": False,
            "eligible": False,
            "alert_sent": False,
            "running_score": 0,
            "alert_level": None,
            "skip_reason": None
        }
        
        # Get token address
        token_address = token_data.get("address", token_data.get("token_address", ""))
        if not token_address:
            result["skip_reason"] = "No token address"
            return result
        
        token_address = token_address.lower()
        chain_prefix = token_data.get("chain_prefix", "[UNKNOWN]")
        
        # 1. Check eligibility (age, market cap, liquidity filters)
        eligibility = is_token_eligible(token_data, chain_config)
        if not eligibility["eligible"]:
            result["skip_reason"] = eligibility["reason"]
            return result
        
        result["eligible"] = True
        
        # 2. Check cooldown
        if self.cooldown.is_on_cooldown(token_address):
            remaining = self.cooldown.get_remaining_cooldown(token_address)
            result["skip_reason"] = f"On cooldown ({remaining}m remaining)"
            return result
        
        # 3. Calculate running score
        # Build score inputs from token_data and base_score_data
        momentum_data = {
            "momentum_confirmed": token_data.get("momentum_confirmed", 
                                                   base_score_data.get("momentum_confirmed", False)),
            "momentum_score": token_data.get("momentum_score", 0)
        }
        
        volume_data = {
            "volume_24h": token_data.get("volume_24h", 0),
            "average_volume": token_data.get("average_volume", 0),
            "volume_spike": token_data.get("volume_spike", False)
        }
        
        liquidity_data = {
            "initial_liquidity": token_data.get("initial_liquidity", 
                                                  token_data.get("liquidity_usd", 0)),
            "current_liquidity": token_data.get("liquidity_usd", 0),
            "liquidity_growing": token_data.get("liquidity_growing", False)
        }
        
        holder_data = {
            "top10_percent": token_data.get("top10_holders_percent", 0),
            "holder_risks": [],
            "dev_flag": token_data.get("dev_activity_flag", 
                                        base_score_data.get("dev_activity_flag", "SAFE"))
        }
        
        # Add holder risks
        if token_data.get("fake_pump_suspected", base_score_data.get("fake_pump_suspected", False)):
            holder_data["holder_risks"].append("Fake pump suspected")
        if token_data.get("mev_pattern_detected", base_score_data.get("mev_pattern_detected", False)):
            holder_data["holder_risks"].append("MEV detected")
        
        base_score = base_score_data.get("score", 0)
        
        score_result = self.score_engine.calculate_running_score(
            base_score=base_score,
            momentum_data=momentum_data,
            volume_data=volume_data,
            liquidity_data=liquidity_data,
            holder_data=holder_data
        )
        
        result["running_score"] = score_result["running_score"]
        result["alert_level"] = score_result["alert_level"]
        result["processed"] = True
        
        # 4. Check if meets alert threshold
        if not score_result["meets_threshold"]:
            result["skip_reason"] = f"Score {score_result['running_score']} below threshold"
            return result
        
        # 5. Send alert
        print(f"[RUNNING] {chain_prefix} Score: {score_result['running_score']}/{score_result['max_possible']} ({score_result['alert_level']})")
        
        alert_sent = self.alert.send_running_alert(token_data, score_result)
        result["alert_sent"] = alert_sent
        
        if alert_sent:
            # Mark cooldown
            self.cooldown.mark_alerted(token_address, {
                "running_score": score_result["running_score"],
                "alert_level": score_result["alert_level"],
                "chain": token_data.get("chain", "unknown"),
                "name": token_data.get("name", "UNKNOWN"),
                "symbol": token_data.get("symbol", "???")
            })
            
            print(f"[RUNNING] {chain_prefix} Alert sent for {token_data.get('name', 'UNKNOWN')}")
        
        return result
    
    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            "enabled": self.is_enabled(),
            "cooldown_stats": self.cooldown.get_stats(),
            "alert_stats": self.alert.get_stats(),
            "thresholds": self.thresholds
        }
    
    def get_score_engine(self) -> RunningScoreEngine:
        """Get the score engine instance."""
        return self.score_engine
    
    def get_cooldown(self) -> RunningCooldown:
        """Get the cooldown instance."""
        return self.cooldown
    
    def get_alert(self) -> RunningAlert:
        """Get the alert instance."""
        return self.alert
