#!/usr/bin/env python3
"""
Quick debug script untuk test Pump.fun scanner directly
"""
import asyncio
import sys
sys.path.insert(0, '/home/hakim/bot-meme')

from modules.solana.pumpfun_scanner import PumpfunScanner
from modules.solana.solana_utils import PUMPFUN_PROGRAM_ID
from config import SOLANA_ALCHEMY_SAFE_CONFIG
from solana.rpc.async_api import AsyncClient

async def main():
    # Create Solana client
    rpc_url = "https://api.alchemy.com/solana/v1/mainnet"  # Or from env
    client = AsyncClient(rpc_url)
    
    # Initialize scanner
    scanner = PumpfunScanner({
        'programs': {'pumpfun': PUMPFUN_PROGRAM_ID}
    })
    scanner.client = client
    
    print(f"🔍 Testing Pump.fun Scanner")
    print(f"Program ID: {PUMPFUN_PROGRAM_ID}")
    print(f"RPC: {rpc_url}")
    print(f"Config: {SOLANA_ALCHEMY_SAFE_CONFIG}\n")
    
    # Test scan
    try:
        result = scanner.scan()
        print(f"✅ Scan result: {len(result)} new tokens")
        for token in result:
            print(f"  - {token.get('symbol')} ({token.get('token_address')})")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())
