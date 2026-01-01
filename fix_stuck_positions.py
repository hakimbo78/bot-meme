"""
Check and Fix Stuck Positions
Finds positions marked OPEN but likely already closed
"""
from trading.db_handler import TradingDB
from trading.position_tracker import PositionTracker
from trading.okx_client import OKXDexClient
from trading.config_manager import ConfigManager
import asyncio

async def check_and_fix_stuck_positions():
    print("\n" + "="*80)
    print("STUCK POSITION CHECKER & FIXER")
    print("="*80 + "\n")
    
    db = TradingDB()
    pt = PositionTracker(db)
    okx = OKXDexClient()
    
    # Get all OPEN positions
    positions = pt.get_open_positions()
    
    print(f"Found {len(positions)} position(s) marked as OPEN\n")
    
    if not positions:
        print("✅ No stuck positions. Database is clean.")
        return
    
    stuck_positions = []
    
    for pos in positions:
        print(f"Checking Position #{pos['id']}:")
        print(f"  Token: {pos['token_address'][:10]}...{pos['token_address'][-8:]}")
        print(f"  Chain: {pos['chain']}")
        print(f"  Entry: ${pos['entry_value_usd']:.2f}")
        
        # Try to get current balance
        try:
            chain = pos['chain']
            token_addr = pos['token_address']
            entry_amount = float(pos['entry_amount'])
            
            # Check if we still have tokens
            native_token = "So11111111111111111111111111111111111111112" if chain == 'solana' else "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
            
            amount_str = str(int(entry_amount))
            quote = await okx.get_quote(
                chain=chain,
                from_token=token_addr,
                to_token=native_token,
                amount=amount_str,
                slippage=0.01
            )
            
            if not quote:
                print(f"  ⚠️ Cannot get quote - token might be rugged or delisted")
                stuck_positions.append(pos)
            else:
                raw_out = float(quote.get('toTokenAmount', '0'))
                if raw_out == 0:
                    print(f"  ⚠️ Quote returns 0 - likely sold or rugged")
                    stuck_positions.append(pos)
                else:
                    print(f"  ✅ Position seems active (can still quote)")
        
        except Exception as e:
            print(f"  ❌ Error checking: {e}")
            stuck_positions.append(pos)
        
        print()
    
    # Summary
    print("="*80)
    print(f"SUMMARY: {len(stuck_positions)} stuck position(s) found")
    print("="*80 + "\n")
    
    if stuck_positions:
        print("Stuck positions that should be closed:")
        for pos in stuck_positions:
            print(f"  - Position #{pos['id']} ({pos['token_address'][:10]}...)")
        
        print("\nDo you want to force-close these positions? (y/n): ", end='')
        response = input().strip().lower()
        
        if response == 'y':
            for pos in stuck_positions:
                pt.force_close_position(pos['id'], reason="MANUAL_FIX_STUCK_POSITION")
                print(f"✅ Closed position #{pos['id']}")
            
            print(f"\n✅ Fixed {len(stuck_positions)} stuck position(s)")
            print("Bot should now accept new trades.")
        else:
            print("\n⚠️ No changes made. Run script again when ready to fix.")
    else:
        print("✅ All OPEN positions appear to be legitimate.")
    
    await okx.close()

if __name__ == "__main__":
    asyncio.run(check_and_fix_stuck_positions())
