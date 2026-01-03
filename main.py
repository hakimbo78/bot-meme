import argparse
import argparse
import time
import asyncio
import requests
from colorama import init, Fore, Style
from web3 import Web3
from scanner import BaseScanner
from analyzer import TokenAnalyzer
from scorer import TokenScorer
from scanner import BaseScanner
from analyzer import TokenAnalyzer
from scorer import TokenScorer
from telegram_notifier import TelegramNotifier
from tokensniffer_analyzer import TokenSnifferAnalyzer
from error_monitor import ErrorMonitor
from config import BASE_RPC_URL, UNISWAP_V2_FACTORY, MIN_LIQUIDITY_USD, ALERT_THRESHOLDS, AUTO_UPGRADE_ENABLED, AUTO_UPGRADE_COOLDOWN_SECONDS, AUTO_UPGRADE_MAX_WAIT_MINUTES, ROTATION_CONFIG, PATTERN_CONFIG, NARRATIVE_CONFIG, SMART_MONEY_CONFIG, CONVICTION_CONFIG

# Market Intelligence Layer
try:
    from core import RotationEngine, PatternMemory, PatternMatcher
    from intelligence import NarrativeEngine, SmartMoneyEngine, ConvictionEngine
    MARKET_INTEL_AVAILABLE = True
except ImportError as e:
    MARKET_INTEL_AVAILABLE = False
    print(f"⚠️ Market Intelligence Layer not found: {e} - Core features will be disabled")

# Solana module imports (optional - will gracefully degrade if not available)
SOLANA_MODULE_AVAILABLE = False
try:
    from modules.solana import (
        SolanaScanner,
        SolanaScoreEngine,
        SolanaSniperDetector,
        SolanaRunningDetector,
        SolanaAlert,
        solana_log
    )
    SOLANA_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Solana module not available: {e}")

# Secondary Market Scanner (optional)
SECONDARY_MODULE_AVAILABLE = False
try:
    from secondary_scanner.secondary_market import SecondaryScanner
    SECONDARY_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Secondary market scanner not available: {e}")

# Activity Scanner (2025-12-29) - CU-Efficient Secondary Activity Detection
ACTIVITY_SCANNER_AVAILABLE = False
try:
    from secondary_activity_scanner import SecondaryActivityScanner
    from activity_integration import ActivityIntegration
    ACTIVITY_SCANNER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Activity scanner not available: {e}")

# Off-Chain Screener (2025-12-29) - RPC-Saving Off-Chain Gatekeeper
OFFCHAIN_SCREENER_AVAILABLE = False
try:
    from offchain.integration import OffChainScreenerIntegration
    from offchain_config import get_offchain_config, is_offchain_enabled
    OFFCHAIN_SCREENER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Off-chain screener not available: {e}")

# Trading Module (2025-12-31) - Auto-Trading Integration
TRADING_MODULE_AVAILABLE = False
try:
    from trading.trade_executor import TradeExecutor
    from trading.wallet_manager import WalletManager
    from trading.okx_client import OKXDexClient
    from trading.position_tracker import PositionTracker
    from trading.db_handler import TradingDB
    from trading.config_manager import ConfigManager as TradingConfig
    from trading.telegram_trading import TelegramTrading
    TRADING_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Trading module not available: {e} (Install 'solders' for Solana support)")

init(autoreset=True)

def print_alert(token_data, score_data):
    # Alert level emojis for console
    alert_emojis = {
        "INFO": "🟦",
        "WATCH": "🟨",
        "TRADE-EARLY": "🟧",
        "TRADE": "🟥",
        None: "⚫"
    }
    
    alert_level = score_data.get('alert_level')
    emoji = alert_emojis.get(alert_level, "⚫")
    
    # Get chain prefix (defaults to [BASE] for backward compatibility)
    chain_prefix = token_data.get('chain_prefix', '[BASE]')
    
    print(f"\n{Fore.CYAN}{'='*50}")
    
    # Show chain prefix and alert level
    if alert_level:
        print(f"{emoji} {Fore.MAGENTA}{chain_prefix} [{alert_level} ALERT]{Style.RESET_ALL}")
    else:
        print(f"{Fore.MAGENTA}{chain_prefix}{Style.RESET_ALL}")
    
    print(f"{Fore.YELLOW}Token Name: {Fore.WHITE}{token_data.get('name')} ({token_data.get('symbol')})")
    print(f"{Fore.YELLOW}Address: {Fore.WHITE}{token_data.get('address')}")
    print(f"{Fore.YELLOW}Age: {Fore.WHITE}{token_data.get('age_minutes'):.1f} min")
    print(f"{Fore.YELLOW}Liquidity: {Fore.WHITE}${token_data.get('liquidity_usd'):,.0f}")
    
    score_color = Fore.GREEN if score_data['score'] >= 75 else (Fore.YELLOW if score_data['score'] >= 60 else Fore.RED)
    print(f"{Fore.YELLOW}Score: {score_color}{score_data['score']}/100")
    
    if score_data['risk_flags']:
        print(f"{Fore.RED}Risk Flags: {', '.join(score_data['risk_flags'])}")
    else:
        print(f"{Fore.GREEN}Risk Flags: None")
        
    print(f"{Fore.YELLOW}Verdict: {score_color}{score_data['verdict']}")
    print(f"{Fore.CYAN}{'='*50}\n")

async def main():
    parser = argparse.ArgumentParser(description="Multi-Chain Meme Token Monitor")
    parser.add_argument("--simulate", action="store_true", help="Run with simulated data")
    parser.add_argument("--chains", nargs='+', default=['base'], 
                        help="Chains to monitor (base, ethereum, blast, solana). Default: base")
    parser.add_argument("--all-chains", action="store_true", 
                        help="Enable all configured chains from chains.yaml")
    parser.add_argument("--sniper-mode", action="store_true",
                        help="Enable HIGH RISK sniper mode for early token detection")
    parser.add_argument("--running-mode", action="store_true",
                        help="Enable running token scanner for post-launch rally detection")
    parser.add_argument("--solana-only", action="store_true",
                        help="Only monitor Solana (Pump.fun, Raydium, Jupiter)")
    parser.add_argument("--offchain", action="store_true",
                        help="Enable off-chain screener (GeckoTerminal + Auto-Trading)")
    args = parser.parse_args()

    # Import multi-chain components
    from multi_scanner import MultiChainScanner
    from config import CHAIN_CONFIGS, get_enabled_chains
    
    # Import TRADE-EARLY config  
    from trade_early_config import (
        get_trade_early_config, 
        is_trade_early_enabled,
        check_upgrade_eligibility
    )

    # Import Auto-Upgrade Integration
    from upgrade_integration import UpgradeIntegration
    from config import (
        PRIORITY_DETECTOR_CONFIG,
        SMART_WALLET_CONFIG, 
        AUTO_UPGRADE_ENGINE_CONFIG
    )

    if args.simulate:
        print(f"{Fore.MAGENTA}STARTING SIMULATION MODE...")
        scanner = BaseScanner(web3_provider=None, factory_address=None)
        analyzer = TokenAnalyzer(web3_provider=None)
        scorer = TokenScorer()
        
        mock_tokens = scanner.get_mock_data()
        
        for token in mock_tokens:
            time.sleep(1)
            # In simulation mode, analyzer just passes through
            analysis = token  # Already has all fields
            score_result = scorer.score_token(analysis)
            print_alert(token, score_result)
            
        print(f"{Fore.MAGENTA}SIMULATION COMPLETE.")
    else:
        # LIVE MODE - Multi-Chain
        
        # Determine which chains to enable
        if args.all_chains:
            enabled_chains = get_enabled_chains()
            if not enabled_chains:
                print(f"{Fore.YELLOW}No chains enabled in chains.yaml! Please enable at least one chain.")
                return
        else:
            enabled_chains = [c.lower() for c in args.chains]
        
        print(f"{Fore.GREEN}🚀 Multi-Chain Meme Token Monitor")
        print(f"{Fore.CYAN}📡 Target Chains: {', '.join([c.upper() for c in enabled_chains])}\n")
        
        # Initialize Telegram notifier
        notifier = TelegramNotifier()
        
        # Initialize Error Monitor
        error_monitor = ErrorMonitor(notifier, cooldown_seconds=300)

        # Initialize Auto-Upgrade Integration (TRADE -> SNIPER)
        upgrade_integration = UpgradeIntegration({
            'priority_detector': PRIORITY_DETECTOR_CONFIG,
            'smart_wallet': SMART_WALLET_CONFIG,
            'auto_upgrade': AUTO_UPGRADE_ENGINE_CONFIG
        })
        
        # Send startup notification
        startup_features = {
            'Market Intelligence': MARKET_INTEL_AVAILABLE,
            'Solana Module': SOLANA_MODULE_AVAILABLE,
            'Secondary Market Scanner': SECONDARY_MODULE_AVAILABLE,
            'Trade-Early': is_trade_early_enabled(),
            'Auto-Upgrade (Early)': AUTO_UPGRADE_ENABLED,
            'Sniper Upgrade': upgrade_integration.enabled
        }
        await error_monitor.send_startup_alert(enabled_chains, startup_features)
        
        # Initialize multi-chain scanner with error monitoring
        # Fix: Filter out Solana from MultiChainScanner as it's handled separately
        evm_chains = [c for c in enabled_chains if c != 'solana']
        scanner = MultiChainScanner(evm_chains, CHAIN_CONFIGS.get('chains', {}), error_monitor)
        
        if not scanner.adapters:
            print(f"{Fore.RED}❌ No chains connected! Check configuration and RPC endpoints.")
            return
        
        scorer = TokenScorer()
        telegram = TelegramNotifier()

        if upgrade_integration.enabled:
            print(f"{Fore.CYAN}🎯 SNIPER AUTO-UPGRADE: ENABLED")
            stats = upgrade_integration.get_monitoring_summary()
            print(f"{Fore.CYAN}    - Threshold: {AUTO_UPGRADE_ENGINE_CONFIG['upgrade_threshold']}")
            print(f"{Fore.CYAN}    - Smart Wallets: {stats['smart_wallets']} ({stats['tier1_wallets']} elite)")

        # Initialize Market Intelligence Engines
        rotation_engine = None
        pattern_memory = None
        pattern_matcher = None
        narrative_engine = None
        smart_money_engine = None
        conviction_engine = None
        
        if MARKET_INTEL_AVAILABLE:
            print(f"{Fore.CYAN}🧠 Initializing Market Intelligence...")
            # Core
            rotation_engine = RotationEngine(ROTATION_CONFIG)
            pattern_memory = PatternMemory(PATTERN_CONFIG.get('db_path'))
            pattern_matcher = PatternMatcher(pattern_memory)
            
            # Intelligence (Phase 5)
            narrative_engine = NarrativeEngine(NARRATIVE_CONFIG)
            smart_money_engine = SmartMoneyEngine(SMART_MONEY_CONFIG)
            conviction_engine = ConvictionEngine(CONVICTION_CONFIG)
            
            print(f"{Fore.CYAN}   - Rotation Engine: Ready")
            print(f"{Fore.CYAN}   - Pattern Memory: Connected ({PATTERN_CONFIG['db_path']})")
            print(f"{Fore.CYAN}   - Narrative Radar: Active")
            print(f"{Fore.CYAN}   - Smart Money: Active")
        
        
        
        # SNIPER MODE - Isolated high-risk early detection
        sniper_mode_enabled = args.sniper_mode
        sniper_engine = None
        sniper_trigger = None
        sniper_cooldown = None
        sniper_killswitch = None
        sniper_alert = None
        
        if sniper_mode_enabled:
            try:
                from sniper import (
                    SniperDetector, SniperScoreEngine, SniperTrigger,
                    SniperCooldown, SniperKillSwitch, SniperAlert,
                    enable_sniper_mode, get_sniper_config
                )
                # Enable sniper config at runtime
                enable_sniper_mode()
                config = get_sniper_config()
                
                # Initialize all sniper components
                sniper_engine = SniperScoreEngine()
                sniper_trigger = SniperTrigger()
                sniper_cooldown = SniperCooldown()
                sniper_killswitch = SniperKillSwitch()
                sniper_alert = SniperAlert()
                
                print(f"{Fore.RED}⚠️  SNIPER MODE: ENABLED (HIGH RISK - READ ONLY)")
                print(f"{Fore.RED}    - Max age: {config['max_age_minutes']} min")
                print(f"{Fore.RED}    - Min base score: {config['trigger_base_score_min']}")
                print(f"{Fore.RED}    - Sniper score threshold: {config['sniper_score_min_threshold']}/{config['sniper_score_max']}")
                print(f"{Fore.RED}    - Liquidity multiplier: {config['trigger_liquidity_multiplier']}x chain min")
                print(f"{Fore.RED}    - Allowed phases: {config['trigger_allowed_phases']}")
                print(f"{Fore.RED}    - Cooldown persistence: {config['cooldown_file']}")
                sniped_count = sniper_cooldown.get_sniped_count()
                if sniped_count > 0:
                    print(f"{Fore.RED}    - Previously sniped tokens: {sniped_count}\n")
                else:
                    print()
            except Exception as e:
                print(f"{Fore.RED}⚠️  Sniper mode failed to initialize: {e}")
                import traceback
                traceback.print_exc()
                sniper_mode_enabled = False
        
        # RUNNING MODE - Post-launch rally detection (isolated)
        running_mode_enabled = args.running_mode
        running_scanner = None
        
        if running_mode_enabled:
            try:
                from running import (
                    RunningScanner,
                    enable_running_mode,
                    get_running_config
                )
                # Enable running config at runtime
                enable_running_mode()
                running_config = get_running_config()
                
                # Initialize running scanner
                running_scanner = RunningScanner()
                
                print(f"{Fore.BLUE}🚀 RUNNING MODE: ENABLED (Post-Launch Rally Detection)")
                print(f"{Fore.BLUE}    - Min age: {running_config['filters']['min_age_minutes']} min")
                print(f"{Fore.BLUE}    - Max age: {running_config['filters']['max_age_days']} days")
                print(f"{Fore.BLUE}    - Market cap: ${running_config['filters']['min_market_cap_usd']:,} - ${running_config['filters']['max_market_cap_usd']:,}")
                print(f"{Fore.BLUE}    - Liquidity: {running_config['filters']['min_liquidity_multiplier']}x chain min")
                print(f"{Fore.BLUE}    - Score thresholds: WATCH={running_config['score_thresholds']['WATCH']}, POTENTIAL={running_config['score_thresholds']['POTENTIAL']}, TRADE={running_config['score_thresholds']['TRADE']}")
                print(f"{Fore.BLUE}    - Cooldown: {running_config['cooldown_minutes']} min\n")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Running mode failed to initialize: {e}")
                import traceback
                traceback.print_exc()
                running_mode_enabled = False
        
        # SECONDARY MARKET SCANNER - Existing pair breakout detection
        # DISABLED: Going full off-chain (GeckoTerminal only)
        secondary_scanner = None
        secondary_enabled = False  # FORCE DISABLED
        
        print(f"{Fore.YELLOW}⚠️  On-chain secondary scanner DISABLED (full off-chain mode)")
        print(f"{Fore.CYAN}💡 Using GeckoTerminal for both NEW and TRENDING coins\n")
        
        # ================================================
        # ACTIVITY SCANNER SETUP (2025-12-29)
        # DISABLED: Going full off-chain (GeckoTerminal only)
        # ================================================
        activity_integration = None  # FORCE DISABLED
        
        print(f"{Fore.YELLOW}⚠️  On-chain activity scanner DISABLED (full off-chain mode)")
        print(f"{Fore.CYAN}💡 GeckoTerminal trending pools will catch old coins with momentum\n")
        
        # ================================================
        # OFF-CHAIN SCREENER SETUP (2025-12-29)
        # ================================================
        offchain_screener = None
        if OFFCHAIN_SCREENER_AVAILABLE and is_offchain_enabled():
            try:
                offchain_config = get_offchain_config()
                
                # IMPORTANT: Off-chain screener has its own enabled_chains
                # It's independent from on-chain scanner (chains.yaml)
                # This allows Solana off-chain scanning even when on-chain is disabled
                offchain_enabled_chains = offchain_config.get('enabled_chains', ['base', 'ethereum', 'solana'])
                
                # Initialize off-chain screener with its own enabled_chains
                offchain_screener = OffChainScreenerIntegration(offchain_config)
                
                print(f"\n{Fore.GREEN}🌐 OFF-CHAIN SCREENER: ENABLED")
                print(f"{Fore.GREEN}    - Primary: DexScreener (FREE)")
                if offchain_config.get('dextools_enabled'):
                    print(f"{Fore.GREEN}    - Secondary: DEXTools (API key required)")
                print(f"{Fore.GREEN}    - Chains: {', '.join([c.upper() for c in offchain_enabled_chains])}")
                print(f"{Fore.GREEN}    - Target: ~95% noise reduction")
                print(f"{Fore.GREEN}    - RPC savings: < 5k calls/day\n")
                
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Off-chain screener failed to initialize: {e}")
                import traceback
                traceback.print_exc()
                offchain_screener = None
        else:
            if not OFFCHAIN_SCREENER_AVAILABLE:
                print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Off-chain screener module not available")
            elif not is_offchain_enabled():
                print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Off-chain screener disabled in config")
        
        
        # SOLANA MODULE - Isolated Solana chain handling
        solana_enabled = False
        solana_scanner = None
        solana_score_engine = None
        solana_sniper = None
        solana_running = None
        solana_alert = None
        
        # Check if Solana is in enabled chains or --solana-only flag
        solana_requested = 'solana' in enabled_chains or args.solana_only
        
        if solana_requested and SOLANA_MODULE_AVAILABLE:
            try:
                # Get Solana config from chains.yaml
                solana_config = CHAIN_CONFIGS.get('chains', {}).get('solana', {})
                
                if solana_config.get('enabled', False):
                    # Initialize Solana components
                    solana_scanner = SolanaScanner(solana_config)
                    solana_score_engine = SolanaScoreEngine(solana_config)
                    solana_sniper = SolanaSniperDetector(solana_config)
                    solana_running = SolanaRunningDetector(solana_config)
                    solana_alert = SolanaAlert()
                    
                    # Connect scanner
                    if solana_scanner.connect():
                        solana_enabled = True
                        print(f"{Fore.MAGENTA}🟣 SOLANA MODULE: ENABLED")
                        print(f"{Fore.MAGENTA}    - Sources: Pump.fun, Raydium, Jupiter")
                        print(f"{Fore.MAGENTA}    - Sniper: {'ENABLED' if solana_sniper.is_enabled() else 'DISABLED'}")
                        print(f"{Fore.MAGENTA}    - Running: {'ENABLED' if solana_running.is_enabled() else 'DISABLED'}")
                        print(f"{Fore.MAGENTA}    - Min liquidity: ${solana_config.get('min_liquidity_usd', 20000):,}\n")
                    else:
                        print(f"{Fore.YELLOW}⚠️  Solana scanner failed to connect")
                else:
                    print(f"{Fore.YELLOW}⚠️  Solana is disabled in chains.yaml")
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Solana module failed to initialize: {e}")
                import traceback
                traceback.print_exc()
        elif solana_requested and not SOLANA_MODULE_AVAILABLE:
            print(f"{Fore.YELLOW}⚠️  Solana requested but module not available")
        
        # TRADE-EARLY Enhanced Config
        
        # ================================================
        # TRADING MODULE INITIALIZATION (2025-12-31)
        # ================================================
        trade_executor = None
        position_tracker = None
        
        if TRADING_MODULE_AVAILABLE:
            try:
                print(f"\n{Fore.CYAN}🤖 TRADING MODULE: INITIALIZING...")
                
                # Check if trading is enabled in config
                if TradingConfig.is_trading_enabled():
                    # 1. Initialize Database
                    trading_db = TradingDB()
                    
                    # 2. Initialize Wallet Manager
                    wallet_manager = WalletManager()
                    
                    # Import Wallets from Environment
                    import os
                    pk_evm = os.getenv('PRIVATE_KEY_EVM')
                    if pk_evm:
                        if wallet_manager.import_wallet_evm(pk_evm, 'base'):
                            print(f"{Fore.GREEN}    - EVM Wallet: CONNECTED")
                        wallet_manager.import_wallet_evm(pk_evm, 'ethereum')
                    
                    pk_sol = os.getenv('PRIVATE_KEY_SOLANA')
                    sol_enabled = TradingConfig.is_chain_enabled('solana')
                    if pk_sol and sol_enabled:
                         if wallet_manager.import_wallet_solana(pk_sol):
                              print(f"{Fore.GREEN}    - Solana Wallet: CONNECTED")
                    elif sol_enabled and not pk_sol:
                         print(f"{Fore.RED}    - Solana Enabled but NO KEY found in .env!")
                    
                    # 3. Initialize OKX Client
                    okx_client = OKXDexClient()
                    
                    # 4. Initialize Position Tracker
                    position_tracker = PositionTracker(trading_db)
                    
                    # 5. Initialize Trade Executor
                    trade_executor = TradeExecutor(
                        wallet_manager=wallet_manager,
                        okx_client=okx_client,
                        position_tracker=position_tracker
                    )
                    
                    print(f"{Fore.GREEN}    - Status: ENABLED")
                    print(f"{Fore.GREEN}    - Budget: ${TradingConfig.get_config()['trading']['budget_per_trade_usd']}")
                    print(f"{Fore.GREEN}    - Auto-TP/SL: ENABLED")
                    print(f"{Fore.GREEN}    - Chains: {', '.join([c.upper() for c in ['base', 'ethereum', 'solana'] if TradingConfig.is_chain_enabled(c)])}")
                else:
                    print(f"{Fore.YELLOW}    - Status: DISABLED in trading_config.py")
            
            except Exception as e:
                print(f"{Fore.RED}⚠️  Trading module initialization failed: {e}")
                import traceback
                traceback.print_exc()

        # START POSITION MONITORING TASK
        async def run_position_monitor():
            if not (trade_executor and position_tracker and okx_client): return
            print(f"{Fore.CYAN}👀 Position Monitor task started")
            
            while True:
                try:
                    await asyncio.sleep(10)  # Check every 10 seconds
                    
                    positions = position_tracker.get_open_positions()
                    if not positions: continue
                    
                    for pos in positions:
                        try:
                            # 0. CHECK MANUAL SELL (Balance Check)
                            # Detect if user sold tokens externally to close position in DB
                            if trade_executor and trade_executor.wm:
                                try:
                                    # GRACE PERIOD: Skip for new positions (< 2 minutes old)
                                    # This prevents false positives when transaction is still confirming
                                    from datetime import datetime
                                    if 'timestamp' in pos:
                                        try:
                                            pos_time = datetime.fromisoformat(pos['timestamp'])
                                            age_seconds = (datetime.now() - pos_time).total_seconds()
                                            if age_seconds < 120:  # Less than 2 minutes
                                                # Skip manual sell check for brand new positions
                                                pass
                                            else:
                                                # Check if position was manually sold
                                                # Get current token balance
                                                current_balance = trade_executor.wm.get_token_balance(pos['chain'], pos['token_address'])
                                                
                                                # If valid balance (>=0) and < 5% of entry amount (meaning >95% sold)
                                                if current_balance >= 0 and current_balance < (pos['entry_amount'] * 0.05):
                                                    print(f"{Fore.YELLOW}⚠️  Detected MANUAL SELL for {pos['token_address']} (Bal: {current_balance})")
                                                    position_tracker.force_close_position(pos['id'], reason="MANUAL_SELL_DETECTED")
                                                    
                                                    if telegram and telegram.enabled:
                                                        await telegram.send_message_async(
                                                            f"⚠️ *MANUAL SELL DETECTED* 🕵️\n"
                                                            f"Token: `{pos['token_address']}`\n"
                                                            f"Action: Closing Position in DB.\n"
                                                            f"Status: MONITORING STOPPED 🛑"
                                                        )
                                                    continue # Stop monitoring this position
                                        except:
                                            pass
                                except Exception as bal_e:
                                    # Ignore balance check errors (e.g. RPC fail) to not disrupt monitoring
                                    pass

                            # 1. Prepare Native Token Address for Quote
                            native_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
                            decimals = 18
                            native_price = 3300.0 # Approx ETH price
                            
                            if pos['chain'] == 'solana':
                                native_token = "So11111111111111111111111111111111111111112"
                                decimals = 9
                                native_price = 190.0 # Approx SOL price
                            
                            # 2. Get Quote for SELLING (Token -> Native)
                            # Input amount is the amount we hold (entry_amount)
                            # Must convert float to int string
                            amount_in = str(int(pos['entry_amount']))
                            
                            quote = await okx_client.get_quote(
                                chain=pos['chain'],
                                from_token=pos['token_address'],
                                to_token=native_token,
                                amount=amount_in,
                                slippage=0.01
                            )
                            
                            current_val_usd = 0
                            
                            if quote:
                                # 3. Calculate Valuation
                                # toTokenAmount is raw output amount
                                raw_out = float(quote.get('toTokenAmount', '0'))
                                real_out = raw_out / (10 ** decimals)
                                current_val_usd = real_out * native_price
                            else:
                                print(f"{Fore.RED}⚠️  No quote for {pos['token_address']} - Assuming Liquidity Gone (Val=0)")
                            
                            # 4. Calculate PnL
                            entry_usd = float(pos['entry_value_usd'])
                            if entry_usd <= 0: entry_usd = 1 # Avoid div by zero
                            
                            pnl_pct = ((current_val_usd - entry_usd) / entry_usd) * 100
                            
                            # 5. Get Exit Strategy Config
                            exit_config = TradingConfig.get_config().get('exit_strategy', {})
                            if not exit_config.get('enabled', False):
                                continue  # Skip if exit strategy disabled
                            
                            tp_pct = exit_config.get('take_profit_percent', 100)
                            sl_pct = exit_config.get('stop_loss_percent', -30)
                            liq_drop_threshold = exit_config.get('emergency_exit_liq_drop', 0.50)
                            
                            # 6. RUGPULL DETECTION: Liquidity Monitoring
                            # Compare current liquidity vs entry liquidity
                            rugpull_detected = False
                            if 'entry_liquidity_usd' in pos and pos['entry_liquidity_usd']:
                                entry_liq = float(pos['entry_liquidity_usd'])
                                if entry_liq > 0:
                                    # Get current liquidity from DexScreener or Quote
                                    # For now, we infer from quote slippage
                                    # If quote fails repeatedly, assume liquidity gone
                                    if not quote and current_val_usd < entry_usd * 0.1:
                                        # Quote failed + value dropped >90% = likely rugpull
                                        rugpull_detected = True
                                        print(f"{Fore.RED}🚨 RUGPULL DETECTED! Liquidity removed or token dead")
                            
                            # 7. EXECUTE EXIT DECISIONS
                            should_sell = False
                            sell_reason = ""
                            sell_percentage = 100  # Default: sell all
                            
                            if rugpull_detected:
                                should_sell = True
                                sell_reason = f"🚨 RUGPULL (Liquidity Gone)"
                                sell_percentage = 100
                            elif pnl_pct <= sl_pct:
                                should_sell = True
                                sell_reason = f"🛑 STOP-LOSS ({pnl_pct:.1f}%)"
                                sell_percentage = 100
                            elif pnl_pct >= tp_pct:
                                should_sell = True
                                sell_reason = f"💰 TAKE-PROFIT (+{pnl_pct:.1f}%)"
                                sell_percentage = 50  # Secure 50%, let 50% ride
                            
                            if should_sell:
                                print(f"{Fore.YELLOW}    📤 {sell_reason} triggered for pos {pos['id']}")
                                
                                # Calculate sell amount
                                if sell_percentage == 100:
                                    sell_amount = int(pos['entry_amount'])
                                    new_status = 'CLOSED'
                                else:
                                    sell_amount = int(pos['entry_amount'] * (sell_percentage / 100))
                                    new_status = 'MOONBAG'
                                
                                # Execute sell
                                success, msg = await trade_executor.execute_sell(
                                    pos['chain'], 
                                    pos['token_address'], 
                                    sell_amount, 
                                    pos['id'],
                                    new_status=new_status
                                )
                                
                                # Send Telegram notification
                                if telegram and telegram.enabled:
                                    if success:
                                        profit_amt = current_val_usd * (sell_percentage / 100) - entry_usd * (sell_percentage / 100)
                                        await telegram.send_message_async(
                                            f"{'🚨' if rugpull_detected else '💰'} *AUTO-EXIT EXECUTED*\n"
                                            f"--------------------------------\n"
                                            f"Reason: {sell_reason}\n"
                                            f"Token: `{pos['token_address'][:8]}...`\n"
                                            f"Entry: ${entry_usd:.2f}\n"
                                            f"Exit: ${current_val_usd:.2f}\n"
                                            f"PnL: {pnl_pct:+.1f}% (${profit_amt:+.2f})\n"
                                            f"Sold: {sell_percentage}%\n"
                                            f"Status: {new_status}"
                                        )
                                    else:
                                        # Sell failed - critical alert
                                        
                                        # FORCE CLOSE Logic for Dead/Rugpulled Tokens
                                        # If we can't sell because liquidity is gone, we must free up the slot
                                        force_closed_msg = "**MANUAL INTERVENTION REQUIRED**"
                                        
                                        if rugpull_detected or "Insufficient liquidity" in str(msg) or "SimulateTransaction" in str(msg) or ("Failed to get swap data" in str(msg) and pnl_pct < -50):
                                            try:
                                                print(f"{Fore.RED}💀 RUGPULL CONFIRMED: Force closing pos {pos['id']} in DB to free slot")
                                                # Use the position_tracker instance from outer scope
                                                # Need to ensure correct method call. force_close_position is in PositionTracker.
                                                if hasattr(position_tracker, 'force_close_position'):
                                                    position_tracker.force_close_position(pos['id'], reason="RUGPULL_DEAD")
                                                    force_closed_msg = "🚫 Position Force Closed (Dead Token). Slot Freed."
                                            except Exception as fc_e:
                                                print(f"Error force closing: {fc_e}")

                                        await telegram.send_message_async(
                                            f"🚨 *AUTO-EXIT FAILED*\n"
                                            f"--------------------------------\n"
                                            f"Reason: {sell_reason}\n"
                                            f"Token: `{pos['token_address'][:8]}...`\n"
                                            f"Error: {msg}\n"
                                            f"Action: {force_closed_msg}"
                                        )
                        except Exception as mon_e:
                            print(f"{Fore.YELLOW}⚠️  Error monitoring pos {pos.get('id')}: {mon_e}")
                            
                except Exception as e:
                    print(f"{Fore.RED}⚠️  Position monitor loop error: {e}")
                    await asyncio.sleep(10)


        trade_early_config = None
        if is_trade_early_enabled():
            trade_early_config = get_trade_early_config()
            print(f"{Fore.CYAN}🔄 TRADE-EARLY: ENABLED")
            print(f"{Fore.CYAN}    - Score range: {trade_early_config['score_range']}")
            print(f"{Fore.CYAN}    - Max age: {trade_early_config['max_age_minutes']} min")
            print(f"{Fore.CYAN}    - Upgrade conditions: momentum + {trade_early_config['upgrade_conditions']['liquidity_growth_pct']}% liq growth + {trade_early_config['upgrade_conditions']['score_increase']} score increase\n")
        
        # Display configuration
        if telegram.enabled:
            print(f"{Fore.GREEN}📱 Telegram alerts: ENABLED\n")
        else:
            print(f"{Fore.YELLOW}📱 Telegram alerts: DISABLED (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env)\n")
        
        # AUTO-UPGRADE TRACKING for TRADE-EARLY → TRADE
        # Structure: {token_address: {token_data, score_data, chain_config, registered_time, initial_liquidity, initial_score}}
        upgrade_pending = {}
        
        if AUTO_UPGRADE_ENABLED:
            print(f"{Fore.CYAN}🔄 Auto-upgrade: ENABLED")
            print(f"{Fore.CYAN}    - Cooldown: {AUTO_UPGRADE_COOLDOWN_SECONDS}s between upgrades")
            print(f"{Fore.CYAN}    - Max wait: {AUTO_UPGRADE_MAX_WAIT_MINUTES} min for momentum confirmation\n")


        # TRADING MODULE INITIALIZATION
        trade_executor = None
        if TRADING_MODULE_AVAILABLE:
            try:
                # 1. Initialize DB
                trading_db = TradingDB()
                
                # 2. Init Config Manager
                # (Static class, no init needed)
                
                # 3. Request Private Key (Simulated/Env)
                # Ideally load from .env using os.getenv("PRIVATE_KEY_BASE_EVM") etc.
                import os
                
                wm = WalletManager()
                
                # Load Wallet - EVM (Base/ETH)
                pk_evm = os.getenv("PRIVATE_KEY_EVM") or os.getenv("PRIVATE_KEY_BASE")
                if pk_evm:
                    wm.import_wallet_evm(pk_evm, 'base')
                    wm.import_wallet_evm(pk_evm, 'ethereum')
                    
                # Load Wallet - Solana
                pk_sol = os.getenv("PRIVATE_KEY_SOLANA")
                if pk_sol:
                    wm.import_wallet_solana(pk_sol)
                    
                # 4. Init Components
                okx_client = OKXDexClient()
                pt = PositionTracker(trading_db)
                trade_executor = TradeExecutor(wm, okx_client, pt)
                telegram_trading = TelegramTrading(trading_db)
                
                if TradingConfig.is_trading_enabled():
                    print(f"{Fore.GREEN}🤖 AUTO-TRADING: ENABLED")
                    print(f"{Fore.GREEN}    - Chains: {', '.join([c for c,d in TradingConfig.get_config()['chains'].items() if d['enabled']])}")
                    print(f"{Fore.GREEN}    - Budget: ${TradingConfig.get_budget()} per trade")
                else:
                    print(f"{Fore.YELLOW}🤖 AUTO-TRADING: DISABLED (enable in trading_config.py)")
                    
            except Exception as e:
                print(f"{Fore.RED}⚠️  Trading module init failed: {e}")
                import traceback
                traceback.print_exc()

        
        # Display chain-specific thresholds
        print(f"{Fore.CYAN}📊 Chain Thresholds:")
        for chain_name in scanner.adapters.keys():
            chain_config = scanner.get_chain_config(chain_name)
            thresholds = chain_config.get('alert_thresholds', {})
            min_liq = chain_config.get('min_liquidity_usd', 0)
            print(f"{Fore.CYAN}  [{chain_name.upper()}]:")
            print(f"{Fore.CYAN}    - Min Liquidity: ${min_liq:,}")
            print(f"{Fore.CYAN}    - INFO: {thresholds.get('INFO', 40)}, WATCH: {thresholds.get('WATCH', 60)}, TRADE: {thresholds.get('TRADE', 75)}")
        
        print(f"\n{Fore.GREEN}🔍 Scanning for new pairs... (Ctrl+C to stop)\n")
        
        try:
            # =========================================================================
            # ASYNC ARCHITECTURE: Queue + Producers + Consumer
            # =========================================================================
            
            queue = asyncio.Queue()
            tasks = []
            
            # Start Position Monitor Task
            if trade_executor:
                 tasks.append(asyncio.create_task(run_position_monitor(), name="position-monitor"))
            
            # 1. Start MultiChainScanner (EVM) in background tasks
            # MultiChainScanner now manages its own isolated tasks per chain
            # DISABLED: Not cost-effective - high CU usage, zero alerts
            # await scanner.start_async(queue)
            print(f"{Fore.YELLOW}⚠️  On-chain scanner DISABLED (saving CU costs)")
            print(f"{Fore.CYAN}💡 Using off-chain screener only (DexScreener)")
            
            # 2. Solana Producer Task
            async def run_solana_producer():
                if not (solana_enabled and solana_scanner): return
                print(f"{Fore.MAGENTA}🟣 Solana scanner task started (Source: Modules)")
                
                while True:
                    try:
                        # Yield control to event loop
                        await asyncio.sleep(0.1)
                        
                        # Run async scan directly (no thread wrapper needed)
                        # Enforce 45s timeout for the entire scan cycle
                        try:
                            tokens = await asyncio.wait_for(
                                solana_scanner.scan_new_pairs_async(),
                                timeout=45.0
                            )
                        except asyncio.TimeoutError:
                            print(f"{Fore.YELLOW}⚠️  [SOL] Scan timed out (>45s)")
                            tokens = []
                        
                        if tokens:
                            print(f"{Fore.MAGENTA}🟣 [SOL] Received {len(tokens)} candidates from scanner")
                            for t in tokens:
                                t['chain'] = 'solana'  # Ensure chain tag
                                await queue.put(t)
                                
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️  [SOL] Loop error: {e}")
                        await asyncio.sleep(5)

            if solana_enabled:
                tasks.append(asyncio.create_task(run_solana_producer(), name="solana-producer"))

            # 2.5. Secondary Market Scanner Producer Task
            async def run_secondary_producer():
                if not secondary_enabled: return
                print(f"{Fore.BLUE}🔍 Secondary market scanner task started (Event-Driven)")
                
                try:
                    from modules.global_block_events import EventBus, BlockSnapshot
                    from modules.market_heat import MarketHeatEngine
                    
                    active_chains = 0
                    for chain_name, sec_scanner in secondary_scanners.items():
                        try:
                            # Use existing adapter logic or fallback to scanner web3
                            adapter = scanner.get_adapter(chain_name)
                            w3 = adapter.w3 if adapter else sec_scanner.web3
                            
                            # Note: GlobalBlockService is already started by MultiChainScanner
                            heat_engine = MarketHeatEngine.get_instance(chain_name)
                            
                            # FIX: Capture loop variables in default args to avoid closure bug
                            async def on_secondary_block(snapshot: BlockSnapshot, c_name=chain_name, s_scanner=sec_scanner, h_engine=heat_engine):
                                try:
                                    # MARKET HEAT GATE
                                    if h_engine.is_cold():
                                        return
                                    
                                    if not s_scanner.is_enabled():
                                        return
                                        
                                    try:
                                        signals = await s_scanner.scan_all_pairs(target_block=snapshot.block_number)
                                        
                                        if signals:
                                            print(f"{Fore.BLUE}🎯 [SECONDARY][{c_name.upper()}] {len(signals)} breakout signals detected")
                                            # Record activity (lower weight for secondary)
                                            h_engine.record_activity(weight=2)
                                            
                                            for signal in signals:
                                                # Add chain info and put in main queue for processing
                                                signal['chain'] = c_name
                                                signal['signal_type'] = 'secondary_market'
                                                await queue.put(signal)
                                                
                                                # Send secondary alert
                                                if telegram.enabled:
                                                    telegram.send_secondary_alert(signal)
                                                    
                                    except Exception as scan_e:
                                        print(f"{Fore.YELLOW}⚠️  [SECONDARY] {c_name.upper()} scan error: {scan_e}")

                                except Exception as e:
                                    print(f"{Fore.YELLOW}⚠️  [SECONDARY] Handler error: {e}")
                            
                            EventBus.subscribe(f"NEW_BLOCK_{chain_name.upper()}", on_secondary_block)
                            active_chains += 1
                            print(f"{Fore.BLUE}✅ [SECONDARY] Subscribed to {chain_name.upper()}")
                        
                        except Exception as e:
                            print(f"{Fore.YELLOW}⚠️  [SECONDARY] Setup error for {chain_name}: {e}")
                    
                    if active_chains == 0:
                        print(f"{Fore.YELLOW}⚠️  [SECONDARY] No active chains connected")
                        
                    while True:
                        await asyncio.sleep(60)
                        
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️  [SECONDARY] Fatal producer error: {e}")
                    # Fallback
                    while True:
                        await asyncio.sleep(30)

            if secondary_enabled:
                tasks.append(asyncio.create_task(run_secondary_producer(), name="secondary-producer"))

            # 2.75. Activity Scanner Producer Task (2025-12-29)
            async def run_activity_producer():
                """Event-driven activity scanner"""
                if not ACTIVITY_SCANNER_AVAILABLE or not activity_integration:
                    return
                
                print(f"{Fore.CYAN}🔥 Activity scanner task started (Event-Driven)")
                
                try:
                    from modules.global_block_events import EventBus, BlockSnapshot
                    from modules.market_heat import MarketHeatEngine
                    
                    # Setup listeners for each chain
                    active_chains = 0
                    for chain_name in activity_integration.scanners.keys():
                        try:
                            adapter = scanner.get_adapter(chain_name)
                            if not adapter: 
                                continue
                                
                            # Note: GlobalBlockService is already started by MultiChainScanner
                            heat_engine = MarketHeatEngine.get_instance(chain_name)
                            
                            # Define handler
                            # FIX: Capture loop variables in default args
                            async def on_activity_block(snapshot: BlockSnapshot, c_name=chain_name, h_engine=heat_engine):
                                try:
                                    # MARKET HEAT GATE (Rule #6)
                                    # If COLD -> DISABLED, unless Smart Wallet activity is being tracked
                                    has_priority = activity_integration.has_smart_wallet_targets(c_name)
                                    
                                    if h_engine.is_cold() and not has_priority:
                                        target_block = 0 # Dummy usage to avoid lint error if needed
                                        return # Skip scan if market is cold and no priority targets
                                    
                                    # Scan specific chain on this block
                                    signals = activity_integration.scan_chain_activity(c_name, snapshot.block_number)
                                    
                                    if signals:
                                        # Record activity (Heat Up)
                                        h_engine.record_activity(weight=5)
                                        
                                        print(f"{Fore.CYAN}🎯 [ACTIVITY][{c_name.upper()}] {len(signals)} signals detected in block {snapshot.block_number}")
                                        
                                        for signal in signals:
                                            should_force = activity_integration.should_force_enqueue(signal)
                                            
                                            if should_force or signal.get('activity_score', 0) >= 60:
                                                enriched_data = activity_integration.process_activity_signal(signal)
                                                await queue.put(enriched_data)
                                                
                                                pool_addr = signal.get('pool_address', 'UNKNOWN')
                                                print(f"{Fore.CYAN}🔥 [ACTIVITY] Enqueued: {pool_addr[:10]}... (score: {signal.get('activity_score', 0)})")
                                                
                                                if telegram.enabled and should_force:
                                                    telegram.send_activity_alert(signal)
                                                    
                                except Exception as e:
                                    print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Handler error: {e}")

                            # Subscribe
                            EventBus.subscribe(f"NEW_BLOCK_{chain_name.upper()}", on_activity_block)
                            active_chains += 1
                            print(f"{Fore.CYAN}✅ [ACTIVITY] Subscribed to {chain_name.upper()} block feed")
                            
                        except Exception as e:
                             print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Setup error for {chain_name}: {e}")
                    
                    if active_chains == 0:
                        print(f"{Fore.YELLOW}⚠️  [ACTIVITY] No active chains connected")
                    
                    # Keep task alive
                    while True:
                        await asyncio.sleep(60)
                        
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Fatal producer error: {e}")
                    # Fallback loop if event system fails
                    while True:
                        await asyncio.sleep(30)
            
            if ACTIVITY_SCANNER_AVAILABLE and activity_integration:
                tasks.append(asyncio.create_task(run_activity_producer(), name="activity-producer"))
                print(f"{Fore.GREEN}✅ Activity scanner producer added to task list")

            # 2.8. Off-Chain Screener Producer Task (2025-12-29) - RPC Savings
            async def run_offchain_producer():
                """
                Producer task for off-chain screener.
                Reads normalized pairs from off-chain APIs and enqueues for processing.
                """
                if not offchain_screener:
                    return
                
                print(f"{Fore.GREEN}🌐 Off-chain screener producer task started")
                
                # Start off-chain scanner background tasks
                try:
                    offchain_tasks = await offchain_screener.start()
                    print(f"{Fore.GREEN}   Started {len(offchain_tasks)} off-chain scanner tasks")
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Failed to start tasks: {e}")
                    return
                
                while True:
                    try:
                        # Get next normalized pair from off-chain screener
                        normalized_pair = await offchain_screener.get_next_pair()
                        
                        # Add metadata for consumer
                        normalized_pair['source_type'] = 'offchain'
                        normalized_pair['requires_onchain_verify'] = True
                        
                        # Enqueue for main consumer processing
                        await queue.put(normalized_pair)
                        
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Producer error: {e}")
                        await asyncio.sleep(5)
            
            if offchain_screener:
                tasks.append(asyncio.create_task(run_offchain_producer(), name="offchain-producer"))
                print(f"{Fore.GREEN}✅ Off-chain screener producer added to task list")


            # 3. Upgrade Monitor Task (Periodic)
            async def run_upgrade_monitor():
                if not upgrade_integration.enabled: return
                print(f"{Fore.CYAN}🔄 Upgrade monitor task started")
                
                while True:
                    try:
                        await asyncio.sleep(3)
                        # PROCESS PENDING UPGRADES
                        await asyncio.to_thread(
                            upgrade_integration.process_pending_upgrades,
                            telegram_notifier=telegram
                        )
                        # Output comes from inside the logic
                    except Exception as e:
                        print(f"{Fore.YELLOW}[AUTO-UPGRADE] Error: {e}")
                        await asyncio.sleep(5)

            tasks.append(asyncio.create_task(run_upgrade_monitor(), name="upgrade-monitor"))

            # 4. Event Consumer Task (Main Logic)
            async def consumer_task():
                print(f"{Fore.GREEN}✅ Event consumer started")
                
                while True:
                    # BLOCKING wait for next pair
                    pair_data = await queue.get()
                    
                    try:
                        # Determine chain type
                        chain = pair_data.get('chain', 'unknown')
                        
                        # ================================================
                        # SOLANA PROCESSING (Native On-Chain)
                        # ================================================
                        if chain == 'solana' and pair_data.get('source_type') != 'offchain':
                            sol_token = pair_data
                            try:
                                token_address = sol_token.get('token_address', '')
                                sol_prefix = "[SOL]"
                                
                                # Score the token
                                sol_score_result = solana_score_engine.calculate_score(sol_token)
                                score = sol_score_result.get('score', 0)
                                verdict = sol_score_result.get('verdict', 'SKIP')
                                
                                # Log detection
                                print(f"{Fore.MAGENTA}🟣 {sol_prefix} Token: {sol_token.get('name', 'UNKNOWN')} | Score: {score} | Verdict: {verdict}")
                                
                                # Trigger TRADE logic for Solana if verdict is TRADE
                                if verdict == 'TRADE' and upgrade_integration.enabled:
                                    upgrade_integration.register_trade(sol_token, sol_score_result)
                                    print(f"{Fore.CYAN}[AUTO-UPGRADE] {sol_prefix} {sol_token.get('name', 'UNKNOWN')}: Registered for SNIPER upgrade monitoring")
                                
                                # SOLANA SNIPER CHECK
                                if solana_sniper and solana_sniper.is_enabled():
                                    sniper_result = solana_sniper.check_sniper_eligibility(sol_token)
                                    
                                    if sniper_result.get('eligible'):
                                        if solana_alert:
                                            alert_sent = solana_alert.send_sniper_alert(sol_token, sniper_result)
                                            if alert_sent:
                                                solana_sniper.mark_alerted(token_address)
                                                print(f"{Fore.MAGENTA}🔥 {sol_prefix} SNIPER ALERT SENT! Score: {sniper_result.get('sniper_score', 0)}")
                                
                                # SOLANA RUNNING CHECK
                                if solana_running and solana_running.is_enabled():
                                    running_result = solana_running.check_running_eligibility(
                                        sol_token, 
                                        solana_scanner.jupiter
                                    )
                                    
                                    if running_result.get('eligible'):
                                        if solana_alert:
                                            alert_sent = solana_alert.send_running_alert(sol_token, running_result)
                                            if alert_sent:
                                                solana_running.mark_alerted(token_address)
                                                print(f"{Fore.MAGENTA}🏃 {sol_prefix} RUNNING ALERT SENT! Phase: {running_result.get('phase')}")
                                
                                print(f"{Fore.MAGENTA}🏃 {sol_prefix} RUNNING ALERT SENT! Phase: {running_result.get('phase')}")
                                
                            except Exception as sol_token_e:
                                print(f"{Fore.YELLOW}⚠️  [SOL] Token processing error: {sol_token_e}")
                        
                        # ================================================
                        # OFF-CHAIN PAIR PROCESSING (2025-12-29)
                        # ================================================
                        elif pair_data.get('source_type') == 'offchain':
                            try:
                                chain_name = pair_data.get('chain', 'unknown')
                                chain_prefix = f"[{chain_name.upper()}]"
                                pair_address = pair_data.get('pair_address', 'UNKNOWN')
                                
                                print(f"{Fore.GREEN}🌐 {chain_prefix} [OFFCHAIN] {pair_data.get('token_symbol', 'UNKNOWN')} | Pair: {pair_address[:10]}...")
                                
                                # Extract off-chain score
                                offchain_score = pair_data.get('offchain_score', 0)
                                
                                # Get scoring config
                                scoring_config = offchain_screener.config.get('scoring', {})
                                verify_threshold = scoring_config.get('verify_threshold', 60)
                                offchain_weight = scoring_config.get('offchain_weight', 0.6)
                                onchain_weight = scoring_config.get('onchain_weight', 0.4)
                                
                                print(f"{Fore.GREEN}    Off-chain score: {offchain_score:.1f} (threshold: {verify_threshold})")
                                
                                # Check if we should trigger on-chain verification
                                if offchain_score >= verify_threshold:
                                    print(f"{Fore.GREEN}    🔍 Triggering on-chain verification...")
                                    
                                    # Get chain adapter
                                    adapter = scanner.get_adapter(chain_name)
                                    if not adapter and chain_name != 'solana':
                                        print(f"{Fore.YELLOW}    ⚠️  No adapter for {chain_name}, skipping RPC verify")
                                        continue

                                    # 1. ANALYZE ON-CHAIN
                                    onchain_analysis = {}
                                    if chain_name == 'solana':
                                        # Solana - use solana_scanner if available or fallback to off-chain data
                                        # Currently Solana scoring is mostly off-chain driven in this branch
                                        if solana_scanner:
                                             # Try to get fresh enrichment if possible
                                             onchain_analysis = await solana_scanner._create_unified_event_async_wrapper(pair_data) or {}
                                    else:
                                        # EVM - use full TokenAnalyzer
                                        try:
                                            analyzer = TokenAnalyzer(adapter=adapter)
                                            onchain_analysis = analyzer.analyze_token(pair_data)
                                        except Exception as e:
                                            print(f"{Fore.YELLOW}    ⚠️  On-chain analysis error: {e}")
                                            onchain_analysis = {}

                                    if onchain_analysis:
                                        # 2. SCORE ON-CHAIN
                                        chain_config = None
                                        if chain_name != 'solana':
                                            chain_config = scanner.get_chain_config(chain_name)
                                            onchain_score_data = scorer.score_token(onchain_analysis, chain_config)
                                            onchain_score = onchain_score_data.get('score', 0)
                                        else:
                                            # Solana scoring
                                            if solana_score_engine:
                                                onchain_score_data = solana_score_engine.calculate_score(onchain_analysis)
                                                onchain_score = onchain_score_data.get('score', 0)
                                            else:
                                                # Fallback if module disabled - assume pass if offchain good
                                                onchain_score = offchain_score
                                                onchain_score_data = {'score': onchain_score, 'verdict': 'OFFCHAIN_ONLY', 'risk_flags': []}

                                        # 3. COMBINED SCORING (Rule: Weight off-chain and on-chain)
                                        final_score = (offchain_score * offchain_weight) + (onchain_score * onchain_weight)
                                        
                                        print(f"{Fore.GREEN}    📊 Final Score: {final_score:.1f} (Off: {offchain_score:.0f}, On: {onchain_score:.0f})")
                                    else:
                                        # FALLBACK: On-chain verification unavailable/failed
                                        # Use off-chain score only
                                        print(f"{Fore.YELLOW}    ⚠️  On-chain verification unavailable, using off-chain score only")
                                        final_score = offchain_score
                                        onchain_score_data = {'score': offchain_score, 'verdict': 'OFFCHAIN_ONLY', 'risk_flags': []}
                                        print(f"{Fore.GREEN}    📊 Final Score: {final_score:.1f} (Off-chain Only)")
                                    
                                    # 4. DECISION & ALERT
                                    check_score = final_score
                                    
                                    # Get thresholds safely
                                    chain_config = None
                                    if chain_name != 'solana':
                                        try:
                                            chain_config = scanner.get_chain_config(chain_name)
                                        except:
                                            pass
                                    
                                    if chain_config:
                                        thresholds = chain_config.get('alert_thresholds', {})
                                    elif solana_score_engine:
                                        thresholds = solana_score_engine.get_thresholds()
                                    else:
                                        # Default fallback thresholds
                                        thresholds = {'INFO': 40, 'WATCH': 60, 'TRADE': 75}
                                    
                                    # Use TradingConfig as authoritative source for TRADING threshold
                                    trade_threshold = TradingConfig.get_config()['trading'].get('min_signal_score', thresholds.get('TRADE', 75))
                                    
                                    if check_score >= trade_threshold:
                                        print(f"{Fore.GREEN}    🚀 TRADE SIGNAL VALIDATED!")
                                        onchain_score_data['verdict'] = 'TRADE'
                                        onchain_score_data['score'] = check_score
                                        # Send updated alert if needed or just log
                                        # Send updated alert if needed or just log
                                        if telegram.enabled:
                                            await telegram.send_message_async(f"🚀 *FINAL VALIDATION PASSED*\n{pair_data.get('token_symbol')} ({chain_name.upper()})\nFinal Score: {check_score:.1f}\nStatus: RPC VERIFIED ✅")

                                        # AUTO-TRADING EXECUTION
                                        if trade_executor and TradingConfig.is_trading_enabled():
                                            try:
                                                # SECURITY GUARD: Deep Check (Holders & Risk)
                                                risk_score = 50
                                                risk_level = 'UNKNOWN'
                                                
                                                try:
                                                    # Helper for telegram escape
                                                    def esc(t): return str(t).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                                                    
                                                    sniff_w3 = adapter.w3 if (chain_name != 'solana' and adapter) else None
                                                    ts_analyzer = TokenSnifferAnalyzer(sniff_w3, chain_name)
                                                    
                                                    # Get external liquidity from DexScreener data SAFE PARSING
                                                    dex_liq = 0.0
                                                    raw_liq = pair_data.get('liquidity', 0)
                                                    if isinstance(raw_liq, dict):
                                                        dex_liq = float(raw_liq.get('usd', 0))
                                                    else:
                                                        try:
                                                            dex_liq = float(raw_liq)
                                                        except:
                                                            dex_liq = 0.0
                                                    
                                                    sec_data = ts_analyzer.analyze_comprehensive(
                                                        pair_data['token_address'], 
                                                        external_liquidity_usd=dex_liq
                                                    )
                                                    
                                                    # 1. SCORE-BASED SECURITY CHECK (New 0-100 System)
                                                    risk_score = sec_data.get('risk_score', 100)
                                                    risk_level = sec_data.get('risk_level', 'FAIL')
                                                    
                                                    # DYNAMIC THRESHOLD from Config
                                                    # Default to 60 (allow WARN) if not set, but user requested 30 (SAFE only)
                                                    max_allowed_score = TradingConfig.get_config()['risk'].get('max_risk_score', 60)
                                                    
                                                    # Helper to format details breakdown
                                                    raw_details = sec_data.get('contract_analysis', {}).get('details', [])
                                                    # Filter out the summary headers we added (RugCheck Base Score..., Final Risk Score...)
                                                    filtered_details = [d for d in raw_details if 'Base Score' not in d and 'Final Risk' not in d]
                                                    formatted_breakdown = "\n".join([f"• {d}" for d in filtered_details])
                                                    if not formatted_breakdown: formatted_breakdown = "• No specific flags detected"
                                                    
                                                    # THRESHOLD CHECK
                                                    if risk_score > max_allowed_score:
                                                        print(f"{Fore.RED}    ❌ BLOCKED BY SECURITY: Risk Score {risk_score}/100 ({risk_level}) > Config Limit {max_allowed_score}")
                                                        
                                                        if telegram.enabled:
                                                            await telegram.send_message_async(
                                                                f"⛔ *AUTO-BUY BLOCKED*\n"
                                                                f"Token: `{esc(pair_data.get('token_symbol'))}`\n"
                                                                f"Reason: Risk Score {risk_score}/100 > Limit {max_allowed_score}\n"
                                                                f"Status: {risk_level} (Config Restricted)\n\n"
                                                                f"*Risk Analysis:*\n"
                                                                f"{esc(formatted_breakdown)}"
                                                            )
                                                        continue
                                                        
                                                    # WARNING LEVEL (If allowed by config)
                                                    elif risk_score > 30:
                                                        print(f"{Fore.YELLOW}    ⚠️ SECURITY WARNING: Risk Score {risk_score}/100 ({risk_level}) - Proceeding (Allowed > 30)")
                                                        for d in filtered_details:
                                                            if '⚠️' in d or '🚨' in d:
                                                                print(f"{Fore.YELLOW}       {d}")

                                                    # 3. LP INTENT RISK CHECK (NEW - Behavioral)
                                                    from lp_intent_analyzer import LPIntentAnalyzer
                                                    lp_analyzer = LPIntentAnalyzer(chain_name)
                                                    lp_risk = lp_analyzer.calculate_risk(pair_data)
                                                    
                                                    # ULTRA-AGGRESSIVE: Block even moderate risk (30 vs original 70)
                                                    if lp_risk['risk_score'] > 30:
                                                        print(f"{Fore.RED}    ❌ BLOCKED BY LP INTENT: Risk Score {lp_risk['risk_score']:.0f}/100 ({lp_risk['risk_level']}) [ULTRA-STRICT]")
                                                        if telegram.enabled:
                                                            await telegram.send_message_async(
                                                                f"⛔ *AUTO-BUY BLOCKED*\n"
                                                                f"Token: `{esc(pair_data.get('token_symbol'))}`\n"
                                                                f"Reason: LP Risk Too High ({lp_risk['risk_score']:.0f}/100 > 30)\n"
                                                                f"Behavioral Risk: {lp_risk['risk_level']}"
                                                            )
                                                        continue
                                                    
                                                    elif lp_risk['risk_score'] > 20:
                                                        print(f"{Fore.YELLOW}    ⚠️ LP INTENT WARNING: Risk Score {lp_risk['risk_score']:.0f}/100 ({lp_risk['risk_level']}) - Proceeding with caution")
                                                    
                                                    top10_pct = sec_data.get('holder_analysis', {}).get('top10_holders_percent', 0)
                                                    print(f"{Fore.GREEN}    ✅ Security Check Passed (Risk: {risk_level}, Top 10: {top10_pct:.1f}%, LP Intent: {lp_risk['risk_score']:.0f}/100)")
                                                except Exception as sec_e:
                                                    print(f"{Fore.YELLOW}    ⚠️ Security Check Skipped: {sec_e}")
                                                    formatted_breakdown = "• Security Check Skipped (Error)"

                                                # FOMO GUARD: Check Volatility
                                                # Access config safely
                                                fomo_limit = 100.0
                                                try:
                                                    fomo_limit = offchain_screener.config['scoring_v3'].get('max_price_change_5m', 100.0)
                                                except:
                                                    pass
                                                    
                                                current_pump = pair_data.get('price_change_m5', 0)
                                                
                                                if current_pump > fomo_limit:
                                                    print(f"{Fore.YELLOW}    🛡️  FOMO GUARD: Skipped (Pump +{current_pump:.1f}% > {fomo_limit}%)")
                                                    if telegram.enabled:
                                                        await telegram.send_message_async(
                                                            f"🛡️ *AUTO-BUY SKIPPED*\n"
                                                            f"Token: {pair_data.get('token_symbol')}\n"
                                                            f"Reason: Pumped +{current_pump:.0f}% in 5m (Risky)\n"
                                                            f"Guard Limit: +{fomo_limit:.0f}%"
                                                        )
                                                    continue

                                                # ============================================================
                                                # 🛡️ PRE-FLIGHT CHECK: Live Liquidity Verification (Anti-Flash Rug)
                                                # ============================================================
                                                try:
                                                    print(f"{Fore.CYAN}    🛡️  Running Pre-Flight Liquidity Check...")
                                                    pf_start = time.time()
                                                    pf_url = f"https://api.dexscreener.com/latest/dex/tokens/{pair_data.get('token_address')}"
                                                    pf_resp = requests.get(pf_url, timeout=5)
                                                    
                                                    if pf_resp.status_code == 200:
                                                        pf_data = pf_resp.json()
                                                        pf_pairs = pf_data.get('pairs', [])
                                                        if pf_pairs:
                                                            # Find the target pair or use the most liquid one
                                                            pf_pair = pf_pairs[0]
                                                            pf_liq_usd = float(pf_pair.get('liquidity', {}).get('usd', 0))
                                                            pf_liq_quote = float(pf_pair.get('liquidity', {}).get('quote', 0))
                                                            pf_mkt_cap = float(pf_pair.get('marketCap', 0))
                                                            pf_symbol = pf_pair.get('baseToken', {}).get('symbol', 'UNKNOWN')
                                                            
                                                            # Threshold: $2,000 (Flash Rug Detection)
                                                            PRE_FLIGHT_MIN_LIQ = 2000.0
                                                            
                                                            # BONDING CURVE EXCEPTION:
                                                            # Pump.fun/Meteora/LaunchLab tokens often return 0 USD Liq but valid Quote Liq (SOL) or Market Cap.
                                                            is_bonding_curve = any(x in pf_pair.get('url', '').lower() or x in pf_pair.get('dexId', '').lower() for x in ['pump', 'meteora', 'launchlab'])
                                                            
                                                            # Calculate implied liquidity if USD is 0 but we have Quote (SOL)
                                                            # Assume SOL ~$150 (Safe conservative estimate or just check unit count)
                                                            # If > 10 SOL in pool, it's roughly > $1500
                                                            if pf_liq_usd == 0 and is_bonding_curve and pf_liq_quote > 10:
                                                                 print(f"       ⚠️ Bonding Curve Detected (USD 0). Using Quote Liq: {pf_liq_quote:.2f} SOL")
                                                                 pf_liq_usd = pf_liq_quote * 150 # Estimate
                                                            
                                                            print(f"       Live Check: Liq ${pf_liq_usd:,.0f} | MC ${pf_mkt_cap:,.0f} (Threshold: ${PRE_FLIGHT_MIN_LIQ:,.0f})")
                                                            
                                                            # Fail if Liq < Threshold AND Market Cap < Threshold (Double Fail)
                                                            # For BC, if Liq is 0 but MC is healthy (>5k), we trust MC.
                                                            if pf_liq_usd < PRE_FLIGHT_MIN_LIQ and pf_mkt_cap < 5000:
                                                                print(f"{Fore.RED}    ❌ PRE-FLIGHT FAIL: Liquidity ${pf_liq_usd:,.0f} & MC ${pf_mkt_cap:,.0f} Too Low (Flash Rug?)")
                                                                if telegram.enabled:
                                                                    await telegram.send_message_async(
                                                                        f"🛡️ *PRE-FLIGHT ABORTED*\n"
                                                                        f"Token: {pair_data.get('token_symbol')}\n"
                                                                        f"Reason: Liquidity Dropped to ${pf_liq_usd:,.0f}\n"
                                                                        f"Status: FLASH RUG DETECTED ❌"
                                                                    )
                                                                continue # ABORT BUY
                                                    else:
                                                        print(f"{Fore.YELLOW}    ⚠️ Pre-Flight API Error ({pf_resp.status_code}) - Proceeding with caution")
                                                except Exception as pf_e:
                                                     print(f"{Fore.YELLOW}    ⚠️ Pre-Flight Check Error: {pf_e}")
                                                
                                                # Verify Pre-Flight duration
                                                print(f"       Pre-Flight Time: {(time.time() - pf_start)*1000:.0f}ms")

                                                print(f"{Fore.CYAN}    🤖 Attempting Auto-Buy (via State Machine)...")
                                                
                                                # PHASE 3: STATE MACHINE EXECUTION
                                                # New logic: PROBE -> WATCH -> SCALE -> EXIT
                                                # Replaces direct trade_executor.execute_buy
                                                
                                                # Instantiate State Machine (Lazy init or ideally moved to setup)
                                                # For now, instantiated here to ensure fresh config
                                                from trading.trading_state_machine import TradingStateMachine
                                                state_machine = TradingStateMachine(trade_executor, position_tracker)
                                                
                                                # Initialize fallback values (Prevent UnboundLocalError)
                                                tx_success = False
                                                msg = "State Machine Failed (Unknown)"

                                                sm_success, sm_msg = await state_machine.process_signal(
                                                    chain=chain_name,
                                                    token_address=pair_data.get('token_address'),
                                                    signal_score=check_score,
                                                    market_data=pair_data
                                                )
                                                
                                                if sm_success:
                                                    # State Machine handles its own logging/actions
                                                    # We just confirm the handoff
                                                    tx_success = True
                                                    msg = sm_msg  # Use the specific success message
                                                else:
                                                    # Capture failure reason
                                                    msg = sm_msg
                                                    print(f"{Fore.RED}    ❌ AUTO-TRADE FAILED: {msg}")
                                                
                                                if tx_success:
                                                    print(f"{Fore.GREEN}    ✅ AUTO-TRADE SUCCESSFUL (Tx: {msg})")
                                                    if telegram.enabled:
                                                        risk_status_emoji = "✅" if risk_score <= 30 else "⚠️"
                                                        
                                                        # Use the formatted breakdown generated above
                                                        # If it wasn't generated (e.g. exception), define default
                                                        if 'formatted_breakdown' not in locals(): formatted_breakdown = "• Analysis unavailable"
                                                        
                                                        await telegram.send_message_async(
                                                            f"🤖 *AUTO-BUY EXECUTED* ✅\n"
                                                            f"--------------------------------\n"
                                                            f"Token: {pair_data.get('token_symbol')} `{pair_data.get('token_address')}`\n"
                                                            f"Chain: {chain_name.upper()}\n"
                                                            f"Signal Score: {check_score:.1f}\n"
                                                            f"Risk Status: {risk_score:.0f}/100 {risk_status_emoji} ({risk_level})\n"
                                                            f"Tx Hash: {msg}\n"
                                                            f"Status: MOONING SOON? 🚀\n\n"
                                                            f"*Risk Analysis Details:*\n"
                                                            f"{esc(formatted_breakdown)}"
                                                        )
                                                else:
                                                    print(f"{Fore.RED}    ❌ AUTO-TRADE FAILED: {msg}")
                                                    
                                                    # Parse error for better user feedback
                                                    error_category = "Unknown Error"
                                                    error_action = "Check logs"
                                                    
                                                    if "Position limit reached" in msg:
                                                        error_category = "🚫 Position Limit"
                                                        error_action = "Close existing positions or increase max_open_positions in config"
                                                    elif "Slippage" in msg or "0x177e" in str(msg):
                                                        error_category = "📈 High Slippage"
                                                        error_action = "Token too volatile or low liquidity. Skipped for safety."
                                                    elif any(x in msg.lower() for x in ["insufficient funds", "insufficient lamports", "broadcast failed", "0x1"]):
                                                        error_category = "💰 Insufficient Balance / Gas"
                                                        error_action = "Top up wallet with more SOL/ETH (Need > 0.01 SOL)"
                                                    elif "disabled" in msg.lower():
                                                        error_category = "⛔ Chain/Trading Disabled"
                                                        error_action = "Enable in trading_config.py"
                                                    elif "Failed to fetch swap data" in msg:
                                                        error_category = "🔌 API Connection"
                                                        error_action = "DEX API temporarily unavailable"
                                                    
                                                    if telegram.enabled:
                                                        # Escape special chars to prevent Telegram parse errors
                                                        def esc(t): return str(t).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                                                        
                                                        alert_title = "❌ *AUTO-BUY BLOCKED*"
                                                        if "disabled" in msg.lower():
                                                            alert_title = "⚠️ *SIGNAL SKIPPED* (Chain Disabled)"
                                                            
                                                        await telegram.send_message_async(
                                                            f"{alert_title}\n"
                                                            f"--------------------------------\n"
                                                            f"Token: {esc(pair_data.get('token_symbol'))}\n"
                                                            f"Chain: {esc(chain_name.upper())}\n"
                                                            f"Category: {esc(error_category)}\n"
                                                            f"Reason: {esc(msg[:100])}\n"
                                                            f"Action: {esc(error_action)}"
                                                        )
                                            except Exception as trade_e:
                                                print(f"{Fore.RED}    ❌ Auto-trade error: {trade_e}")
                                        
                                    print(f"{Fore.GREEN}    ⚡ RPC VERIFICATION COMPLETE")
                                    
                                    # Display off-chain statistics every 10 pairs
                                    if offchain_screener.stats.get('passed_to_queue', 0) % 10 == 0:
                                        stats = offchain_screener.get_stats()
                                        pipeline = stats.get('pipeline', {})
                                        if pipeline.get('total_raw_pairs', 0) > 0:
                                            noise_reduction = (1 - pipeline['passed_to_queue'] / pipeline['total_raw_pairs']) * 100
                                            print(f"{Fore.CYAN}    📊 [OFFCHAIN STATS] Noise reduction: {noise_reduction:.1f}% | Passed: {pipeline['passed_to_queue']}/{pipeline['total_raw_pairs']}")
                                    
                                else:
                                    print(f"{Fore.YELLOW}    ⏭️  Skipped (score < {verify_threshold}) - RPC calls SAVED!")
                                
                            except Exception as offchain_e:
                                print(f"{Fore.YELLOW}⚠️  [OFFCHAIN] Processing error: {offchain_e}")
                                import traceback
                                traceback.print_exc()
                        
                        # ================================================
                        # SECONDARY MARKET PROCESSING
                        # ================================================
                        elif pair_data.get('signal_type') == 'secondary_market':
                            try:
                                signal = pair_data
                                chain_name = signal.get('chain', 'unknown')
                                chain_prefix = f"[{chain_name.upper()}]"
                                
                                print(f"{Fore.BLUE}🎯 {chain_prefix} Secondary signal: {signal.get('token_address', 'UNKNOWN')[:8]}... - {signal.get('state', 'UNKNOWN')}")
                                
                                # The signal has already been alerted in the producer task
                                # Here we could add additional processing if needed
                                
                            except Exception as sec_e:
                                print(f"{Fore.YELLOW}⚠️  [SECONDARY] Signal processing error: {sec_e}")
                        
                        # ================================================
                        # ACTIVITY-DETECTED TOKEN PROCESSING (2025-12-29)
                        # ================================================
                        elif pair_data.get('activity_override') or pair_data.get('source') == 'secondary_activity':
                            try:
                                chain_name = pair_data.get('chain', 'unknown')
                                chain_prefix = f"[{chain_name.upper()}]"
                                pool_address = pair_data.get('pool_address', pair_data.get('pair_address', 'UNKNOWN'))
                                
                                print(f"{Fore.CYAN}🔥 {chain_prefix} [ACTIVITY] Processing pool {pool_address[:10]}...")
                                
                                # Get chain config
                                chain_config = scanner.get_chain_config(chain_name)
                                
                                # Import activity integration helpers
                                from activity_integration import apply_activity_context_to_analysis
                                
                                # Get token address (may be empty initially)
                                token_address = pair_data.get('token_address')
                                
                                if token_address:
                                    # Run full analysis
                                    try:
                                        # Get adapter
                                        adapter = scanner.get_adapter(chain_name)
                                        if not adapter:
                                            print(f"{Fore.YELLOW}   ⚠️  No adapter for {chain_name}")
                                            continue
                                        
                                        # Analyze token
                                        analyzer = TokenAnalyzer(adapter=adapter)
                                        analysis = analyzer.analyze_token({'address': token_address, 'pair_address': pool_address})
                                        
                                        if analysis:
                                            # Apply activity context
                                            enriched_analysis = apply_activity_context_to_analysis(
                                                analysis,
                                                pair_data
                                            )
                                            
                                            # Score with activity overrides
                                            score_data = scorer.score_token(enriched_analysis, chain_config)
                                            
                                            # Log result
                                            print(f"{Fore.CYAN}   Score: {score_data.get('score', 0)} | Verdict: {score_data.get('verdict', 'UNKNOWN')}")
                                            
                                            # Send activity alert if qualifies
                                            if score_data.get('alert_level'):
                                                telegram.send_activity_alert(pair_data, score_data)
                                                print(f"{Fore.GREEN}📨 {chain_prefix} [ACTIVITY] Alert sent!")
                                        else:
                                            print(f"{Fore.YELLOW}   ⚠️  Analysis failed")
                                    
                                    except Exception as analyze_e:
                                        print(f"{Fore.YELLOW}⚠️  {chain_prefix} [ACTIVITY] Analysis error: {analyze_e}")
                                
                                else:
                                    # No token address yet - send initial activity alert
                                    print(f"{Fore.YELLOW}   Token address not resolved - sending initial alert")
                                    telegram.send_activity_alert(pair_data)
                            
                            except Exception as act_e:
                                print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Processing error: {act_e}")
                                import traceback
                                traceback.print_exc()
                                
                                
                        # ================================================
                        # EVM PROCESSING
                        # ================================================
                        else:
                            try:
                                chain_name = pair_data.get('chain', 'base')
                                chain_prefix = pair_data.get('chain_prefix', '[UNKNOWN]')
                                chain_config = scanner.get_chain_config(chain_name)
                                min_liquidity = chain_config.get('min_liquidity_usd', 0)
                                
                                print(f"{Fore.CYAN}{chain_prefix} New pair detected! Analyzing...")
                                
                                # Get the adapter for this chain
                                adapter = scanner.get_adapter(chain_name)
                                if not adapter:
                                    # Fallback: Try lowercase
                                    adapter = scanner.get_adapter(chain_name.lower())
                                
                                if not adapter:
                                    print(f"{Fore.RED}⚠️  {chain_prefix} No adapter available for chain '{chain_name}'")
                                    continue
                                
                                # Analyze the token using the chain adapter
                                analyzer = TokenAnalyzer(adapter=adapter)
                                analysis = analyzer.analyze_token(pair_data)
                                
                                # Skip if analysis failed
                                if analysis is None:
                                    print(f"{Fore.RED}⚠️  {chain_prefix} Analysis failed, skipping token")
                                    continue
                                
                                # Check for liquidity spike (cached, no eth_call)
                                if adapter.heat_engine and analysis.get('liquidity_usd', 0) > 50000:
                                    adapter.heat_engine.set_liquidity_spike_flag()
                                
                                # MARKET INTEL: Pattern Matching & Rotation Bias
                                pattern_insight = None
                                rotation_bonus = 0
                                narrative_insight = None
                                smart_money_insight = None
                                conviction_result = None
                                
                                if MARKET_INTEL_AVAILABLE:
                                    # 1. Check Rotation Bias
                                    rotation_bonus = rotation_engine.get_score_bonus(chain_name)
                                    rotation_data = rotation_engine.get_rotation_insight()
                                    rotation_data['is_aligned'] = (chain_name.lower() == str(rotation_data.get('rotation_bias', '')).lower())
                                    
                                    # 2. Pattern Matching
                                    pattern_insight = pattern_matcher.match_token(analysis)
                                    analysis['pattern_insight'] = pattern_insight
                                    
                                    # 3. Narrative Detection
                                    narrative_insight = narrative_engine.analyze_token(analysis)
                                    analysis['narrative_insight'] = narrative_insight
                                    
                                    # 4. Smart Money Analysis
                                    smart_money_insight = smart_money_engine.analyze_token_wallets([]) 
                                    analysis['smart_money_insight'] = smart_money_insight
                                    
                                    # 5. Final Conviction Score
                                    conviction_result = conviction_engine.calculate_conviction(
                                        narrative_insight,
                                        smart_money_insight,
                                        rotation_data,
                                        pattern_insight
                                    )
                                    analysis['conviction_insight'] = conviction_result
                                    
                                    if pattern_insight['confidence_label'] != 'NO_MATCH':
                                        sim = pattern_insight['pattern_similarity']
                                        print(f"{Fore.MAGENTA}🧠 {chain_prefix} Pattern Match: {sim}% similarity")
                                        
                                    if narrative_insight['confidence'] > 0.5:
                                        print(f"{Fore.MAGENTA}🧠 {chain_prefix} Narrative: {narrative_insight['narrative']}")

                                analysis['rotation_bonus'] = rotation_bonus
                                
                                # Chain-specific liquidity filter
                                if analysis.get('liquidity_usd', 0) < min_liquidity:
                                    print(f"{Fore.YELLOW}⚠️  {chain_prefix} Low liquidity (${analysis.get('liquidity_usd'):,.0f} < ${min_liquidity:,})")
                                    continue
                                
                                # Record shortlisted candidate for heat calculation
                                if adapter.heat_engine:
                                    adapter.heat_engine.record_shortlisted_candidate()
                                
                                # Score it
                                score_result = scorer.score_token(analysis, chain_config)

                                # ACTIVITY SCANNER ADMISSION (2025-12-29)
                                # Feed high-value pools into the hunter-mode scanner
                                if activity_integration:
                                    activity_integration.track_new_pool(analysis, score_result)
                                
                                # Apply bias
                                if rotation_bonus > 0:
                                    score_result['original_score'] = score_result['score']
                                    score_result['score'] = min(100, score_result['score'] + rotation_bonus)
                                    if 'breakdown' not in score_result: score_result['breakdown'] = {}
                                    score_result['breakdown']['rotation_bonus'] = rotation_bonus
                                    print(f"{Fore.MAGENTA}🔥 {chain_prefix} Rotation Bias: +{rotation_bonus}")
                                
                                # Feed event to Rotation Engine
                                if MARKET_INTEL_AVAILABLE and score_result.get('alert_level'):
                                    rotation_engine.add_event(chain_name, score_result['alert_level'], score_result['score'])
                                    
                                # Store patterns
                                if MARKET_INTEL_AVAILABLE and score_result['alert_level'] in ['TRADE', 'TRADE-EARLY']:
                                    pattern_memory.add_pattern(
                                        chain=chain_name,
                                        source=analysis.get('source', 'unknown'),
                                        initial_score=score_result['score'],
                                        liquidity=analysis.get('liquidity_usd', 0),
                                        momentum_confirmed=analysis.get('momentum_confirmed', False),
                                        holder_concentration=analysis.get('holder_risk', 0),
                                        phase=score_result['alert_level'],
                                        outcome='PENDING'
                                    )
                                
                                # Alert
                                print_alert(analysis, score_result)
                                
                                alert_level = score_result.get('alert_level')
                                if telegram.enabled and alert_level:
                                    try:
                                        if alert_level == "TRADE-EARLY":
                                            print(f"{Fore.CYAN}📱 {chain_prefix} Sending {alert_level} alert...")
                                            success = telegram.send_trade_early_alert(analysis, score_result)
                                        else:
                                            print(f"{Fore.CYAN}📱 {chain_prefix} Sending {alert_level} alert...")
                                            success = telegram.send_alert(analysis, score_result)
                                        
                                        if success:
                                            print(f"{Fore.GREEN}✅ {chain_prefix} Telegram alert sent!")
                                            # Record alert triggered for heat calculation
                                            if adapter.heat_engine:
                                                adapter.heat_engine.record_alert_triggered()
                                        else:
                                            print(f"{Fore.YELLOW}ℹ️  {chain_prefix} Alert skipped")
                                    except Exception as e:
                                        print(f"{Fore.RED}❌ {chain_prefix} Telegram error: {e}")
                                
                                # UPGRADE REGISTRATION
                                if upgrade_integration.enabled and alert_level == "TRADE":
                                    upgrade_integration.register_trade(analysis, score_result)
                                    print(f"{Fore.CYAN}[AUTO-UPGRADE] {chain_prefix} {analysis.get('name', 'UNKNOWN')}: Registered for SNIPER monitor")
                                
                                if AUTO_UPGRADE_ENABLED and score_result.get('is_trade_early', False):
                                    token_address = analysis.get('address', analysis.get('token_address', ''))
                                    if token_address and token_address.lower() not in upgrade_pending:
                                        upgrade_pending[token_address.lower()] = {
                                            'token_data': analysis,
                                            'score_data': score_result,
                                            'chain_config': chain_config,
                                            'chain_prefix': chain_prefix,
                                            'registered_time': time.time()
                                        }
                                        print(f"{Fore.CYAN}[AUTO-UPGRADE] {chain_prefix} {analysis.get('name', 'UNKNOWN')}: TRADE-EARLY registered")
                                
                                # Check upgrades
                                if AUTO_UPGRADE_ENABLED and upgrade_pending:
                                    current_time = time.time()
                                    tokens_to_remove = []
                                    for pending_addr, pending_data in upgrade_pending.items():
                                        wait_time = current_time - pending_data['registered_time']
                                        if wait_time > AUTO_UPGRADE_MAX_WAIT_MINUTES * 60:
                                            tokens_to_remove.append(pending_addr)
                                            continue
                                            
                                        upgrade_result = scorer.check_auto_upgrade(
                                            pending_data['score_data'],
                                            pending_data['token_data'],
                                            pending_data['chain_config']
                                        )
                                        if upgrade_result['can_upgrade']:
                                            # Upgraded
                                            upgraded_score = upgrade_result['upgraded_score_data']
                                            print(f"{Fore.GREEN}[AUTO-UPGRADE] ✅ UPGRADED to TRADE ({upgrade_result['upgrade_reason']})")
                                            if telegram.enabled:
                                                telegram.send_upgrade_alert(
                                                    pending_data['token_data'], pending_data['score_data'],
                                                    upgraded_score, upgrade_result
                                                )
                                            tokens_to_remove.append(pending_addr)
                                    for addr in tokens_to_remove:
                                        del upgrade_pending[addr]
                                
                                # SNIPER MODE check (simplified for async)
                                if sniper_mode_enabled and sniper_engine and sniper_alert:
                                    try:
                                        token_address = analysis.get('address', '')
                                        if not sniper_cooldown.is_token_sniped(token_address):
                                            from sniper import SniperDetector
                                            sniper_detector = SniperDetector(adapter=adapter)
                                            eligibility = sniper_detector.is_eligible(analysis)
                                            if eligibility['eligible']:
                                                # Get momentum data (from analysis if available)
                                                momentum_data = analysis.get('momentum_data', {
                                                    'momentum_confirmed': analysis.get('momentum_confirmed', False),
                                                    'momentum_score': analysis.get('momentum_score', 0),
                                                    'momentum_details': analysis.get('momentum_details', {})
                                                })
                                                
                                                # Get transaction analysis data
                                                tx_analysis = analysis.get('tx_analysis', {
                                                    'fake_pump_suspected': analysis.get('fake_pump_suspected', False),
                                                    'mev_pattern_detected': analysis.get('mev_pattern_detected', False)
                                                })
                                                
                                                # Evaluate ALL trigger conditions
                                                trigger_result = sniper_trigger.evaluate(
                                                    token_data=analysis,
                                                    score_data=score_result,
                                                    momentum=momentum_data,
                                                    tx_analysis=tx_analysis,
                                                    chain_config=chain_config
                                                )
                                                
                                                if trigger_result['trigger_sniper']:
                                                    # ALL CONDITIONS PASSED - Calculate sniper score
                                                    
                                                    # Build liquidity trend
                                                    liquidity_trend = {
                                                        'initial_liquidity': analysis.get('liquidity_usd', 0),
                                                        'current_liquidity': analysis.get('liquidity_usd', 0),
                                                        'trend': 'stable'
                                                    }
                                                    
                                                    # Build holder risk
                                                    holder_risk = {
                                                        'top10_percent': analysis.get('top10_holders_percent', 0),
                                                        'dev_flag': analysis.get('dev_activity_flag', 'SAFE'),
                                                        'mev_detected': tx_analysis.get('mev_pattern_detected', False),
                                                        'fake_pump': tx_analysis.get('fake_pump_suspected', False)
                                                    }
                                                    
                                                    # Calculate sniper score
                                                    sniper_score_data = sniper_engine.calculate_sniper_score(
                                                        base_score=score_result.get('score', 0),
                                                        momentum_data=momentum_data,
                                                        liquidity_trend=liquidity_trend,
                                                        holder_risk=holder_risk
                                                    )
                                                    
                                                    # Print sniper detection to console
                                                    print(f"{Fore.RED}🎯 {chain_prefix} [SNIPER] Age: {eligibility['token_age_minutes']:.1f}m | Score: {sniper_score_data['sniper_score']}/{sniper_score_data['max_possible']} | Risk: {sniper_score_data['risk_level']}")
                                                    
                                                    # Check if meets sniper threshold
                                                    if sniper_score_data['meets_threshold']:
                                                        # Get operator protocol
                                                        operator_protocol = sniper_engine.get_operator_protocol()
                                                        
                                                        # Send sniper alert
                                                        alert_sent = sniper_alert.send_sniper_alert(
                                                            token_data=analysis,
                                                            score_data=sniper_score_data,
                                                            trigger_result=trigger_result,
                                                            operator_protocol=operator_protocol
                                                        )
                                                        
                                                        if alert_sent:
                                                            # Mark as sniped (persistent cooldown)
                                                            sniper_cooldown.mark_token_sniped(token_address, {
                                                                'sniper_score': sniper_score_data['sniper_score'],
                                                                'chain': chain_name,
                                                                'name': analysis.get('name', 'UNKNOWN'),
                                                                'symbol': analysis.get('symbol', '???')
                                                            })
                                                            
                                                            # Register for kill switch monitoring
                                                            sniper_killswitch.register_sniper_target(token_address, {
                                                                'liquidity_usd': analysis.get('liquidity_usd', 0),
                                                                'sniper_score': sniper_score_data['sniper_score'],
                                                                'momentum_confirmed': momentum_data.get('momentum_confirmed', False),
                                                                'dev_flag': holder_risk.get('dev_flag', 'SAFE'),
                                                                'mev_detected': holder_risk.get('mev_detected', False),
                                                                'fake_pump': holder_risk.get('fake_pump', False)
                                                            })
                                                            
                                                            print(f"{Fore.RED}🔥 {chain_prefix} [SNIPER ALERT SENT] Score: {sniper_score_data['sniper_score']}")
                                                    else:
                                                        print(f"{Fore.YELLOW}🎯 {chain_prefix} [SNIPER] Score {sniper_score_data['sniper_score']} below threshold {sniper_score_data['threshold']}")
                                                else:
                                                    # Trigger conditions failed - log downgrade reason
                                                    print(f"{Fore.YELLOW}🎯 {chain_prefix} [SNIPER] Downgrade: {trigger_result['downgrade_reason'][:80]}...")
                                            else:
                                                # Basic eligibility failed (age, liquidity, etc)
                                                pass  # Skip silently - not sniper eligible
                                    except Exception as e:
                                        print(f"{Fore.YELLOW}⚠️  [SNIPER] Error: {e}")
                                
                                # RUNNING MODE check
                                if running_mode_enabled and running_scanner:
                                    try:
                                        running_scanner.process_token(analysis, score_result, chain_config)
                                    except Exception as e:
                                        print(f"{Fore.YELLOW}⚠️  [RUNNING] Error: {e}")

                            except Exception as evm_e:
                                print(f"{Fore.RED}⚠️  {pair_data.get('chain_prefix', '?')} Processing error: {evm_e}")
                    
                    except Exception as loop_e:
                        print(f"Loop error: {loop_e}")
                    finally:
                        queue.task_done()

            # PHASE 5: EVENT-DRIVEN MODE (Optional)
            # if args.event_mode: ... (Logic already in place for blocks)

            # --- INTEGRATION: ACTIVE POSITION MONITOR ---
            # Automatically start position monitoring in background
            try:
                from monitor_positions import monitor_positions
                print(f"{Fore.CYAN}🚀 Launching Integrated Position Monitor...")
                tasks.append(asyncio.create_task(monitor_positions(), name="position_monitor"))
            except ImportError:
                 print(f"{Fore.RED}⚠️ Failed to import monitor_positions (Module not found)")
            except Exception as mon_e:
                 print(f"{Fore.RED}⚠️ Failed to start Position Monitor: {mon_e}")
            # --------------------------------------------

            tasks.append(asyncio.create_task(consumer_task(), name="consumer"))
            
            # Run everything
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitoring stopped.")
            
            # Cleanup off-chain screener
            if offchain_screener:
                print(f"{Fore.CYAN}🌐 Closing off-chain screener...")
                await offchain_screener.close()

if __name__ == "__main__":
    asyncio.run(main())
