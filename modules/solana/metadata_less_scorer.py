"""
Metadata-Less Scoring Engine for Solana Tokens

Scores tokens based on behavior, not metadata:
- LP Speed & Quality
- Buy Velocity
- Wallet Quality (Smart Money)
- Creator Risk Assessment

Used when metadata is missing or pending.
"""

import time
import math
from typing import Dict, List, Optional, Any
from .solana_utils import solana_log


class MetadataLessScorer:
    """
    Scores tokens without requiring metadata.

    Core concept: "Price & behavior never lie, metadata always comes last."

    Components:
    - LP Speed Score (0-25)
    - Liquidity Quality Score (0-20)
    - Buy Velocity Score (0-20)
    - Wallet Quality Score (0-15)
    - Creator Risk Score (-20 to 0)

    Final Score: 0-100 (clamped)
    """

    def __init__(self, config: Optional[Dict] = None, smart_wallet_detector=None):
        """
        Initialize metadata-less scorer.

        Args:
            config: Configuration dict
            smart_wallet_detector: SmartWalletDetector instance
        """
        self.config = config or {}
        self.smart_wallet_detector = smart_wallet_detector

        # Score component weights (max values)
        self.lp_speed_max = 25
        self.liquidity_quality_max = 20
        self.buy_velocity_max = 20
        self.wallet_quality_max = 15
        self.creator_risk_min = -20  # Minimum (worst) creator risk score

        # Thresholds
        self.lp_speed_thresholds = {
            60: 25,   # < 60s = 25 points
            120: 20,  # < 120s = 20 points
            300: 15,  # < 300s = 15 points
        }

        self.buy_velocity_thresholds = {
            20: 20,  # >= 20 buys/min = 20 points
            10: 12,  # >= 10 buys/min = 12 points
            5: 6,    # >= 5 buys/min = 6 points
        }

        # Safe mode rules (hard blocks)
        self.safe_mode_enabled = self.config.get('safe_mode', True)
        self.hard_block_conditions = [
            'honeypot_detected',
            'freeze_authority_active',
            'mint_authority_not_revoked',
            'creator_holds_90_percent'
        ]

    def calculate_score(self, token_data: Dict) -> Dict:
        """
        Calculate metadata-less score for a token.

        Args:
            token_data: Token data dict with behavior metrics

        Returns:
            Dict with score breakdown and final score
        """
        # Check hard blocks first
        if self.safe_mode_enabled:
            hard_block_reason = self._check_hard_blocks(token_data)
            if hard_block_reason:
                return {
                    'score': 0,
                    'breakdown': {},
                    'hard_block': True,
                    'hard_block_reason': hard_block_reason,
                    'final_score': 0
                }

        # Calculate components
        lp_speed_score = self._calculate_lp_speed_score(token_data)
        liquidity_quality_score = self._calculate_liquidity_quality_score(token_data)
        buy_velocity_score = self._calculate_buy_velocity_score(token_data)
        wallet_quality_score = self._calculate_wallet_quality_score(token_data)
        creator_risk_score = self._calculate_creator_risk_score(token_data)

        # Sum components
        total_score = (
            lp_speed_score +
            liquidity_quality_score +
            buy_velocity_score +
            wallet_quality_score +
            creator_risk_score
        )

        # Clamp to 0-100
        final_score = max(0, min(100, total_score))

        breakdown = {
            'lp_speed': lp_speed_score,
            'liquidity_quality': liquidity_quality_score,
            'buy_velocity': buy_velocity_score,
            'wallet_quality': wallet_quality_score,
            'creator_risk': creator_risk_score,
            'total_raw': total_score,
            'final_score': final_score
        }

        return {
            'score': final_score,
            'breakdown': breakdown,
            'hard_block': False,
            'hard_block_reason': None,
            'final_score': final_score
        }

    def _calculate_lp_speed_score(self, token_data: Dict) -> int:
        """
        Calculate LP Speed Score (0-25).

        Faster LP creation = higher conviction.

        Args:
            token_data: Token data with lp_creation_time_seconds

        Returns:
            Score 0-25
        """
        lp_creation_seconds = token_data.get('lp_creation_time_seconds', float('inf'))

        if lp_creation_seconds < 60:
            return 25
        elif lp_creation_seconds < 120:
            return 20
        elif lp_creation_seconds < 300:
            return 15
        else:
            return 5  # Default for slower LPs

    def _calculate_liquidity_quality_score(self, token_data: Dict) -> int:
        """
        Calculate Liquidity Quality Score (0-20).

        Based on SOL added and LP ratio.

        Args:
            token_data: Token data with lp_sol_amount, lp_locked_percent

        Returns:
            Score 0-20
        """
        lp_sol_amount = token_data.get('lp_sol_amount', 0)
        lp_locked_percent = token_data.get('lp_locked_percent', 0)

        # Base score from SOL amount (logarithmic scaling)
        if lp_sol_amount > 0:
            base_score = min(20, math.log10(lp_sol_amount) * 10)
        else:
            base_score = 0

        # Bonus for locked liquidity
        lock_bonus = 0
        if lp_locked_percent >= 100:
            lock_bonus = 5
        elif lp_locked_percent >= 50:
            lock_bonus = 3

        return min(20, base_score + lock_bonus)

    def _calculate_buy_velocity_score(self, token_data: Dict) -> int:
        """
        Calculate Buy Velocity Score (0-20).

        Measures buy transaction acceleration.

        Args:
            token_data: Token data with buys_per_minute, unique_buyers

        Returns:
            Score 0-20
        """
        buys_per_minute = token_data.get('buys_per_minute', 0)
        unique_buyers = token_data.get('unique_buyers', 0)

        # Base score from buys per minute
        if buys_per_minute >= 20:
            velocity_score = 20
        elif buys_per_minute >= 10:
            velocity_score = 12
        elif buys_per_minute >= 5:
            velocity_score = 6
        else:
            velocity_score = 0

        # Bonus for unique buyers
        if unique_buyers >= 50:
            velocity_score += 5
        elif unique_buyers >= 20:
            velocity_score += 3
        elif unique_buyers >= 10:
            velocity_score += 1

        return min(20, velocity_score)

    def _calculate_wallet_quality_score(self, token_data: Dict) -> int:
        """
        Calculate Wallet Quality Score (0-15).

        Uses Smart Wallet Detector to score early buyers.

        Args:
            token_data: Token data with buyer_wallet_addresses

        Returns:
            Score 0-15
        """
        if not self.smart_wallet_detector:
            return 0

        buyer_wallets = token_data.get('buyer_wallet_addresses', [])
        if not buyer_wallets:
            return 0

        # Analyze wallets
        analysis = self.smart_wallet_detector.analyze_wallets(buyer_wallets)
        smart_wallet_score = analysis.get('smart_wallet_score', 0)

        # Scale to 0-15 range (smart wallet detector returns 0-40)
        scaled_score = min(15, (smart_wallet_score / 40) * 15)

        return int(scaled_score)

    def _calculate_creator_risk_score(self, token_data: Dict) -> int:
        """
        Calculate Creator Risk Score (-20 to 0).

        Penalties for risky creator behavior.

        Args:
            token_data: Token data with creator analysis

        Returns:
            Score -20 to 0
        """
        score = 0

        # Creator used fresh wallet
        if token_data.get('creator_fresh_wallet', False):
            score -= 10

        # Creator reused deploy wallet
        if token_data.get('creator_reused_wallet', False):
            score -= 5

        # Creator dumped previous tokens
        if token_data.get('creator_dumped_previous', False):
            score -= 10

        # Creator blacklisted
        if token_data.get('creator_blacklisted', False):
            score -= 20

        # Creator holds too much supply
        creator_supply_percent = token_data.get('creator_supply_percent', 0)
        if creator_supply_percent >= 90:
            score -= 20  # This will be caught by hard block too
        elif creator_supply_percent >= 50:
            score -= 10
        elif creator_supply_percent >= 20:
            score -= 5

        return max(-20, score)  # Clamp to minimum -20

    def _check_hard_blocks(self, token_data: Dict) -> Optional[str]:
        """
        Check for hard block conditions that prevent scoring.

        Args:
            token_data: Token data

        Returns:
            Block reason string or None
        """
        for condition in self.hard_block_conditions:
            if token_data.get(condition, False):
                return f"HARD_BLOCK: {condition.replace('_', ' ').upper()}"

        return None

    def log_score(self, token_data: Dict, score_result: Dict):
        """
        Log metadata-less score in required format.

        Args:
            token_data: Token data
            score_result: Score calculation result
        """
        mint = token_data.get('mint', 'UNKNOWN')
        breakdown = score_result.get('breakdown', {})

        solana_log(
            f"[SOLANA][SCORE][METALESS] Token: {mint[:8]}... | "
            f"LP Speed: +{breakdown.get('lp_speed', 0)} | "
            f"Liquidity: +{breakdown.get('liquidity_quality', 0)} | "
            f"Velocity: +{breakdown.get('buy_velocity', 0)} | "
            f"Wallets: +{breakdown.get('wallet_quality', 0)} | "
            f"Creator Risk: {breakdown.get('creator_risk', 0)} | "
            f"Final Score: {score_result.get('final_score', 0)}",
            "INFO"
        )