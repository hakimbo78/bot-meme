#!/usr/bin/env python3
"""
V3 Activity Monitor

Monitors bot logs for V3 scanning activity and pool detections.
Run this script to check recent V3 activity in the logs.
"""

import time
import os
import glob
from datetime import datetime, timedelta

def check_log_files():
    """Check for V3 activity in log files"""
    print("🔍 V3 Activity Monitor")
    print("=" * 50)

    # Look for log files (adjust path as needed)
    log_patterns = [
        "*.log",
        "logs/*.log",
        "/var/log/meme-trading-bot/*.log"
    ]

    found_logs = False
    for pattern in log_patterns:
        log_files = glob.glob(pattern)
        if log_files:
            found_logs = True
            print(f"📁 Found log files: {log_files}")

            for log_file in log_files[-3:]:  # Check last 3 log files
                if os.path.exists(log_file):
                    check_log_file(log_file)

    if not found_logs:
        print("ℹ️ No log files found in standard locations")
        print("💡 V3 activity monitoring:")
        print("   • Run: tail -f /var/log/syslog | grep -i v3")
        print("   • Or check systemd: journalctl -u meme-trading-bot -f | grep V3")

def check_log_file(filepath):
    """Check a specific log file for V3 activity"""
    try:
        print(f"\n📄 Checking: {filepath}")

        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Get recent lines (last 1000)
        recent_lines = lines[-1000:] if len(lines) > 1000 else lines

        v3_lines = []
        connection_lines = []
        pool_lines = []

        for line in recent_lines:
            line_lower = line.lower()
            if 'v3' in line_lower or 'uniswap_v3' in line_lower:
                v3_lines.append(line.strip())

            if 'uniswap v3 support enabled' in line_lower:
                connection_lines.append(line.strip())

            if 'pool' in line_lower and ('v3' in line_lower or 'fee' in line_lower):
                pool_lines.append(line.strip())

        # Report findings
        if connection_lines:
            print("✅ V3 Support Active:")
            for line in connection_lines[-3:]:
                print(f"   {line}")

        if pool_lines:
            print("🎯 V3 Pools Detected:")
            for line in pool_lines[-5:]:
                print(f"   {line}")

        if v3_lines:
            print("📋 Recent V3 Activity:")
            for line in v3_lines[-10:]:
                print(f"   {line}")

        if not any([connection_lines, pool_lines, v3_lines]):
            print("ℹ️ No V3 activity in recent logs")

    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")

def show_monitoring_guide():
    """Show how to monitor V3 activity"""
    print("\n" + "=" * 50)
    print("📊 V3 MONITORING GUIDE")
    print("=" * 50)

    print("\n🔍 Real-time Monitoring:")
    print("   journalctl -u meme-trading-bot -f | grep -i v3")

    print("\n📱 Telegram Alerts:")
    print("   • Look for '[V3]' prefix in alert headers")
    print("   • V3 pools show fee tier info")

    print("\n🖥️ Dashboard:")
    print("   • V3 pools show 'V3 (0.3%)' badges")
    print("   • Fee tier displayed in token cards")

    print("\n📋 Log Indicators:")
    print("   • '🔄 [CHAIN] Uniswap V3 support enabled' = V3 active")
    print("   • '🎯 V3 Pairs detected' = New V3 pools found")
    print("   • Fee tier mentions = V3 pool analysis")

    print("\n⚡ Expected Behavior:")
    print("   • V3 scanning runs alongside V2")
    print("   • No new pools = Normal (waiting for creations)")
    print("   • V3 pools processed same as V2 pools")
    print("   • All existing features work with V3")

if __name__ == "__main__":
    check_log_files()
    show_monitoring_guide()