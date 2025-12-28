"""
Dashboard State Manager
Aggregates token data from all bot modes for dashboard display.

Read-only - no modifications to bot state.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from dashboard_config import get_dashboard_config, get_cooldown_path


class DashboardState:
    """
    Aggregates token data from all bot modes for dashboard display.
    
    Read-only - no modifications to bot state.
    
    Modes tracked:
    - SNIPER: High-risk early tokens
    - TRADE: Strong signals
    - TRADE-EARLY: Pending momentum confirmation
    - RUNNING: Post-launch rally detection
    """
    
    def __init__(self):
        self.config = get_dashboard_config()
        self.sniper_tokens: Dict = {}
        self.running_tokens: Dict = {}
        self.trade_early_tokens: Dict = {}
        self.trade_tokens: Dict = {}
        self.last_refresh: Optional[float] = None
        self.refresh_count: int = 0
    
    def refresh(self) -> Dict:
        """
        Reload all token data from persistent files.
        
        Returns:
            Dict with refresh status and counts
        """
        results = {
            "success": True,
            "sniper_count": 0,
            "running_count": 0,
            "trade_early_count": 0,
            "trade_count": 0,
            "errors": []
        }
        
        # Load sniper tokens
        sniper_path = get_cooldown_path("sniper")
        if sniper_path and sniper_path.exists():
            try:
                with open(sniper_path, 'r') as f:
                    data = json.load(f)
                    self.sniper_tokens = data.get("tokens", {})
                    results["sniper_count"] = len(self.sniper_tokens)
            except Exception as e:
                results["errors"].append(f"Sniper load error: {e}")
        
        # Load running tokens
        running_path = get_cooldown_path("running")
        if running_path and running_path.exists():
            try:
                with open(running_path, 'r') as f:
                    data = json.load(f)
                    self.running_tokens = data.get("tokens", {})
                    results["running_count"] = len(self.running_tokens)
            except Exception as e:
                results["errors"].append(f"Running load error: {e}")
        
        # Load trade-early tokens
        trade_early_path = get_cooldown_path("trade_early")
        if trade_early_path and trade_early_path.exists():
            try:
                with open(trade_early_path, 'r') as f:
                    data = json.load(f)
                    self.trade_early_tokens = data.get("tokens", {})
                    results["trade_early_count"] = len(self.trade_early_tokens)
            except Exception as e:
                results["errors"].append(f"Trade-early load error: {e}")
        
        # Update refresh timestamp
        self.last_refresh = time.time()
        self.refresh_count += 1
        
        if results["errors"]:
            results["success"] = False
        
        return results
    
    def get_all_tokens(self, 
                       chain_filter: List[str] = None,
                       mode_filter: str = None,
                       min_score: int = 0,
                       min_liquidity: float = 0) -> List[Dict]:
        """
        Get filtered list of all tokens.
        
        Args:
            chain_filter: List of chain names to include (None = all)
            mode_filter: Single mode to filter (None = all)
            min_score: Minimum score threshold
            min_liquidity: Minimum liquidity threshold
            
        Returns:
            List of token dicts with mode and all details
        """
        all_tokens = []
        
        # Add sniper tokens
        if mode_filter is None or mode_filter.lower() == "sniper":
            for addr, data in self.sniper_tokens.items():
                token = self._normalize_token(addr, data, "sniper")
                if self._passes_filters(token, chain_filter, min_score, min_liquidity):
                    all_tokens.append(token)
        
        # Add running tokens
        if mode_filter is None or mode_filter.lower() == "running":
            for addr, data in self.running_tokens.items():
                token = self._normalize_token(addr, data, "running")
                if self._passes_filters(token, chain_filter, min_score, min_liquidity):
                    all_tokens.append(token)
        
        # Add trade-early tokens
        if mode_filter is None or mode_filter.lower() in ["trade_early", "trade-early"]:
            for addr, data in self.trade_early_tokens.items():
                token = self._normalize_token(addr, data, "trade_early")
                if self._passes_filters(token, chain_filter, min_score, min_liquidity):
                    all_tokens.append(token)
        
        # Add trade tokens (from trade-early that were upgraded)
        if mode_filter is None or mode_filter.lower() == "trade":
            for addr, data in self.trade_early_tokens.items():
                if data.get("upgraded", False):
                    token = self._normalize_token(addr, data, "trade")
                    if self._passes_filters(token, chain_filter, min_score, min_liquidity):
                        all_tokens.append(token)
        
        # Sort by timestamp (newest first)
        all_tokens.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return all_tokens
    
    def _normalize_token(self, address: str, data: Dict, mode: str) -> Dict:
        """Normalize token data from different sources to unified format."""
        timestamp = data.get("timestamp", 0)
        
        # Calculate age
        age_seconds = time.time() - timestamp if timestamp else 0
        age_display = self._format_age(age_seconds)
        
        return {
            "address": address,
            "mode": mode,
            "name": data.get("name", data.get("token_name", "Unknown")),
            "symbol": data.get("symbol", data.get("token_symbol", "???")),
            "chain": data.get("chain", "unknown"),
            "score": data.get("score", data.get("sniper_score", data.get("running_score", 0))),
            "liquidity_usd": data.get("liquidity_usd", data.get("liquidity", 0)),
            "timestamp": timestamp,
            "alert_time": data.get("sniped_at", data.get("alerted_at", "")),
            "age_display": age_display,
            "age_seconds": age_seconds,
            
            # Mode-specific fields
            "sniper_score": data.get("sniper_score", 0),
            "running_score": data.get("running_score", 0),
            "base_score": data.get("base_score", data.get("score", 0)),
            
            # Status fields
            "momentum_confirmed": data.get("momentum_confirmed", False),
            "phase": data.get("phase", data.get("market_phase", "unknown")),
            "holder_risk": data.get("holder_risk", data.get("top10_percent", 0)),
            "upgraded": data.get("upgraded", False),
            "killswitch_triggered": data.get("killswitch_triggered", False),
            
            # Operator protocol (for sniper)
            "operator_protocol": data.get("operator_protocol", {}),
            
            # Warnings
            "warnings": data.get("warnings", []),
            "high_risk": data.get("high_risk", False),
            "high_concentration": data.get("high_concentration", False),
            
            # Raw data for detail view
            "_raw": data
        }
    
    def _passes_filters(self, token: Dict, 
                        chain_filter: List[str],
                        min_score: int,
                        min_liquidity: float) -> bool:
        """Check if token passes all filters."""
        # Chain filter
        if chain_filter and token.get("chain", "").lower() not in [c.lower() for c in chain_filter]:
            return False
        
        # Score filter
        if token.get("score", 0) < min_score:
            return False
        
        # Liquidity filter
        if token.get("liquidity_usd", 0) < min_liquidity:
            return False
        
        return True
    
    def _format_age(self, seconds: float) -> str:
        """Format age in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h"
        else:
            return f"{int(seconds / 86400)}d"
    
    def get_token_details(self, token_address: str) -> Optional[Dict]:
        """
        Get detailed info for a specific token.
        
        Args:
            token_address: Token contract address
            
        Returns:
            Token dict with all details, or None if not found
        """
        address = token_address.lower()
        
        # Check all sources
        if address in self.sniper_tokens:
            return self._normalize_token(address, self.sniper_tokens[address], "sniper")
        
        if address in self.running_tokens:
            return self._normalize_token(address, self.running_tokens[address], "running")
        
        if address in self.trade_early_tokens:
            data = self.trade_early_tokens[address]
            mode = "trade" if data.get("upgraded") else "trade_early"
            return self._normalize_token(address, data, mode)
        
        return None
    
    def get_stats(self) -> Dict:
        """Get dashboard statistics."""
        return {
            "total_tokens": (
                len(self.sniper_tokens) + 
                len(self.running_tokens) + 
                len(self.trade_early_tokens)
            ),
            "sniper_count": len(self.sniper_tokens),
            "running_count": len(self.running_tokens),
            "trade_early_count": len(self.trade_early_tokens),
            "last_refresh": self.last_refresh,
            "last_refresh_formatted": (
                datetime.fromtimestamp(self.last_refresh).strftime("%H:%M:%S")
                if self.last_refresh else "Never"
            ),
            "refresh_count": self.refresh_count
        }
    
    def get_chains(self) -> List[str]:
        """Get unique list of chains from all tokens."""
        chains = set()
        
        for tokens in [self.sniper_tokens, self.running_tokens, self.trade_early_tokens]:
            for data in tokens.values():
                chain = data.get("chain", "")
                if chain:
                    chains.add(chain.lower())
        
        return sorted(list(chains))


# Singleton instance
_dashboard_state: Optional[DashboardState] = None


def get_dashboard_state() -> DashboardState:
    """Get or create dashboard state singleton."""
    global _dashboard_state
    if _dashboard_state is None:
        _dashboard_state = DashboardState()
    return _dashboard_state
