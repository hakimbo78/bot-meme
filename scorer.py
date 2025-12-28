"""
Token Scorer - SINGLE SOURCE OF TRUTH for scoring logic
Enhanced with Security Audit Upgrades (2025-12-26)

Scoring adjustments:
- Momentum validation bonus/cap
- Fake pump/MEV penalties
- Wallet tracking (dev/smart money) adjustments
- Market phase scoring weights
"""
from config import (
    SCORE_RULES, 
    ALERT_THRESHOLDS, 
    EXTREME_HOLDER_CONCENTRATION_THRESHOLD,
    MOMENTUM_CAP_SCORE,
    MOMENTUM_SCORE_MAX,
    AUTO_UPGRADE_ENABLED
)

def classify_alert(score):
    """
    Classify alert level based on score.
    
    Args:
        score: Integer score value
        
    Returns:
        "INFO" | "WATCH" | "TRADE" | None
    """
    if score >= ALERT_THRESHOLDS["TRADE"]:
        return "TRADE"
    elif score >= ALERT_THRESHOLDS["WATCH"]:
        return "WATCH"
    elif score >= ALERT_THRESHOLDS["INFO"]:
        return "INFO"
    return None


class TokenScorer:
    """
    Enhanced Token Scorer with Security Audit features.
    
    SINGLE SOURCE OF TRUTH for all scoring logic.
    
    New features:
    - Momentum validation: +momentum_score if confirmed, cap at 65 if not
    - Fake pump detection: -25 points if suspected
    - MEV detection: Force verdict to WATCH
    - Dev wallet tracking: DUMP = IGNORE, WARNING = -15 points
    - Smart money bonus: +10 if detected
    - Market phase adjustments: Phase-specific weight bonuses
    """
    
    def score_token(self, data, chain_config=None):
        """
        Score token based on rules, optionally using chain-specific thresholds.
        
        Enhanced with security audit scoring adjustments.
        
        Args:
            data: Token analysis data (enriched with security modules)
            chain_config: Optional chain-specific config for thresholds
        
        Returns:
            Dict with score, risk_flags, verdict, alert_level, and new fields
        """
        score = 0
        risk_flags = []
        forced_verdict = None  # For forced overrides (MEV, dev DUMP)
        
        # Use chain-specific thresholds if provided, else defaults
        thresholds = chain_config.get('alert_thresholds', ALERT_THRESHOLDS) if chain_config else ALERT_THRESHOLDS
        
        # =========================================
        # ORIGINAL SCORING RULES
        # =========================================
        
        # Rule: Liquidity >= $20k -> +30
        if data.get("liquidity_usd", 0) >= 20000:
            score += SCORE_RULES["LIQUIDITY_GT_20K"]
        else:
            risk_flags.append(f"Low Liquidity (${data.get('liquidity_usd', 0):,.0f})")

        # Rule: Ownership renounced -> +20
        if data.get("renounced"):
            score += SCORE_RULES["RENOUNCED"]
        else:
            risk_flags.append("Ownership NOT renounced")

        # Rule: No mint / blacklist -> +20
        if not data.get("mintable") and not data.get("blacklist"):
            score += SCORE_RULES["NO_MINT_BLACKLIST"]
        else:
            if data.get("mintable"): 
                risk_flags.append("Mintable")
            if data.get("blacklist"): 
                risk_flags.append("Blacklist Enabled")

        # Rule: Top10 holders <= 40% -> +20
        top10_percent = data.get("top10_holders_percent", 100)
        if top10_percent <= 40:
            score += SCORE_RULES["HOLDERS_TOP10_LT_40"]
        else:
            if top10_percent > EXTREME_HOLDER_CONCENTRATION_THRESHOLD:
                risk_flags.append(f"Extreme Holder Concentration ({top10_percent:.0f}%)")
            else:
                risk_flags.append(f"High Concentration (Top10: {top10_percent:.0f}%)")

        # Rule: Token age < 15 minutes -> +10
        if data.get("age_minutes", 999) < 15:
            score += SCORE_RULES["AGE_LT_15_MIN"]

        # =========================================
        # NEW SECURITY AUDIT SCORING RULES
        # =========================================
        
        # 1. MOMENTUM VALIDATION
        momentum_confirmed = data.get("momentum_confirmed", False)
        momentum_score = data.get("momentum_score", 0)
        
        if momentum_confirmed:
            # Add momentum bonus (0-20 points)
            score += min(momentum_score, MOMENTUM_SCORE_MAX)
        else:
            # Flag as snapshot-only if not confirmed
            risk_flags.append("⚠️ Snapshot only (no momentum confirmation)")
        
        # 2. FAKE PUMP DETECTION (-25 points)
        if data.get("fake_pump_suspected", False):
            score -= 25
            risk_flags.append("🚨 FAKE PUMP suspected")
        
        # 3. MEV DETECTION (force WATCH verdict)
        if data.get("mev_pattern_detected", False):
            forced_verdict = "WATCH"
            risk_flags.append("🤖 MEV pattern detected")
        
        # 4. DEV WALLET ACTIVITY
        dev_flag = data.get("dev_activity_flag", "UNKNOWN")
        if dev_flag == "DUMP":
            forced_verdict = "IGNORE"
            risk_flags.append("🔴 DEV DUMP detected")
        elif dev_flag == "WARNING":
            score -= 15
            risk_flags.append("⚠️ DEV activity warning")
        elif dev_flag == "SAFE":
            # No penalty, could add small bonus
            pass
        
        # 5. SMART MONEY BONUS (+10)
        if data.get("smart_money_involved", False):
            score += 10
            # Note: Not a risk flag, it's positive
        
        # 6. MARKET PHASE ADJUSTMENTS
        phase_weights = data.get("phase_weights", {})
        if phase_weights:
            # Apply phase-specific bonuses
            # These are additive adjustments based on current market phase
            
            # Liquidity bonus for launch phase
            if data.get("liquidity_usd", 0) >= 20000:
                score += phase_weights.get("liquidity_bonus", 0)
            
            # Momentum bonus for launch phase
            if momentum_confirmed:
                score += phase_weights.get("momentum_bonus", 0)
            
            # Holder bonus for growth phase  
            if top10_percent <= 40:
                score += phase_weights.get("holder_bonus", 0)
            
            # Volume bonus (simplified - based on liquidity proxy)
            if data.get("liquidity_usd", 0) > 50000:
                score += phase_weights.get("volume_bonus", 0)
        
        # =========================================
        # MOMENTUM CAP ENFORCEMENT
        # =========================================
        
        # If momentum NOT confirmed, cap score at 65
        if not momentum_confirmed and score > MOMENTUM_CAP_SCORE:
            original_score = score
            score = MOMENTUM_CAP_SCORE
            risk_flags.append(f"Score capped at {MOMENTUM_CAP_SCORE} (momentum not confirmed, was {original_score})")
        
        # Ensure score doesn't go negative
        score = max(0, score)
        
        # =========================================
        # FINAL VERDICT DETERMINATION
        # =========================================
        
        # Track if this is an auto-upgrade candidate
        is_trade_early = False
        upgrade_eligible = False
        
        # Check for forced verdicts first
        if forced_verdict:
            verdict = forced_verdict
            alert_level = forced_verdict if forced_verdict in ["INFO", "WATCH", "TRADE"] else None
        else:
            # Normal classification using chain-specific thresholds
            alert_level = self._classify_alert(score, thresholds)
            
            # TRADE-EARLY Logic: Score meets TRADE but momentum not confirmed
            if alert_level == "TRADE" and not momentum_confirmed and AUTO_UPGRADE_ENABLED:
                # Check for blocking conditions (would prevent upgrade anyway)
                has_blocking_conditions = (
                    data.get("fake_pump_suspected", False) or
                    data.get("mev_pattern_detected", False) or
                    dev_flag == "DUMP"
                )
                
                if not has_blocking_conditions:
                    # Assign TRADE-EARLY instead of TRADE
                    alert_level = "TRADE-EARLY"
                    verdict = "TRADE-EARLY"
                    is_trade_early = True
                    upgrade_eligible = True
                    risk_flags.append("⏳ TRADE-EARLY: Awaiting momentum confirmation for upgrade")
                else:
                    verdict = alert_level if alert_level else "IGNORE"
            else:
                verdict = alert_level if alert_level else "IGNORE"
        
        # =========================================
        # BUILD RESULT
        # =========================================
        
        return {
            "score": score,
            "risk_flags": risk_flags,
            "verdict": verdict,
            "alert_level": alert_level,
            
            # New fields for operator clarity
            "momentum_confirmed": momentum_confirmed,
            "market_phase": data.get("market_phase", "unknown"),
            "fake_pump_suspected": data.get("fake_pump_suspected", False),
            "mev_pattern_detected": data.get("mev_pattern_detected", False),
            "dev_activity_flag": dev_flag,
            "smart_money_involved": data.get("smart_money_involved", False),
            "forced_verdict": forced_verdict is not None,
            
            # Auto-upgrade fields
            "is_trade_early": is_trade_early,
            "upgrade_eligible": upgrade_eligible,
            
            # Operator hints (calculated)
            "operator_hint": self._generate_operator_hint(
                score=score,
                risk_flags=risk_flags,
                momentum_confirmed=momentum_confirmed,
                dev_flag=dev_flag,
                mev_detected=data.get("mev_pattern_detected", False),
                fake_pump=data.get("fake_pump_suspected", False)
            )
        }
    
    def _classify_alert(self, score, thresholds):
        """Classify alert level based on score and thresholds"""
        if score >= thresholds["TRADE"]:
            return "TRADE"
        elif score >= thresholds["WATCH"]:
            return "WATCH"
        elif score >= thresholds["INFO"]:
            return "INFO"
        return None
    
    def _generate_operator_hint(self, score, risk_flags, momentum_confirmed, 
                                 dev_flag, mev_detected, fake_pump):
        """
        Generate operator decision hints.
        
        NOT buy/sell signals - just decision clarity for manual review.
        """
        # Risk Level
        risk_count = len(risk_flags)
        if risk_count >= 5 or fake_pump or dev_flag == "DUMP":
            risk_level = "HIGH"
        elif risk_count >= 3 or mev_detected or dev_flag == "WARNING":
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Suggested Entry Strategy (NOT a buy signal)
        if risk_level == "HIGH":
            entry_suggestion = "Pullback only - high risk detected"
        elif risk_level == "MEDIUM":
            entry_suggestion = "Wait for confirmation"
        else:
            entry_suggestion = "Standard consideration"
        
        # Confidence Level
        if momentum_confirmed and dev_flag == "SAFE" and not mev_detected:
            confidence = "Full validation"
        elif momentum_confirmed:
            confidence = "Momentum confirmed"
        else:
            confidence = "Snapshot only"
        
        return {
            "risk_level": risk_level,
            "suggested_entry": entry_suggestion,
            "confidence": confidence
        }
    
    def check_auto_upgrade(self, score_data: dict, token_data: dict, chain_config: dict = None) -> dict:
        """
        Check if TRADE-EARLY can be upgraded to TRADE.
        
        Auto-upgrade triggers when:
        - Verdict == TRADE-EARLY
        - momentum_confirmed == True
        - liquidity_usd >= chain min_liquidity_usd
        - fake_pump_suspected == False
        - mev_pattern_detected == False
        - dev_activity_flag != "DUMP"
        
        Args:
            score_data: Score result from score_token()
            token_data: Token analysis data
            chain_config: Optional chain-specific config
            
        Returns:
            Dict with:
            - can_upgrade: bool
            - upgrade_reason: str (if can_upgrade)
            - blocked_reasons: list[str] (if cannot upgrade)
            - upgraded_score_data: dict (updated score_data if upgraded)
        """
        result = {
            "can_upgrade": False,
            "upgrade_reason": None,
            "blocked_reasons": [],
            "upgraded_score_data": None
        }
        
        # Only process TRADE-EARLY verdicts
        if score_data.get("verdict") != "TRADE-EARLY":
            result["blocked_reasons"].append("Not a TRADE-EARLY verdict")
            return result
        
        # Check upgrade conditions
        blocked_reasons = []
        
        # 1. Momentum confirmation
        momentum_confirmed = token_data.get("momentum_confirmed", False) or score_data.get("momentum_confirmed", False)
        if not momentum_confirmed:
            blocked_reasons.append("Momentum not confirmed")
        
        # 2. Liquidity check
        min_liquidity = 0
        if chain_config:
            min_liquidity = chain_config.get("min_liquidity_usd", 0)
        liquidity_usd = token_data.get("liquidity_usd", 0)
        if liquidity_usd < min_liquidity:
            blocked_reasons.append(f"Liquidity ${liquidity_usd:,.0f} < min ${min_liquidity:,}")
        
        # 3. Fake pump check
        if token_data.get("fake_pump_suspected", False) or score_data.get("fake_pump_suspected", False):
            blocked_reasons.append("Fake pump detected")
        
        # 4. MEV check
        if token_data.get("mev_pattern_detected", False) or score_data.get("mev_pattern_detected", False):
            blocked_reasons.append("MEV pattern detected")
        
        # 5. Dev activity check
        dev_flag = token_data.get("dev_activity_flag", score_data.get("dev_activity_flag", "UNKNOWN"))
        if dev_flag == "DUMP":
            blocked_reasons.append("Dev DUMP detected")
        
        # Determine upgrade eligibility
        if not blocked_reasons:
            # All conditions met - can upgrade
            result["can_upgrade"] = True
            result["upgrade_reason"] = "Momentum confirmed, all safety checks passed"
            
            # Create upgraded score data
            upgraded_data = score_data.copy()
            upgraded_data["verdict"] = "TRADE"
            upgraded_data["alert_level"] = "TRADE"
            upgraded_data["is_trade_early"] = False
            upgraded_data["upgrade_eligible"] = False
            upgraded_data["was_upgraded"] = True
            upgraded_data["upgrade_reason"] = result["upgrade_reason"]
            
            # Update risk flags - remove TRADE-EARLY message, add upgrade indicator
            new_flags = [f for f in upgraded_data.get("risk_flags", []) 
                        if "TRADE-EARLY" not in f]
            new_flags.append("🔄 AUTO-UPGRADED from TRADE-EARLY")
            upgraded_data["risk_flags"] = new_flags
            
            # Update operator hint for upgraded confidence
            upgraded_data["operator_hint"] = {
                "risk_level": upgraded_data.get("operator_hint", {}).get("risk_level", "MEDIUM"),
                "suggested_entry": "Standard consideration",
                "confidence": "Full validation (upgraded)"
            }
            
            result["upgraded_score_data"] = upgraded_data
        else:
            result["blocked_reasons"] = blocked_reasons
        
        return result
