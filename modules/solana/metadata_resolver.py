"""
Solana SPL Token Metadata Resolver

Resolves token metadata via Metaplex:
- Token name and symbol
- Decimals and supply
- Metadata URI
- Caching with TTL

Used for enriching token data beyond Pump.fun detection.
"""
import time
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from functools import lru_cache

from .solana_utils import (
    TOKEN_PROGRAM_ID,
    solana_log,
    rate_limit_rpc,
    is_valid_solana_address
)

# =============================================================================
# METAPLEX CONSTANTS
# =============================================================================

METAPLEX_PROGRAM_ID = "metaqbxxUerdq28cj1RbAqKEsbh9EwMaFQBi5kLSeled"

# Metadata seed for PDA derivation
METADATA_SEED = b"metadata"


@dataclass
class TokenMetadata:
    """Resolved token metadata."""
    mint: str
    name: str
    symbol: str
    decimals: int
    supply: int
    uri: str = ""
    metadata_status: str = "RESOLVED"
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        """Convert to dict output."""
        return {
            "mint": self.mint,
            "name": self.name,
            "symbol": self.symbol,
            "decimals": self.decimals,
            "supply": self.supply,
            "uri": self.uri,
            "metadata_status": self.metadata_status,
            "timestamp": self.timestamp
        }
    
    def is_fresh(self, ttl_seconds: int = 1800) -> bool:
        """Check if metadata is still fresh."""
        return time.time() - self.timestamp < ttl_seconds


class MetadataResolver:
    """
    Resolves SPL token metadata from Metaplex.
    
    Fetches:
    - Mint account (decimals, supply)
    - Metadata PDA (name, symbol, uri)
    
    Caches results with TTL.
    """
    
    def __init__(self, client=None, cache_ttl: int = 1800):
        """
        Initialize metadata resolver.
        
        Args:
            client: Solana RPC client
            cache_ttl: Cache TTL in seconds (default 30 minutes)
        """
        self.client = client
        self.cache_ttl = cache_ttl
        self._metadata_cache: Dict[str, TokenMetadata] = {}
        self._failed_mints: Dict[str, float] = {}  # Track failed resolves
        self._skip_ttl = 300  # Don't retry failed mints for 5 minutes
    
    def set_client(self, client):
        """Update Solana RPC client."""
        self.client = client
    
    async def resolve(self, mint: str) -> Optional[TokenMetadata]:
        """
        Resolve token metadata for a mint address.
        
        Args:
            mint: Solana token mint address
            
        Returns:
            TokenMetadata or None if resolution failed
        """
        if not mint or not is_valid_solana_address(mint):
            solana_log(f"[META] Invalid mint address: {mint}", "WARN")
            return None
        
        # Check cache
        if mint in self._metadata_cache:
            cached = self._metadata_cache[mint]
            if cached.is_fresh(self.cache_ttl):
                solana_log(f"[META] Cache hit: {cached.symbol} ({cached.name})", "DEBUG")
                return cached
        
        # Check skip list (recent failures)
        if mint in self._failed_mints:
            if time.time() - self._failed_mints[mint] < self._skip_ttl:
                solana_log(f"[META] Skipping recent failure: {mint}", "DEBUG")
                return None
            else:
                # TTL expired, try again
                del self._failed_mints[mint]
        
        # Resolve metadata
        try:
            metadata = await self._fetch_metadata(mint)
            if metadata:
                self._metadata_cache[mint] = metadata
                solana_log(
                    f"[SOLANA][META] Resolved token {metadata.name} ({metadata.symbol}) "
                    f"decimals={metadata.decimals} supply={metadata.supply:,}",
                    "INFO"
                )
                return metadata
            else:
                # Failed to resolve
                self._failed_mints[mint] = time.time()
                solana_log(f"[SOLANA][META][WARN] Metadata not found for mint {mint}", "WARN")
                return None
        
        except Exception as e:
            self._failed_mints[mint] = time.time()
            solana_log(f"[META] Resolution error for {mint}: {e}", "ERROR")
            return None
    
    async def _fetch_metadata(self, mint: str) -> Optional[TokenMetadata]:
        """
        Fetch metadata from Metaplex.
        
        Steps:
        1. Fetch mint account (decimals, supply)
        2. Derive metadata PDA
        3. Fetch metadata account (name, symbol, uri)
        
        Args:
            mint: Token mint address
            
        Returns:
            TokenMetadata or None
        """
        if not self.client:
            solana_log("[META] No RPC client available", "ERROR")
            return None
        
        try:
            # Step 1: Get mint account info
            rate_limit_rpc()
            mint_info = self.client.get_account_info(mint)
            
            if not mint_info.value or not mint_info.value.data:
                return None
            
            # Parse mint account to get decimals and supply
            decimals, supply = self._parse_mint_account(mint_info.value.data)
            
            # Step 2: Derive metadata PDA
            metadata_pda = await self._derive_metadata_pda(mint)
            if not metadata_pda:
                return None
            
            # Step 3: Get metadata account
            rate_limit_rpc()
            metadata_info = self.client.get_account_info(metadata_pda)
            
            if not metadata_info.value or not metadata_info.value.data:
                return None
            
            # Parse metadata account
            name, symbol, uri = self._parse_metadata_account(metadata_info.value.data)
            
            return TokenMetadata(
                mint=mint,
                name=name or "UNKNOWN",
                symbol=symbol or "???",
                decimals=decimals,
                supply=supply,
                uri=uri or ""
            )
        
        except Exception as e:
            solana_log(f"[META] Fetch error: {e}", "DEBUG")
            return None
    
    async def _derive_metadata_pda(self, mint: str) -> Optional[str]:
        """
        Derive Metaplex metadata PDA for a mint.
        
        PDA = findProgramAddress(
            seeds = [b"metadata", METAPLEX_PROGRAM_ID, mint_pubkey],
            program_id = METAPLEX_PROGRAM_ID
        )
        
        Args:
            mint: Token mint address
            
        Returns:
            Metadata PDA address or None
        """
        try:
            from solana.publickey import PublicKey
            from solana.spl.token.core import find_program_address
            
            mint_pubkey = PublicKey(mint)
            metaplex_pubkey = PublicKey(METAPLEX_PROGRAM_ID)
            
            # Find PDA
            pda, bump = find_program_address(
                [METADATA_SEED, metaplex_pubkey.encode(), mint_pubkey.encode()],
                metaplex_pubkey
            )
            
            return str(pda)
        
        except Exception as e:
            solana_log(f"[META] PDA derivation error: {e}", "DEBUG")
            return None
    
    def _parse_mint_account(self, data: bytes) -> tuple:
        """
        Parse mint account to extract decimals and supply.
        
        Mint account structure:
        - Bytes 0-43: Account data layout header
        - Byte 44: Decimals (u8)
        - Bytes 45-48: Owner (u32, reserved)
        - Bytes 49-56: Supply (u64)
        
        Args:
            data: Raw mint account data
            
        Returns:
            (decimals, supply) tuple
        """
        try:
            if len(data) < 82:
                return (0, 0)
            
            # Decimals at byte 44
            decimals = data[44]
            
            # Supply at bytes 48-55 (u64, little-endian)
            supply_bytes = data[48:56]
            supply = int.from_bytes(supply_bytes, byteorder='little')
            
            return (decimals, supply)
        
        except Exception as e:
            solana_log(f"[META] Mint parse error: {e}", "DEBUG")
            return (0, 0)
    
    def _parse_metadata_account(self, data: bytes) -> tuple:
        """
        Parse metadata account to extract name, symbol, uri.
        
        Metadata account structure:
        - Bytes 0-1: Key (u8)
        - Bytes 1-33: Mint (Pubkey)
        - Bytes 33-65: Owner (Pubkey)
        - Bytes 65-97: Update authority (Pubkey)
        - Bytes 97-165: Name (String, 32 bytes max)
        - Bytes 165-173: Symbol length (u32)
        - Bytes 173+: Symbol (variable length string)
        - ...: URI (variable length string)
        
        Args:
            data: Raw metadata account data
            
        Returns:
            (name, symbol, uri) tuple
        """
        try:
            if len(data) < 65:
                return ("UNKNOWN", "???", "")
            
            # Name starts at byte 65, max 32 bytes
            name_section = data[65:97]
            # First 4 bytes are length (u32 little-endian)
            name_len = int.from_bytes(name_section[0:4], byteorder='little')
            name = name_section[4:4+name_len].decode('utf-8', errors='ignore').strip()
            
            # Symbol starts after name
            symbol_offset = 65 + 4 + name_len
            if symbol_offset + 4 > len(data):
                return (name or "UNKNOWN", "???", "")
            
            symbol_len = int.from_bytes(
                data[symbol_offset:symbol_offset+4],
                byteorder='little'
            )
            symbol_end = symbol_offset + 4 + symbol_len
            
            if symbol_end > len(data):
                return (name or "UNKNOWN", "???", "")
            
            symbol = data[symbol_offset+4:symbol_end].decode('utf-8', errors='ignore').strip()
            
            # URI follows symbol
            uri_offset = symbol_end
            if uri_offset + 4 > len(data):
                return (name or "UNKNOWN", symbol or "???", "")
            
            uri_len = int.from_bytes(
                data[uri_offset:uri_offset+4],
                byteorder='little'
            )
            uri_end = uri_offset + 4 + uri_len
            
            if uri_end > len(data):
                uri = ""
            else:
                uri = data[uri_offset+4:uri_end].decode('utf-8', errors='ignore').strip()
            
            return (
                name or "UNKNOWN",
                symbol or "???",
                uri or ""
            )
        
        except Exception as e:
            solana_log(f"[META] Metadata parse error: {e}", "DEBUG")
            return ("UNKNOWN", "???", "")
    
    def get_cached(self, mint: str) -> Optional[TokenMetadata]:
        """Get cached metadata without resolving."""
        return self._metadata_cache.get(mint)
    
    def clear_cache(self):
        """Clear all cached metadata."""
        self._metadata_cache.clear()
        self._failed_mints.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "cached_tokens": len(self._metadata_cache),
            "failed_mints": len(self._failed_mints),
            "cache_ttl_seconds": self.cache_ttl
        }
