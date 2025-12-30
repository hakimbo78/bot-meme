"""
Demo Manual Audit - Menampilkan hasil lengkap audit token
"""
import asyncio
from manual_audit import ManualTokenAuditor

async def demo_audit():
    """Demo audit dengan output lengkap"""
    auditor = ManualTokenAuditor()
    
    print("\n" + "="*80)
    print("DEMO: MANUAL TOKEN AUDIT TOOL")
    print("="*80)
    
    # Test Base - VIRTUAL token
    print("\n\n📍 TEST 1: BASE NETWORK - VIRTUAL TOKEN")
    print("-" * 80)
    await auditor.audit_token('base', '0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b', send_telegram=False)
    
    print("\n\n" + "="*80)
    print("DEMO SELESAI")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(demo_audit())
