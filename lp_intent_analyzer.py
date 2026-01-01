"""
LP Intent-Based Risk Analyzer
Detects liquidity rugpull intent through behavioral analysis.

Core Metrics:
1. LP Control Risk - Who owns the LP?
2. Economic Incentive - Is rugpull profitable?
3. LP Behavior - How is LP changing?
4. Market Divergence - LP vs Volume anomalies
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import time


@dataclass
class LPSnapshot:
    """Single liquidity pool snapshot at a point in time."""
    timestamp: float
    lp_usd: float
    volume_usd: float
    price: float
    marketcap: float
    
    
class LPIntentAnalyzer:
    """
    Analyzes liquidity pool behavior to detect rugpull intent.
    
    Risk Score: 0-100
    - 0-25: Safe
    - 25-50: Caution
    - 50-70: Danger
    - 70-100: Critical (EXIT)
    """
    
    def __init__(self, chain_name: str):
        self.chain_name = chain_name.lower()
        self.lp_history: Dict[str, List[LPSnapshot]] = {}
        
    def calculate_risk(self, pair_data: Dict) -> Dict:
        """
        Calculate comprehensive LP intent risk score.
        
        Args:
            pair_data: DexScreener pair data with LP info
            
        Returns:
            {
                'risk_score': 0-100,
                'risk_level': 'SAFE|CAUTION|DANGER|CRITICAL',
                'details': [...],
                'components': {
                    'control_risk': 0-75,
                    'economic_risk': 0-45,
                    'behavior_risk': 0-60,
                    'divergence_risk': 0-30
                }
            }
        """
        result = {
            'risk_score': 0,
            'risk_level': 'UNKNOWN',
            'details': [],
            'components': {}
        }
        
        try:
            # Extract data
            token_address = pair_data.get('baseToken', {}).get('address', '')
            lp_usd = float(pair_data.get('liquidity', {}).get('usd', 0))
            volume_24h = float(pair_data.get('volume', {}).get('h24', 0))
            marketcap = float(pair_data.get('fdv', 0))
            price = float(pair_data.get('priceUsd', 0))
            pair_created_at = pair_data.get('pairCreatedAt', 0)
            
            # Store snapshot
            snapshot = LPSnapshot(
                timestamp=time.time(),
                lp_usd=lp_usd,
                volume_usd=volume_24h,
                price=price,
                marketcap=marketcap
            )
            
            if token_address not in self.lp_history:
                self.lp_history[token_address] = []
            self.lp_history[token_address].append(snapshot)
            
            # Keep only last 120 snapshots (1 hour at 30s intervals)
            if len(self.lp_history[token_address]) > 120:
                self.lp_history[token_address] = self.lp_history[token_address][-120:]
            
            # Calculate risk components
            control_risk = self._calculate_control_risk(pair_data)
            economic_risk = self._calculate_economic_risk(lp_usd, marketcap)
            behavior_risk = self._calculate_behavior_risk(token_address, lp_usd)
            divergence_risk = self._calculate_divergence_risk(token_address)
            
            result['components'] = {
                'control_risk': control_risk,
                'economic_risk': economic_risk,
                'behavior_risk': behavior_risk,
                'divergence_risk': divergence_risk
            }
            
            # Aggregate risk score
            total_risk = control_risk + economic_risk + behavior_risk + divergence_risk
            
            # Time discount (reduce risk for established tokens)
            token_age_minutes = (time.time() - (pair_created_at / 1000)) / 60 if pair_created_at else 0
            time_discount = min(token_age_minutes / 10, 20)
            total_risk = max(0, total_risk - time_discount)
            
            result['risk_score'] = min(100, total_risk)
            result['risk_level'] = self._determine_risk_level(result['risk_score'])
            
            # Generate details
            result['details'].append(f"Total Risk: {result['risk_score']:.0f}/100 ({result['risk_level']})")
            result['details'].append(f"Control: {control_risk:.0f}, Economic: {economic_risk:.0f}, Behavior: {behavior_risk:.0f}, Divergence: {divergence_risk:.0f}")
            
            if token_age_minutes > 0:
                result['details'].append(f"Token Age: {token_age_minutes:.1f} min (Discount: -{time_discount:.0f})")
            
        except Exception as e:
            result['details'].append(f"⚠️ Error calculating risk: {str(e)}")
        
        return result
    
    def _calculate_control_risk(self, pair_data: Dict) -> float:
        """
        Calculate LP control risk (0-75).
        
        Checks:
        - Is LP owned by single wallet? (+20)
        - Is LP owner the deployer? (+25)
        - Has LP been transferred recently? (+30)
        """
        risk = 0
        
        # Note: DexScreener doesn't provide LP holder info directly
        # This would require additional on-chain query or API
        # For now, we assume moderate risk if data unavailable
        
        # Placeholder: In production, query LP token holders
        # For Solana: Check Raydium LP token holders
        # For EVM: Check Uniswap V2 LP token holders
        
        # Default assumption: Unknown = moderate risk
        risk += 10  # Unknown LP ownership = small penalty
        
        return risk
    
    def _calculate_economic_risk(self, lp_usd: float, marketcap: float) -> float:
        """
        Calculate economic incentive risk (0-45).
        
        Checks:
        - LP/MarketCap ratio too low? (+20)
        - LP ratio velocity declining? (+25)
        """
        risk = 0
        
        if marketcap > 0:
            lp_ratio = lp_usd / marketcap
            
            # Low LP ratio = easier to rug
            if lp_ratio < 0.05:
                risk += 20
                
            elif lp_ratio < 0.1:
                risk += 10
        else:
            # No marketcap data
            risk += 5
        
        # TODO: Calculate velocity (requires history)
        # if lp_ratio_velocity < -5% per 10min: risk += 25
        
        return risk
    
    def _calculate_behavior_risk(self, token_address: str, current_lp: float) -> float:
        """
        Calculate LP behavior risk (0-60).
        
        Checks:
        - LP drop in last 5 minutes > 5%? (+40)
        - Stepwise drain pattern detected? (+20)
        """
        risk = 0
        
        history = self.lp_history.get(token_address, [])
        
        if len(history) < 2:
            # Not enough data yet
            return 0
        
        # Calculate LP delta over last 5 minutes (10 snapshots at 30s interval)
        if len(history) >= 10:
            lp_5m_ago = history[-10].lp_usd
            lp_now = current_lp
            
            if lp_5m_ago > 0:
                lp_drop_pct = ((lp_5m_ago - lp_now) / lp_5m_ago) * 100
                
                if lp_drop_pct > 5:
                    risk += 40
                    
                elif lp_drop_pct > 3:
                    risk += 20
        
        # Detect stepwise pattern (gradual drain)
        if len(history) >= 6:
            # Check if LP consistently declining
            declining_count = 0
            for i in range(len(history) - 5, len(history)):
                if history[i].lp_usd < history[i-1].lp_usd:
                    declining_count += 1
            
            if declining_count >= 4:  # 4 out of 5 declining
                risk += 20
        
        return risk
    
    def _calculate_divergence_risk(self, token_address: str) -> float:
        """
        Calculate market divergence risk (0-30).
        
        Checks:
        - LP decreasing while volume increasing? (+30)
        """
        risk = 0
        
        history = self.lp_history.get(token_address, [])
        
        if len(history) < 6:
            return 0
        
        # Compare last 3 snapshots to previous 3
        recent_3 = history[-3:]
        previous_3 = history[-6:-3]
        
        avg_lp_recent = sum(s.lp_usd for s in recent_3) / 3
        avg_lp_previous = sum(s.lp_usd for s in previous_3) / 3
        
        avg_vol_recent = sum(s.volume_usd for s in recent_3) / 3
        avg_vol_previous = sum(s.volume_usd for s in previous_3) / 3
        
        lp_decreasing = avg_lp_recent < avg_lp_previous * 0.95  # 5% drop
        vol_increasing = avg_vol_recent > avg_vol_previous * 1.2  # 20% increase
        
        if lp_decreasing and vol_increasing:
            # This is a strong rugpull signal
            risk += 30
        
        return risk
    
    def _determine_risk_level(self, score: float) -> str:
        """Convert risk score to risk level."""
        if score < 25:
            return 'SAFE'
        elif score < 50:
            return 'CAUTION'
        elif score < 70:
            return 'DANGER'
        else:
            return 'CRITICAL'
    
    def get_lp_delta(self, token_address: str, minutes: int = 5) -> Optional[float]:
        """
        Get LP change percentage over specified time window.
        
        Returns:
            Percentage change (positive = increase, negative = decrease)
            None if insufficient data
        """
        history = self.lp_history.get(token_address, [])
        
        if len(history) < 2:
            return None
        
        # Calculate number of snapshots (30s interval)
        snapshots_needed = (minutes * 60) // 30
        
        if len(history) < snapshots_needed:
            snapshots_needed = len(history)
        
        lp_past = history[-snapshots_needed].lp_usd
        lp_now = history[-1].lp_usd
        
        if lp_past == 0:
            return None
        
        delta_pct = ((lp_now - lp_past) / lp_past) * 100
        return delta_pct
    
    def should_emergency_exit(self, token_address: str) -> tuple[bool, str]:
        """
        Check if emergency exit is required.
        
        Returns:
            (should_exit: bool, reason: str)
        """
        # Check LP drop
        lp_delta_5m = self.get_lp_delta(token_address, minutes=5)
        
        if lp_delta_5m is not None and lp_delta_5m < -5:
            return (True, f"LP dropped {abs(lp_delta_5m):.1f}% in 5 minutes")
        
        # Check risk score
        history = self.lp_history.get(token_address, [])
        if not history:
            return (False, "")
        
        # Get latest snapshot for risk calculation
        # (In production, this would use full pair_data)
        # For now, we only check stored risk if available
        
        return (False, "")
    
    def clear_history(self, token_address: str):
        """Clear LP history for a token (e.g., after exit)."""
        if token_address in self.lp_history:
            del self.lp_history[token_address]
