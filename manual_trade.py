import asyncio
import argparse
import os
import logging
from colorama import init, Fore, Style
from dotenv import load_dotenv

from trading.trade_executor import TradeExecutor
from trading.wallet_manager import WalletManager
from trading.okx_client import OKXDexClient

# Load .env file
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualTrade")
from trading.position_tracker import PositionTracker
from trading.db_handler import TradingDB
from trading.config_manager import ConfigManager

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ManualTrade")

init(autoreset=True)

async def main():
    parser = argparse.ArgumentParser(description="Manual Trade Executor Tool")
    parser.add_argument("--chain", type=str, required=True, help="Chain (base, solana, ethereum)")
    parser.add_argument("--token", type=str, required=True, help="Token Address to BUY")
    parser.add_argument("--amount_usd", type=float, default=10.0, help="Amount in USD (default: $10)")
    args = parser.parse_args()

    print(f"{Fore.CYAN}🛠️  Initializing Manual Trade...")
    print(f"{Fore.CYAN}    Chain: {args.chain}")
    print(f"{Fore.CYAN}    Token: {args.token}")
    print(f"{Fore.CYAN}    Amount: ${args.amount_usd}")

    try:
        # 1. Init Components
        db = TradingDB()
        wm = WalletManager()
        
        # Load Keys
        pk_evm = os.getenv("PRIVATE_KEY_EVM") or os.getenv("PRIVATE_KEY_BASE")
        if pk_evm:
            try:
                wm.import_wallet_evm(pk_evm, 'base')
                wm.import_wallet_evm(pk_evm, 'ethereum')
            except Exception as e:
                print(f"EVM Load Warning: {e}")
            
        pk_sol = os.getenv("PRIVATE_KEY_SOLANA")
        if pk_sol:
            # Official import
            wm.import_wallet_solana(pk_sol)
            
        okx = OKXDexClient()
        pt = PositionTracker(db)
        executor = TradeExecutor(wm, okx, pt)

        # 2. Check Wallet
        wallet = wm.get_address(args.chain)
        if not wallet:
            print(f"{Fore.RED}❌ No wallet found for chain {args.chain}. Check .env!")
            return

        print(f"{Fore.GREEN}✅ Wallet loaded: {wallet}")

        # 3. Override Budget Config Temporarily
        ConfigManager.set_budget(args.amount_usd)
        
        # 4. Execute Trade
        print(f"{Fore.YELLOW}🚀 Executing BUY...")
        success, msg = await executor.execute_buy(
            chain=args.chain,
            token_address=args.token,
            signal_score=999.0 # Manual trade score
        )

        if success:
            print(f"{Fore.GREEN}✅ TRADE SUCCESSFUL! Tx: {msg}")
        else:
            print(f"{Fore.RED}❌ TRADE FAILED: {msg}")

    except Exception as e:
        print(f"{Fore.RED}❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await okx.close()

if __name__ == "__main__":
    asyncio.run(main())
