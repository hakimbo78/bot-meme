"""
Phase Detector - Classifies token lifecycle phase for context-aware scoring
Determines whether a token is in LAUNCH, EARLY_GROWTH, or MATURE phase.

This module helps adjust scoring weights based on token age:
- LAUNCH (<5 min): Highest priority for sniper mode, prioritize liquidity and momentum
- EARLY_GROWTH (5-60 min): Still eligible for sniper, prioritize holder distribution
- MATURE (>1h): Not eligible for sniper, prioritize volume sustainability
"""
from typing import Literal

# Type alias for market phases
MarketPhase = Literal["launch", "early_growth", "mature"]

# Sniper-eligible phases
SNIPER_ELIGIBLE_PHASES = ["launch", "early_growth"]


def detect_market_phase(age_minutes: float) -> MarketPhase:
    """
    Classify token lifecycle phase based on age.
    
    Args:
        age_minutes: Token age in minutes since pair creation
        
    Returns:
        Market phase: "launch" | "early_growth" | "mature"
    """
    if age_minutes < 5:
        return "launch"
    elif age_minutes < 60:  # 1 hour
        return "early_growth"
    else:
        return "mature"


def is_sniper_eligible_phase(phase: MarketPhase) -> bool:
    """Check if phase is eligible for sniper mode."""
    return phase in SNIPER_ELIGIBLE_PHASES


def get_phase_scoring_weights(phase: MarketPhase) -> dict:
    """
    Get scoring weight adjustments for the given market phase.
    
    Returns dict with bonus/penalty points for each phase.
    These are additive adjustments to the base score.
    """
    if phase == "launch":
        return {
            'liquidity_bonus': 5,       # Extra points for good liquidity
            'momentum_bonus': 5,        # Extra points for momentum confirmation
            'holder_bonus': 0,          # No extra for holder distribution (too early)
            'volume_bonus': 0,          # No extra for volume (just launched)
            'sniper_eligible': True,
            'description': 'Launch phase: liquidity and momentum prioritized (SNIPER ELIGIBLE)'
        }
    elif phase == "early_growth":
        return {
            'liquidity_bonus': 3,
            'momentum_bonus': 3,
            'holder_bonus': 5,          # Prioritize holder distribution
            'volume_bonus': 2,          # Some weight on volume
            'sniper_eligible': True,
            'description': 'Early growth phase: balanced scoring (SNIPER ELIGIBLE)'
        }
    else:  # mature
        return {
            'liquidity_bonus': 0,
            'momentum_bonus': -5,       # Momentum less important (should be stable)
            'holder_bonus': 0,
            'volume_bonus': 5,          # Volume sustainability important
            'sniper_eligible': False,
            'description': 'Mature phase: volume sustainability prioritized'
        }


def get_phase_description(phase: MarketPhase) -> str:
    """Get human-readable description of the phase."""
    descriptions = {
        "launch": "🚀 LAUNCH (<5 min)",
        "early_growth": "📈 EARLY GROWTH (5-60 min)",
        "mature": "🏛️ MATURE (>1h)"
    }
    return descriptions.get(phase, "❓ UNKNOWN")


def get_phase_requirements(phase: MarketPhase) -> dict:
    """
    Get stricter/looser requirements based on phase.
    
    For example, LAUNCH phase might require less liquidity
    but stricter momentum confirmation.
    """
    if phase == "launch":
        return {
            'min_liquidity_multiplier': 0.8,  # Allow 80% of min liquidity
            'require_momentum': True,          # Must have momentum confirmation
            'max_holder_concentration': 50,    # Allow higher concentration (early)
            'sniper_eligible': True,
            'description': 'Launch: relaxed liquidity, strict momentum'
        }
    elif phase == "early_growth":
        return {
            'min_liquidity_multiplier': 1.0,
            'require_momentum': True,
            'max_holder_concentration': 45,    # Slightly stricter
            'sniper_eligible': True,
            'description': 'Early growth: standard requirements'
        }
    else:  # mature
        return {
            'min_liquidity_multiplier': 1.2,  # Require more liquidity
            'require_momentum': False,         # Momentum less critical (stable)
            'max_holder_concentration': 35,    # Tighter distribution required
            'sniper_eligible': False,
            'description': 'Mature: stricter liquidity and distribution'
        }


class PhaseDetector:
    """
    Stateless utility class for phase detection.
    Can be used as a class or via standalone functions.
    """
    
    @staticmethod
    def detect(age_minutes: float) -> MarketPhase:
        """Detect market phase from age."""
        return detect_market_phase(age_minutes)
    
    @staticmethod
    def get_weights(phase: MarketPhase) -> dict:
        """Get scoring weight adjustments."""
        return get_phase_scoring_weights(phase)
    
    @staticmethod
    def get_requirements(phase: MarketPhase) -> dict:
        """Get phase-specific requirements."""
        return get_phase_requirements(phase)
    
    @staticmethod
    def is_sniper_eligible(phase: MarketPhase) -> bool:
        """Check if phase is eligible for sniper mode."""
        return is_sniper_eligible_phase(phase)
    
    @staticmethod
    def get_full_analysis(age_minutes: float) -> dict:
        """
        Get complete phase analysis for a token.
        
        Args:
            age_minutes: Token age in minutes
            
        Returns:
            Complete phase analysis including phase, weights, and requirements
        """
        phase = detect_market_phase(age_minutes)
        
        return {
            'market_phase': phase,
            'phase_description': get_phase_description(phase),
            'scoring_weights': get_phase_scoring_weights(phase),
            'requirements': get_phase_requirements(phase),
            'sniper_eligible': is_sniper_eligible_phase(phase),
            'age_minutes': age_minutes
        }

