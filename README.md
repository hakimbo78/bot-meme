# Multi-Chain Meme Token Monitor 🚀

An AI crypto agent that monitors new meme token launches across **Base, Ethereum, Blast, and Solana** networks, scores them using predefined rules, and sends alerts - **NO trading execution, manual confirmation only**.

## ⚠️ Safety Statement

> **This system remains INFORMATIONAL-ONLY:**
> - ❌ No automated trading actions are performed
> - ❌ No wallet management or private keys
> - ❌ No transaction execution
> - ✅ All alerts require manual operator confirmation
> - ✅ Read-only blockchain monitoring
> - ✅ No buy/sell signals - only decision clarity hints

## Features

### Core Features
- 🌐 **Multi-Chain Support**: Monitor Base, Ethereum, Blast, and Solana simultaneously
- 📊 **Real-time Monitoring**: Scans DEX factories for new pair creation events
- 🎯 **Smart Scoring**: Evaluates tokens based on liquidity, security, and holder distribution
- ⚙️ **Per-Chain Configuration**: Independent thresholds and filters for each chain
- 📱 **Telegram Alerts**: Sends formatted alerts with chain prefixes for high-scoring tokens
- 🔒 **Security-First**: Integrates with GoPlus API for security checks
- 🧪 **Simulation Mode**: Test the bot with mock data before going live

### Security Audit Features (2025-12-26)
- 🔄 **Momentum Validation**: Multi-cycle confirmation (3-5 snapshots) to reduce false positives
- 🚨 **Fake Pump Detection**: Identifies rapid buy/sell patterns and wallet spam
- 🤖 **MEV Detection**: Flags gas anomalies and sandwich patterns
- 👛 **Wallet Tracking**: Monitors deployer and smart money activity
- 🔁 **Auto Re-Alert**: Smart re-alerting based on improvements (15 min cooldown)
- 📋 **Operator Hints**: Risk level, entry suggestions, confidence indicators
- 📈 **Market Phase Detection**: LAUNCH/GROWTH/MATURE phase-aware scoring


## Scoring Rules

### Base Scoring

| Criteria | Points | Description |
|----------|--------|-------------|
| Liquidity ≥ $20k | +30 | Sufficient trading volume |
| Ownership Renounced | +20 | Owner cannot modify contract |
| No Mint/Blacklist | +20 | Safe from inflation & blocking |
| Top 10 Holders ≤ 40% | +20 | Good token distribution |
| Token Age < 15 min | +10 | Fresh launch opportunity |

### Security Audit Adjustments

| Condition | Adjustment | Description |
|-----------|------------|-------------|
| Momentum Confirmed | +0-20 | Multi-cycle validation bonus |
| Momentum NOT Confirmed | Cap at 65 | Prevents false TRADE signals |
| Fake Pump Suspected | -25 | Manipulation penalty |
| MEV Pattern Detected | Force WATCH | Override to prevent false TRADE |
| Dev Activity: DUMP | Force IGNORE | Block dev dumping tokens |
| Dev Activity: WARNING | -15 | Caution penalty |
| Smart Money Involved | +10 | Positive signal bonus |

### Operator Hints (NOT buy/sell signals)

| Risk Level | Entry Suggestion | Confidence |
|------------|------------------|------------|
| HIGH | Pullback only | Snapshot only |
| MEDIUM | Wait for confirmation | Momentum confirmed |
| LOW | Standard consideration | Full validation |

**Maximum Base Score**: 100 points


## Installation

1. **Clone/Navigate to directory**:
   ```bash
   cd c:\Users\hakim\Downloads\ScriptTrading\bot-meme
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   - Copy `.env.example` to `.env`
   - Add your Telegram bot token and chat ID (optional)
   ```env
   BASE_RPC_URL=https://mainnet.base.org
   GOPLUS_API_URL=https://api.gopluslabs.io/api/v1/token_security/8453
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

## Usage

### Simulation Mode (Test First!)
```bash
python main.py --simulate
```
This runs the bot with 3 mock tokens to verify everything works.


### Live Mode - Base Only (Default, Backward Compatible)
```bash
python main.py
```
Monitors Base network only - same as previous version.

### Live Mode - Multiple Chains
```bash
python main.py --chains base ethereum
```
Monitor specific chains (base, ethereum, blast, solana).

### Live Mode - All Enabled Chains
```bash
python main.py --all-chains
```
Monitors all chains marked as `enabled: true` in `chains.yaml`.

## Output Format

```
==============================
Token Name: Based Pepe (BPEPE)
Address: 0x123...abc
Age: 5.0 min
Liquidity: $25,000
Score: 100/100
Risk Flags: None
Verdict: WATCH
==============================
```

## Telegram Integration

When enabled, the bot sends alerts like this:

```
🟢 NEW TOKEN ALERT 🟢

Token: Based Pepe (BPEPE)
Address: 0x123...abc
Score: 100/100 ✅

📊 Metrics:
• Age: 5.0 min
• Liquidity: $25,000

🔍 Risk Flags:
• None ✅

Verdict: WATCH
```

**Alert Threshold**: Tokens must score ≥70 to trigger Telegram alerts (configurable in `config.py`)

## Multi-Chain Configuration

### Enabling/Disabling Chains

Edit `chains.yaml` to control which chains are active:

```yaml
chains:
  base:
    enabled: true  # Set to false to disable
  ethereum:
    enabled: true  # Set to true to enable Ethereum monitoring
  blast:
    enabled: false # Disabled by default
  solana:
    enabled: false # Disabled by default (requires additional setup)
```

### Per-Chain Settings

Each chain has independent configuration in `chains.yaml`:

**RPC Endpoints**: Set your preferred RPC provider
```yaml
base:
  rpc_url: "https://mainnet.base.org"  # Free public RPC
ethereum:
  rpc_url: "https://eth.llamarpc.com"  # Or use Alchemy/Infura
```

**Liquidity Filters**: Adjust minimum liquidity thresholds per chain
```yaml
base:
  min_liquidity_usd: 15000  # Lower for Base memes
ethereum:
  min_liquidity_usd: 50000  # Higher for ETH (more expensive)
blast:
  min_liquidity_usd: 10000  # Even lower for Blast
```

**Alert Thresholds**: Independent scoring thresholds for each chain
```yaml
base:
  alert_thresholds:
    INFO: 40   # Base has lower barrier to entry
    WATCH: 60
    TRADE: 75

ethereum:
  alert_thresholds:
    INFO: 50   # Higher standards for ETH
    WATCH: 70
    TRADE: 85
```

### Solana Setup (Optional)

Solana support requires additional dependencies:
```bash
pip install solana solders
```

**Note**: Solana scanning is currently a placeholder. Full Raydium/Pump.fun integration requires additional implementation.

### Chain-Specific Output

All logs and alerts include chain prefixes:
- **[BASE]** - Base network tokens
- **[ETH]** - Ethereum mainnet tokens  
- **[BLAST]** - Blast network tokens
- **[SOL]** - Solana tokens

Example Telegram alert:
```
🟥 [ETH] TRADE ALERT 🟥

Token: SuperDoge (SDOGE)
Chain: [ETH]
Address: 0x123...
Score: 85/100
...
```

## Configuration

Edit `config.py` to customize:

- `TELEGRAM_SCORE_THRESHOLD`: Minimum score for alerts (default: 70)
- `SCORE_RULES`: Adjust point values for each criterion
- `UNISWAP_V2_FACTORY`: Change DEX factory address if needed

## Architecture

```
┌─────────────────┐
│  MultiScanner   │  Orchestrates multi-chain scanning
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ChainAdapters  │  Chain-specific data fetching (read-only)
│  (Base/ETH/etc) │  
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Analyzer     │  Enriches data + Security analysis
│  ┌───────────┐  │
│  │ Momentum  │  │  Multi-cycle validation
│  │ Tracker   │  │
│  ├───────────┤  │
│  │ Tx        │  │  Fake pump/MEV detection
│  │ Analyzer  │  │
│  ├───────────┤  │
│  │ Wallet    │  │  Dev/smart money tracking
│  │ Tracker   │  │
│  ├───────────┤  │
│  │ Phase     │  │  Market phase detection
│  │ Detector  │  │
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Scorer      │  SINGLE SOURCE OF TRUTH for scoring
│                 │  Applies all rules + security adjustments
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Notifier      │  Telegram dispatch with re-alert logic
│                 │  + Operator hints
└─────────────────┘
```


## Files

### Core Files
- `main.py` - Entry point and orchestration
- `multi_scanner.py` - Multi-chain orchestrator
- `analyzer.py` - Enriches token data + security analysis integration
- `scorer.py` - SINGLE SOURCE OF TRUTH for all scoring logic
- `telegram_notifier.py` - Sends Telegram alerts with re-alert support
- `config.py` - Configuration and environment variables
- `chains.yaml` - Per-chain configuration

### Security Analysis Modules (NEW)
- `momentum_tracker.py` - Multi-cycle momentum validation
- `transaction_analyzer.py` - Fake pump/MEV detection
- `wallet_tracker.py` - Dev wallet and smart money tracking
- `phase_detector.py` - Market phase classification

### Chain Adapters
- `chain_adapters/base_adapter.py` - Base adapter interface
- `chain_adapters/evm_adapter.py` - Shared EVM chain implementation
- `chain_adapters/solana_adapter.py` - Solana adapter (disabled by audit)


## Safety Features

- ✅ **Read-Only**: No trading execution or transaction signing
- ✅ **Manual Confirmation**: All decisions require human approval
- ✅ **Risk Flagging**: Clearly highlights potential dangers
- ✅ **API Rate Limiting**: Respects external API limits
- ✅ **Error Handling**: Graceful degradation on API failures

## Troubleshooting

**Can't connect to Base RPC**:
- Check your internet connection
- Verify `BASE_RPC_URL` in `.env` is correct
- Try alternative RPC: `https://base.llamarpc.com`

**Telegram alerts not sending**:
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
- Test your bot token with BotFather
- Check firewall/network restrictions

**No tokens detected**:
- Ensure you're monitoring the correct factory address
- Base can have periods of low activity
- Try simulation mode to verify bot functionality

## Disclaimer

⚠️ **This tool is for informational purposes only. Always DYOR (Do Your Own Research). Meme tokens are highly speculative and risky. Never invest more than you can afford to lose.**

## License

MIT
