"""
Sniper Trigger - Evaluates ALL conditions before triggering sniper alert

This module implements the strict trigger logic for sniper mode.
ALL conditions must be true to trigger a sniper alert.
If ANY fails: downgrade to normal TRADE alert.

Trigger Conditions (ALL must be true):
- base_score >= 75
- liquidity >= 2x chain min_liquidity_usd
- momentum.confirmed == True
- fake_pump == False
- mev_detected == False
- phase in [LAUNCH, EARLY_GROWTH]
- token age <= 3 minutes

All log messages prefixed with [SNIPER].
"""
from typing import Dict
from .sniper_config import get_sniper_config


class SniperTrigger:
    """
    Sniper Trigger - evaluates ALL conditions before allowing sniper alert.
    
    If ANY condition fails, the token is downgraded to a normal TRADE alert.
    """
    
    def __init__(self):
        self.config = get_sniper_config()
    
    def evaluate(self,
                 token_data: Dict,
                 score_data: Dict,
                 momentum: Dict,
                 tx_analysis: Dict,
                 chain_config: Dict) -> Dict:
        """
        Evaluate all sniper trigger conditions.
        
        Args:
            token_data: Token analysis data from analyzer
            score_data: Score data from TokenScorer
            momentum: Momentum data from MomentumTracker
            tx_analysis: Transaction analysis from TransactionAnalyzer
            chain_config: Chain-specific configuration
            
        Returns:
            Dict with:
            - trigger_sniper: bool (True if ALL conditions pass)
            - downgrade_to_trade: bool (True if should downgrade)
            - downgrade_reason: str (reason for downgrade)
            - failed_conditions: list (conditions that failed)
            - passed_conditions: list (conditions that passed)
            - condition_details: dict (detailed check results)
        """
        failed = []
        passed = []
        details = {}
        
        # Get config values
        min_base_score = self.config.get('trigger_base_score_min', 75)
        liquidity_multiplier = self.config.get('trigger_liquidity_multiplier', 2.0)
        max_age = self.config.get('max_age_minutes', 3)
        allowed_phases = self.config.get('trigger_allowed_phases', ['launch', 'early_growth'])
        
        # Get chain min liquidity
        chain_min_liq = chain_config.get('min_liquidity_usd', 5000)
        required_liquidity = chain_min_liq * liquidity_multiplier
        
        # 1. Base Score Check
        base_score = score_data.get('score', 0)
        details['base_score'] = {'value': base_score, 'required': min_base_score}
        if base_score >= min_base_score:
            passed.append(f'Base Score: {base_score} >= {min_base_score}')
        else:
            failed.append(f'Base Score: {base_score} < {min_base_score}')
            print(f"[SNIPER] FAIL: Base score {base_score} < {min_base_score}")
        
        # 2. Liquidity Check (>= 2x chain min)
        liquidity = token_data.get('liquidity_usd', 0)
        details['liquidity'] = {
            'value': liquidity, 
            'required': required_liquidity,
            'multiplier': liquidity_multiplier
        }
        if liquidity >= required_liquidity:
            passed.append(f'Liquidity: ${liquidity:,.0f} >= ${required_liquidity:,.0f} (2x)')
        else:
            failed.append(f'Liquidity: ${liquidity:,.0f} < ${required_liquidity:,.0f} (2x min)')
            print(f"[SNIPER] FAIL: Liquidity ${liquidity:,.0f} < ${required_liquidity:,.0f}")
        
        # 3. Momentum Confirmed Check
        momentum_confirmed = momentum.get('momentum_confirmed', False)
        details['momentum'] = {'confirmed': momentum_confirmed}
        if momentum_confirmed:
            passed.append('Momentum: Confirmed ✓')
        else:
            failed.append('Momentum: NOT confirmed')
            print(f"[SNIPER] FAIL: Momentum not confirmed")
        
        # 4. Fake Pump Check
        fake_pump = tx_analysis.get('fake_pump_suspected', False)
        details['fake_pump'] = {'detected': fake_pump}
        if not fake_pump:
            passed.append('Fake Pump: No ✓')
        else:
            failed.append('Fake Pump: DETECTED')
            print(f"[SNIPER] FAIL: Fake pump suspected")
        
        # 5. MEV Check
        mev_detected = tx_analysis.get('mev_pattern_detected', False)
        details['mev'] = {'detected': mev_detected}
        if not mev_detected:
            passed.append('MEV: No ✓')
        else:
            failed.append('MEV: DETECTED')
            print(f"[SNIPER] FAIL: MEV pattern detected")
        
        # 6. Phase Check
        phase = token_data.get('market_phase', 'unknown')
        details['phase'] = {'value': phase, 'allowed': allowed_phases}
        if phase in allowed_phases:
            passed.append(f'Phase: {phase.upper()} ✓')
        else:
            failed.append(f'Phase: {phase.upper()} not in {allowed_phases}')
            print(f"[SNIPER] FAIL: Phase {phase} not in {allowed_phases}")
        
        # 7. Token Age Check
        age = token_data.get('age_minutes', 999)
        details['age'] = {'value': age, 'max': max_age}
        if age <= max_age:
            passed.append(f'Age: {age:.1f}m <= {max_age}m ✓')
        else:
            failed.append(f'Age: {age:.1f}m > {max_age}m')
            print(f"[SNIPER] FAIL: Age {age:.1f}m > {max_age}m")
        
        # Evaluate result
        trigger_sniper = len(failed) == 0
        downgrade_to_trade = not trigger_sniper
        
        # Build downgrade reason
        if downgrade_to_trade:
            downgrade_reason = f"Failed {len(failed)} condition(s): " + "; ".join(failed)
            print(f"[SNIPER] Downgrade to TRADE: {downgrade_reason[:100]}...")
        else:
            downgrade_reason = ""
            print(f"[SNIPER] ALL CONDITIONS PASSED - Trigger sniper for {token_data.get('address', 'unknown')[:10]}...")
        
        return {
            'trigger_sniper': trigger_sniper,
            'downgrade_to_trade': downgrade_to_trade,
            'downgrade_reason': downgrade_reason,
            'failed_conditions': failed,
            'passed_conditions': passed,
            'condition_details': details
        }
    
    def format_condition_status(self, result: Dict) -> str:
        """
        Format trigger conditions for display in alert.
        
        Returns formatted string with checkmarks/crosses.
        """
        lines = []
        
        for condition in result.get('passed_conditions', []):
            lines.append(f"• {condition}")
        
        for condition in result.get('failed_conditions', []):
            lines.append(f"• ❌ {condition}")
        
        return '\n'.join(lines)
