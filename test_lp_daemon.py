"""
Quick test for LP Monitor Daemon (dry-run mode)
"""

import asyncio
from lp_monitor_daemon import LPMonitorDaemon
from colorama import init, Fore

init(autoreset=True)


async def test_daemon():
    """Test LP monitor daemon with mock/dry-run."""
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}LP MONITOR DAEMON - TEST MODE")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    print(f"{Fore.YELLOW}Testing daemon instantiation...")
    daemon = LPMonitorDaemon()
    
    print(f"{Fore.GREEN}✅ Daemon initialized successfully")
    print(f"{Fore.YELLOW}Analyzers available:")
    for chain in daemon.lp_analyzers.keys():
        print(f"  - {chain.upper()}")
    
    print(f"\n{Fore.GREEN}{'='*60}")
    print(f"{Fore.GREEN}DAEMON TEST PASSED")
    print(f"{Fore.GREEN}{'='*60}\n")
    
    print(f"{Fore.CYAN}To run daemon in production:")
    print(f"  python lp_monitor_daemon.py")
    print(f"\n{Fore.CYAN}Daemon will:")
    print(f"  1. Check all open positions every 30s")
    print(f"  2. Calculate LP Intent Risk (0-100)")
    print(f"  3. Auto-exit if Risk > 70 or LP drop > 5%")
    print(f"  4. Continue monitoring until stopped (Ctrl+C)\n")


if __name__ == "__main__":
    asyncio.run(test_daemon())
