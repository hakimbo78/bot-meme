"""
Quick test script to verify Birdeye API integration.
Tests OHLCV data fetching and ATH calculation.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Birdeye client
from birdeye_client import BirdeyeClient

async def test_birdeye():
    """Test Birdeye API connection and ATH calculation."""
    
    print("=" * 60)
    print("BIRDEYE API INTEGRATION TEST")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv('BIRDEYE_API_KEY')
    if not api_key:
        print("❌ ERROR: BIRDEYE_API_KEY not found in .env")
        return
    
    print(f"✅ API Key loaded: {api_key[:10]}...")
    
    # Initialize client
    client = BirdeyeClient(api_key)
    print("✅ Birdeye client initialized")
    
    # Test token (well-known Solana token: BONK)
    test_token = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK token
    chain = "solana"
    
    print(f"\n🧪 Testing with token: {test_token[:10]}... (BONK)")
    print(f"📊 Fetching OHLCV data...")
    
    try:
        # Test OHLCV fetch
        candles = await client.get_ohlcv(test_token, chain, timeframe='1H', limit=100)
        
        if candles:
            print(f"✅ Successfully fetched {len(candles)} candles")
            print(f"   Latest candle: {candles[-1]}")
            
            # Test ATH calculation
            print(f"\n📈 Calculating ATH...")
            ath_data = await client.calculate_ath(test_token, chain)
            
            if ath_data.get('error'):
                print(f"❌ ATH calculation failed: {ath_data['error']}")
            else:
                print(f"✅ ATH calculation successful!")
                print(f"   ATH: ${ath_data['ath']:.8f}")
                print(f"   Current: ${ath_data['current_price']:.8f}")
                print(f"   Drop: {ath_data['drop_percent']:.1f}%")
                print(f"   Candles analyzed: {ath_data['candles_count']}")
        else:
            print("❌ No candles returned (check API key or rate limits)")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_birdeye())
