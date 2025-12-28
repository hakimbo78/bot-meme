"""
Solana Utilities - Shared helpers and constants for Solana module

This module provides:
- Solana RPC connection helpers
- Program ID constants
- SOL price fetching
- Transaction parsing utilities

CRITICAL: This module must NOT import any EVM adapters.
"""
import time
import requests
from typing import Optional, Dict, Any
from functools import lru_cache

# =============================================================================
# PROGRAM IDS (Mainnet)
# =============================================================================

PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
RAYDIUM_AMM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
JUPITER_AGGREGATOR_V6 = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"

# Raydium pool related programs
RAYDIUM_LIQUIDITY_POOL_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_OPENBOOK_MARKET = "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX"

# Token programs
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# Native SOL mint
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"

# =============================================================================
# RPC ENDPOINTS
# =============================================================================

DEFAULT_RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo",  # Fallback
]

# Rate limiting
RPC_RATE_LIMIT_DELAY = 0.1  # seconds between requests
_last_rpc_call = 0

# =============================================================================
# SOL PRICE CACHE
# =============================================================================

_sol_price_cache = {
    'price': 180.0,  # Fallback price
    'timestamp': 0,
    'ttl': 60  # Cache for 60 seconds
}


def get_sol_price_usd() -> float:
    """
    Get current SOL price in USD with caching.
    
    Uses CoinGecko API with fallback to cached value.
    
    Returns:
        SOL price in USD
    """
    global _sol_price_cache
    
    now = time.time()
    if now - _sol_price_cache['timestamp'] < _sol_price_cache['ttl']:
        return _sol_price_cache['price']
    
    try:
        # CoinGecko simple price API
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "solana", "vs_currencies": "usd"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            price = data.get('solana', {}).get('usd', _sol_price_cache['price'])
            _sol_price_cache['price'] = price
            _sol_price_cache['timestamp'] = now
            return price
    except Exception as e:
        print(f"[SOLANA] ⚠️  Price fetch error: {e}")
    
    return _sol_price_cache['price']


def sol_to_usd(sol_amount: float) -> float:
    """Convert SOL amount to USD."""
    return sol_amount * get_sol_price_usd()


def usd_to_sol(usd_amount: float) -> float:
    """Convert USD amount to SOL."""
    price = get_sol_price_usd()
    return usd_amount / price if price > 0 else 0


# =============================================================================
# RPC HELPERS
# =============================================================================

def rate_limit_rpc():
    """Apply rate limiting between RPC calls."""
    global _last_rpc_call
    elapsed = time.time() - _last_rpc_call
    if elapsed < RPC_RATE_LIMIT_DELAY:
        time.sleep(RPC_RATE_LIMIT_DELAY - elapsed)
    _last_rpc_call = time.time()


def create_solana_client(rpc_url: str = None):
    """
    Create a Solana RPC client with graceful fallback.
    
    Args:
        rpc_url: Custom RPC URL or None for default
        
    Returns:
        Solana Client instance or None if dependencies missing
    """
    try:
        from solana.rpc.api import Client
        
        url = rpc_url or DEFAULT_RPC_ENDPOINTS[0]
        client = Client(url)
        
        # Test connection
        response = client.get_version()
        if response.value:
            return client
            
    except ImportError:
        print("[SOLANA] ⚠️  Solana dependencies not installed")
        return None
    except Exception as e:
        print(f"[SOLANA] ⚠️  RPC connection error: {e}")
        return None
    
    return None


# =============================================================================
# TRANSACTION PARSING
# =============================================================================

def parse_lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL (1 SOL = 1e9 lamports)."""
    return lamports / 1_000_000_000


def parse_token_amount(amount: int, decimals: int) -> float:
    """Convert raw token amount to human-readable format."""
    return amount / (10 ** decimals)


def extract_token_transfers(transaction_data: Dict) -> list:
    """
    Extract token transfers from a transaction.
    
    Args:
        transaction_data: Parsed transaction data
        
    Returns:
        List of transfer dicts with source, dest, amount, mint
    """
    transfers = []
    
    try:
        meta = transaction_data.get('meta', {})
        pre_balances = meta.get('preTokenBalances', [])
        post_balances = meta.get('postTokenBalances', [])
        
        # Build balance change map
        for post in post_balances:
            account_index = post.get('accountIndex')
            mint = post.get('mint', '')
            post_amount = int(post.get('uiTokenAmount', {}).get('amount', 0))
            
            # Find matching pre-balance
            pre_amount = 0
            for pre in pre_balances:
                if pre.get('accountIndex') == account_index and pre.get('mint') == mint:
                    pre_amount = int(pre.get('uiTokenAmount', {}).get('amount', 0))
                    break
            
            change = post_amount - pre_amount
            if change != 0:
                transfers.append({
                    'mint': mint,
                    'change': change,
                    'decimals': post.get('uiTokenAmount', {}).get('decimals', 9),
                    'owner': post.get('owner', '')
                })
                
    except Exception as e:
        print(f"[SOLANA] ⚠️  Transfer parsing error: {e}")
    
    return transfers


# =============================================================================
# SIGNATURE HELPERS
# =============================================================================

def is_valid_solana_address(address: str) -> bool:
    """
    Check if string is a valid Solana address (base58, 32-44 chars).
    
    Args:
        address: Address string to validate
        
    Returns:
        True if valid Solana address format
    """
    if not address or not isinstance(address, str):
        return False
    
    # Solana addresses are 32-44 characters base58
    if len(address) < 32 or len(address) > 44:
        return False
    
    # Base58 character set (no 0, O, I, l)
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    return all(c in base58_chars for c in address)


def shorten_address(address: str, chars: int = 4) -> str:
    """Shorten address for display: abc...xyz"""
    if not address or len(address) < chars * 2 + 3:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


# =============================================================================
# LOGGING HELPERS
# =============================================================================

def solana_log(message: str, level: str = "INFO"):
    """
    Log message with [SOLANA] prefix.
    
    Args:
        message: Log message
        level: Log level (INFO, DEBUG, WARN, ERROR)
    """
    if level == "DEBUG":
        prefix = "[SOLANA][DEBUG]"
    else:
        prefix = "[SOLANA]"
        
    if level == "WARN":
        print(f"{prefix} ⚠️  {message}", flush=True)
    elif level == "ERROR":
        print(f"{prefix} ❌ {message}", flush=True)
    else:
        print(f"{prefix} {message}", flush=True)


# =============================================================================
# TOKEN METADATA
# =============================================================================

def get_token_metadata_from_uri(uri: str) -> Optional[Dict]:
    """
    Fetch token metadata from URI (IPFS, Arweave, HTTP).
    
    Args:
        uri: Metadata URI
        
    Returns:
        Metadata dict or None
    """
    if not uri:
        return None
    
    try:
        # Convert IPFS URI to HTTP gateway
        if uri.startswith('ipfs://'):
            uri = uri.replace('ipfs://', 'https://ipfs.io/ipfs/')
        
        response = requests.get(uri, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    return None


# =============================================================================
# CONSTANTS FOR SCORING
# =============================================================================

# Buy velocity thresholds
BUY_VELOCITY_LOW = 5      # buys/min
BUY_VELOCITY_MEDIUM = 15  # buys/min
BUY_VELOCITY_HIGH = 30    # buys/min

# SOL inflow thresholds
SOL_INFLOW_LOW = 5        # SOL
SOL_INFLOW_MEDIUM = 15    # SOL
SOL_INFLOW_HIGH = 50      # SOL

# Age thresholds (seconds)
SNIPER_MAX_AGE = 120      # 2 minutes
EARLY_MAX_AGE = 600       # 10 minutes
RUNNING_MIN_AGE = 1800    # 30 minutes
RUNNING_MAX_AGE = 1209600 # 14 days

# Liquidity thresholds (USD)
MIN_LIQUIDITY_SNIPER = 5000
MIN_LIQUIDITY_TRADE = 20000
MIN_LIQUIDITY_RUNNING = 50000
