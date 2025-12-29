import argparse
import argparse
import time
import asyncio
from colorama import init, Fore, Style
from web3 import Web3
from scanner import BaseScanner
from analyzer import TokenAnalyzer
from scorer import TokenScorer
from scanner import BaseScanner
from analyzer import TokenAnalyzer
from scorer import TokenScorer
from telegram_notifier import TelegramNotifier
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
        secondary_scanner = None
        secondary_enabled = False
        
        if SECONDARY_MODULE_AVAILABLE:
            try:
                # Get global secondary scanner config
                secondary_config = CHAIN_CONFIGS.get('secondary_scanner', {})
                
                # Initialize secondary scanner for each enabled EVM chain
                secondary_scanners = {}
                for chain_name in evm_chains:
                    chain_config = CHAIN_CONFIGS.get('chains', {}).get(chain_name, {})
                    if chain_config.get('enabled', False):
                        # Get web3 provider from adapter
                        adapter = scanner.get_adapter(chain_name)
                        if adapter and hasattr(adapter, 'w3'):
                            # Merge chain config with global secondary config
                            full_config = {
                                **chain_config, 
                                'chain_name': chain_name,
                                'secondary_scanner': secondary_config
                            }
                            
                            sec_scanner = SecondaryScanner(
                                adapter.w3, 
                                full_config
                            )
                            
                            # Discover and add pairs to monitor
                            discovered_pairs = sec_scanner.discover_pairs()
                            for pair_info in discovered_pairs:
                                sec_scanner.add_pair_to_monitor(**pair_info)
                            
                            secondary_scanners[chain_name] = sec_scanner
                
                if secondary_scanners:
                    secondary_enabled = True
                    print(f"{Fore.GREEN}🚀 SECONDARY MARKET SCANNER: ENABLED")
                    for chain_name, sec_scanner in secondary_scanners.items():
                        stats = sec_scanner.get_stats()
                        print(f"{Fore.GREEN}    - {chain_name.upper()}: Monitoring {stats.get('monitored_pairs', 0)} pairs")
                    print()
                    
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Secondary scanner failed to initialize: {e}")
                import traceback
                traceback.print_exc()
                secondary_enabled = False
        
        # ================================================
        # ACTIVITY SCANNER SETUP (2025-12-29)
        # ================================================
        activity_integration = None
        if ACTIVITY_SCANNER_AVAILABLE:
            try:
                activity_integration = ActivityIntegration(enabled=True)
                
                # Register scanner for each enabled EVM chain
                for chain_name in evm_chains:
                    chain_config = CHAIN_CONFIGS.get('chains', {}).get(chain_name, {})
                    
                    # Check if secondary scanner enabled for this chain (activity scanner piggybacks on this setting)
                    if chain_config.get('secondary_scanner', {}).get('enabled', False):
                        # Get web3 provider from adapter
                        adapter = scanner.get_adapter(chain_name)
                        if adapter and hasattr(adapter, 'w3'):
                            scanner_instance = SecondaryActivityScanner(
                                web3=adapter.w3,
                                chain_name=chain_name,
                                chain_config=chain_config
                            )
                            activity_integration.register_scanner(chain_name, scanner_instance)
                            print(f"{Fore.CYAN}✅ [ACTIVITY] Registered scanner for {chain_name.upper()}")
                
                # Print status
                if activity_integration and len(activity_integration.scanners) > 0:
                    print(f"\n{Fore.CYAN}🔥 ACTIVITY SCANNER: ENABLED")
                    activity_integration.print_status()
                else:
                    print(f"{Fore.YELLOW}⚠️  [ACTIVITY] No scanners registered")
                    activity_integration = None
                    
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️  Activity scanner failed to initialize: {e}")
                import traceback
                traceback.print_exc()
                activity_integration = None
        else:
            print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Activity scanner module not available")
        
        
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
            
            # 1. Start MultiChainScanner (EVM) in background tasks
            # MultiChainScanner now manages its own isolated tasks per chain
            await scanner.start_async(queue)
            
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
                print(f"{Fore.BLUE}🔍 Secondary market scanner task started")
                
                while True:
                    try:
                        await asyncio.sleep(30)  # Scan every 30 seconds
                        
                        for chain_name, sec_scanner in secondary_scanners.items():
                            if not sec_scanner.is_enabled():
                                continue
                                
                            try:
                                signals = await sec_scanner.scan_all_pairs()
                                
                                if signals:
                                    print(f"{Fore.BLUE}🎯 [SECONDARY] {chain_name.upper()}: {len(signals)} breakout signals detected")
                                    
                                    for signal in signals:
                                        # Add chain info and put in main queue for processing
                                        signal['chain'] = chain_name
                                        signal['signal_type'] = 'secondary_market'
                                        await queue.put(signal)
                                        
                                        # Send secondary alert
                                        if telegram.enabled:
                                            telegram.send_secondary_alert(signal)
                                                
                            except Exception as e:
                                print(f"{Fore.YELLOW}⚠️  [SECONDARY] {chain_name.upper()} scan error: {e}")
                                
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️  [SECONDARY] Producer error: {e}")
                        await asyncio.sleep(30)

            if secondary_enabled:
                tasks.append(asyncio.create_task(run_secondary_producer(), name="secondary-producer"))

            # 2.75. Activity Scanner Producer Task (2025-12-29)
            async def run_activity_producer():
                """Scan for activity signals across all chains"""
                if not ACTIVITY_SCANNER_AVAILABLE or not activity_integration:
                    return
                
                print(f"{Fore.CYAN}🔥 Activity scanner task started")
                
                while True:
                    try:
                        await asyncio.sleep(30)  # Scan every 30 seconds
                        
                        # Scan all registered chains
                        signals = activity_integration.scan_all_chains()
                        
                        if signals:
                            print(f"{Fore.CYAN}🎯 [ACTIVITY] {len(signals)} signals detected")
                            
                            for signal in signals:
                                # Check DEXTools guarantee rule
                                should_force = activity_integration.should_force_enqueue(signal)
                                
                                if should_force or signal.get('activity_score', 0) >= 60:
                                    # Enrich signal with activity context
                                    enriched_data = activity_integration.process_activity_signal(signal)
                                    
                                    # Add to main queue for processing
                                    await queue.put(enriched_data)
                                    
                                    pool_addr = signal.get('pool_address', 'UNKNOWN')
                                    print(f"{Fore.CYAN}🔥 [ACTIVITY] Enqueued: {pool_addr[:10]}... (score: {signal.get('activity_score', 0)})")
                                    
                                    # Send immediate activity alert if force enqueue (high confidence)
                                    if telegram.enabled and should_force:
                                        telegram.send_activity_alert(signal)
                    
                    except Exception as e:
                        print(f"{Fore.YELLOW}⚠️  [ACTIVITY] Producer error: {e}")
                        import traceback
                        traceback.print_exc()
                        await asyncio.sleep(30)
            
            if ACTIVITY_SCANNER_AVAILABLE and activity_integration:
                tasks.append(asyncio.create_task(run_activity_producer(), name="activity-producer"))
                print(f"{Fore.GREEN}✅ Activity scanner producer added to task list")


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
                        # SOLANA PROCESSING
                        # ================================================
                        if chain == 'solana':
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

            tasks.append(asyncio.create_task(consumer_task(), name="consumer"))
            
            # Run everything
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitoring stopped.")

if __name__ == "__main__":
    asyncio.run(main())
