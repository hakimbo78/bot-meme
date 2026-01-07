"""
DEBUG SCRIPT: Trace signal flow to find where pairs are being filtered
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading_config import TRADING_CONFIG

def check_config():
    """Check signal mode configuration"""
    print("=== CONFIGURATION CHECK ===\n")
    
    signal_config = TRADING_CONFIG.get('signal_mode', {})
    print(f"Signal Mode Enabled: {signal_config.get('enabled')}")
    print(f"Max Age: {signal_config.get('max_age_hours')}h")
    print(f"Min Age: {signal_config.get('min_age_hours')}h")  
    print(f"Min Liquidity: ${signal_config.get('min_liquidity'):,}")
    print(f"Score Thresholds: BUY≥{signal_config.get('score_thresholds', {}).get('buy')}, WATCH≥{signal_config.get('score_thresholds', {}).get('watch')}")
    
    rebound_config = TRADING_CONFIG.get('rebound_mode', {})
    print(f"\nRebound Mode Enabled: {rebound_config.get('enabled')}")
    print(f"Min ATH Drop: {rebound_config.get('min_ath_drop_percent')}%")
    
    print("\n=== POTENTIAL ISSUES ===\n")
    
    # Check if age range is too restrictive
    if signal_config.get('min_age_hours', 0) >= 1.0:
        print("⚠️  WARNING: min_age_hours = 1h means tokens <1h old are blocked!")
        print("   This filters out very fresh launches")
    
    # Check if liquidity threshold too high
    if signal_config.get('min_liquidity', 0) >= 20000:
        print("⚠️  WARNING: min_liquidity = $20K is quite high")
        print("   Many fresh meme tokens start with <$20K liquidity")
    
    # Check score thresholds
    if signal_config.get('score_thresholds', {}).get('watch', 0) >= 50:
        print("⚠️  INFO: WATCH threshold ≥50 means only mid-tier tokens get alerts")
        print("   Score <50 = completely ignored")

if __name__ == "__main__":
    check_config()
