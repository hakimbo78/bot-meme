"""
Jupiter Scanner - Momentum Confirmation Module

Monitors Jupiter aggregator for:
- Token routing activity
- Volume tracking (24h)
- Slippage trends
- Routing frequency

Output: Momentum confirmation data for scoring

CRITICAL: READ-ONLY - No execution, no wallets
"""
import time
import requests
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .solana_utils import (
    JUPITER_AGGREGATOR_V6,
    is_valid_solana_address,
    solana_log,
    rate_limit_rpc,
    sol_to_usd
)


@dataclass
class JupiterTokenData:
    """Represents Jupiter routing data for a token."""
    token_mint: str
    first_seen: float
    total_volume_usd: float = 0.0
    volume_24h_usd: float = 0.0
    trade_count_24h: int = 0
    avg_slippage_bps: float = 0.0
    routing_count: int = 0
    last_trade_timestamp: float = 0.0
    volume_history: List[tuple] = field(default_factory=list)  # (timestamp, volume)
    
    @property
    def volume_trend(self) -> str:
        """Determine volume trend: increasing, stable, decreasing."""
        if len(self.volume_history) < 2:
            return "stable"
        
        # Compare last hour to previous hour
        now = time.time()
        hour_ago = now - 3600
        two_hours_ago = now - 7200
        
        recent_vol = sum(v for t, v in self.volume_history if t > hour_ago)
        prev_vol = sum(v for t, v in self.volume_history if two_hours_ago < t <= hour_ago)
        
        if prev_vol == 0:
            return "increasing" if recent_vol > 0 else "stable"
        
        change = (recent_vol - prev_vol) / prev_vol
        
        if change > 0.2:
            return "increasing"
        elif change < -0.2:
            return "decreasing"
        return "stable"
    
    @property
    def is_active(self) -> bool:
        """Check if token has recent Jupiter activity."""
        return time.time() - self.last_trade_timestamp < 3600  # Active in last hour
    
    def to_dict(self) -> Dict:
        """Convert to normalized output format."""
        return {
            "source": "jupiter",
            "token_mint": self.token_mint,
            "jupiter_listed": True,
            "volume_24h_usd": round(self.volume_24h_usd, 2),
            "total_volume_usd": round(self.total_volume_usd, 2),
            "trade_count_24h": self.trade_count_24h,
            "avg_slippage_bps": round(self.avg_slippage_bps, 2),
            "routing_count": self.routing_count,
            "routing_trend": self.volume_trend,
            "is_active": self.is_active,
            "first_seen": self.first_seen,
            "last_trade": self.last_trade_timestamp
        }


class JupiterScanner:
    """
    Scanner for Jupiter aggregator activity.
    
    Tracks token routing through Jupiter to confirm momentum
    and trading interest.
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize Jupiter scanner.
        
        Args:
            config: Solana chain config
        """
        self.config = config or {}
        self.program_id = self.config.get('programs', {}).get(
            'jupiter', JUPITER_AGGREGATOR_V6
        )
        self.client = None
        self._tokens: Dict[str, JupiterTokenData] = {}
        self._processed_signatures: Set[str] = set()
        self._enabled = True
        
        # Jupiter API endpoints
        self._price_api = "https://price.jup.ag/v4/price"
        self._quote_api = "https://quote-api.jup.ag/v6/quote"
        
        # Tracking limits
        self._max_tracked_tokens = 200
        self._signature_history_limit = 1000
        
    def connect(self, client) -> bool:
        """
        Set the Solana RPC client.
        
        Args:
            client: Solana RPC client instance
            
        Returns:
            True if client is valid
        """
        if client is None:
            solana_log("Jupiter scanner: No client provided", "WARN")
            self._enabled = False
            return False
        
        self.client = client
        solana_log("Jupiter scanner connected")
        return True
    
    def scan(self) -> List[Dict]:
        """
        Scan for Jupiter routing activity.
        
        Returns:
            List of normalized token dicts with Jupiter data
        """
        if not self._enabled or not self.client:
            return []
        
        updated_tokens = []
        
        try:
            rate_limit_rpc()
            
            from solders.pubkey import Pubkey
            
            program_key = Pubkey.from_string(self.program_id)
            
            # Get recent signatures
            response = self.client.get_signatures_for_address(
                program_key,
                limit=15
            )
            
            if not response.value:
                return []
            
            new_sigs = []
            for sig_info in response.value:
                sig = str(sig_info.signature)
                if sig not in self._processed_signatures:
                    new_sigs.append(sig)
                    self._processed_signatures.add(sig)

            # Process in parallel
            if new_sigs:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(self._parse_jupiter_transaction, sig) for sig in new_sigs]
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            token_data = future.result()
                            if token_data:
                                updated_tokens.append(token_data)
                        except Exception:
                            pass
            
            # Keep bounded
            if len(self._processed_signatures) > self._signature_history_limit:
                excess = len(self._processed_signatures) - self._signature_history_limit
                for _ in range(excess + 50):
                    try:
                        self._processed_signatures.pop()
                    except (KeyError, AttributeError):
                        break
            
            # Update 24h volume calculations
            self._update_volume_stats()
            
        except Exception as e:
            solana_log(f"Jupiter scan error: {e}", "ERROR")
        
        return updated_tokens
    
    def _parse_jupiter_transaction(self, signature: str) -> Optional[Dict]:
        """
        Parse a Jupiter transaction for swap events.
        
        Args:
            signature: Transaction signature
            
        Returns:
            Token data dict or None
        """
        try:
            rate_limit_rpc()
            
            response = self.client.get_transaction(
                signature,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not response.value:
                return None
            
            tx = response.value
            meta = tx.meta if hasattr(tx, 'meta') else None
            
            if not meta or meta.err:  # Skip failed transactions
                return None
            
            block_time = getattr(tx, 'block_time', None) or time.time()
            
            # Extract tokens involved in swap
            tokens_involved = self._extract_swap_tokens(meta)
            
            if not tokens_involved:
                return None
            
            # Update token tracking
            result = None
            for token_mint, volume_sol in tokens_involved:
                if token_mint not in self._tokens:
                    self._tokens[token_mint] = JupiterTokenData(
                        token_mint=token_mint,
                        first_seen=block_time
                    )
                
                token = self._tokens[token_mint]
                volume_usd = sol_to_usd(volume_sol)
                
                token.total_volume_usd += volume_usd
                token.routing_count += 1
                token.last_trade_timestamp = block_time
                token.volume_history.append((block_time, volume_usd))
                
                # Keep history bounded
                if len(token.volume_history) > 1000:
                    token.volume_history = token.volume_history[-500:]
                
                result = token.to_dict()
            
            return result
            
        except Exception:
            pass
        
        return None
    
    def _extract_swap_tokens(self, meta) -> List[tuple]:
        """
        Extract token mints and volumes from swap transaction.
        
        Returns:
            List of (token_mint, volume_sol) tuples
        """
        tokens = []
        
        try:
            # Use pre/post token balances to identify swapped tokens
            pre_balances = meta.pre_token_balances if hasattr(meta, 'pre_token_balances') else []
            post_balances = meta.post_token_balances if hasattr(meta, 'post_token_balances') else []
            
            # Build balance change map
            balance_changes = {}
            
            for post in post_balances:
                mint = str(post.mint) if hasattr(post, 'mint') else None
                if not mint:
                    continue
                
                post_amount = 0
                if hasattr(post, 'ui_token_amount'):
                    post_amount = float(post.ui_token_amount.ui_amount or 0)
                
                # Find matching pre-balance
                pre_amount = 0
                for pre in pre_balances:
                    pre_mint = str(pre.mint) if hasattr(pre, 'mint') else None
                    if pre_mint == mint:
                        if hasattr(pre, 'ui_token_amount'):
                            pre_amount = float(pre.ui_token_amount.ui_amount or 0)
                        break
                
                change = abs(post_amount - pre_amount)
                if change > 0:
                    if mint not in balance_changes:
                        balance_changes[mint] = 0
                    balance_changes[mint] += change
            
            # Convert to list, estimate SOL value (simplified)
            for mint, amount in balance_changes.items():
                # Skip wrapped SOL
                if mint == "So11111111111111111111111111111111111111112":
                    continue
                # Rough estimate: use amount as-is (would need price API for accuracy)
                tokens.append((mint, amount * 0.01))  # Placeholder conversion
            
        except Exception:
            pass
        
        return tokens
    
    def _update_volume_stats(self):
        """Update 24h volume statistics for all tokens."""
        now = time.time()
        day_ago = now - 86400
        
        for token in self._tokens.values():
            # Calculate 24h volume
            vol_24h = sum(
                v for t, v in token.volume_history
                if t > day_ago
            )
            token.volume_24h_usd = vol_24h
            
            # Calculate 24h trade count
            token.trade_count_24h = sum(
                1 for t, _ in token.volume_history
                if t > day_ago
            )
        
        # Cleanup old tokens
        self._cleanup_inactive_tokens()
    
    def _cleanup_inactive_tokens(self):
        """Remove tokens inactive for more than 24 hours."""
        now = time.time()
        cutoff = now - 86400
        
        to_remove = [
            mint for mint, token in self._tokens.items()
            if token.last_trade_timestamp < cutoff
        ]
        
        for mint in to_remove:
            del self._tokens[mint]
        
        # Also limit total
        if len(self._tokens) > self._max_tracked_tokens:
            sorted_tokens = sorted(
                self._tokens.items(),
                key=lambda x: x[1].last_trade_timestamp
            )
            for mint, _ in sorted_tokens[:len(self._tokens) - self._max_tracked_tokens]:
                del self._tokens[mint]
    
    def is_listed(self, token_mint: str) -> bool:
        """Check if token has Jupiter routing activity."""
        return token_mint in self._tokens
    
    def get_token_data(self, token_mint: str) -> Optional[Dict]:
        """Get Jupiter data for a token."""
        token = self._tokens.get(token_mint)
        return token.to_dict() if token else None
    
    def get_momentum_data(self, token_mint: str) -> Dict:
        """
        Get momentum data for a token.
        
        Returns standardized dict for scoring.
        """
        token = self._tokens.get(token_mint)
        
        if not token:
            return {
                "jupiter_listed": False,
                "volume_24h_usd": 0,
                "routing_trend": "unknown"
            }
        
        return {
            "jupiter_listed": True,
            "volume_24h_usd": token.volume_24h_usd,
            "routing_trend": token.volume_trend,
            "is_active": token.is_active,
            "trade_count_24h": token.trade_count_24h
        }
    
    def check_volume_spike(self, token_mint: str, multiplier: float = 2.0) -> bool:
        """
        Check if token has a volume spike.
        
        Args:
            token_mint: Token mint address
            multiplier: Spike threshold (e.g., 2.0 = 2x average)
            
        Returns:
            True if volume spike detected
        """
        token = self._tokens.get(token_mint)
        if not token or len(token.volume_history) < 10:
            return False
        
        # Calculate average volume per hour
        now = time.time()
        hour_ago = now - 3600
        
        recent_vol = sum(v for t, v in token.volume_history if t > hour_ago)
        
        # Average over previous hours
        older_vols = [v for t, v in token.volume_history if t <= hour_ago]
        if not older_vols:
            return False
        
        avg_vol = sum(older_vols) / len(older_vols)
        
        return recent_vol > avg_vol * multiplier if avg_vol > 0 else False
    
    def get_all_tokens(self) -> List[Dict]:
        """Get all tracked tokens."""
        return [t.to_dict() for t in self._tokens.values()]
    
    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return {
            "enabled": self._enabled,
            "tracked_tokens": len(self._tokens),
            "processed_signatures": len(self._processed_signatures),
            "program_id": self.program_id
        }
