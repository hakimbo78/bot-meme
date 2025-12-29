"""
PAIR NORMALIZER

Converts raw API responses from different sources (DexScreener, DEXTools)
into the standardized NORMALIZED PAIR EVENT format.

This ensures the existing score engine receives consistent data regardless of source.
"""

from typing import Dict, Optional
from datetime import datetime


class PairNormalizer:
    """
    Normalizes pair data from different sources into standard format.
    
    NORMALIZED PAIR EVENT FORMAT (MANDATORY):
    {
      "chain": "base",
      "dex": "uniswap_v2",
      "pair_address": "0x...",
      "token0": "0x...",
      "token1": "0x...",
      "price_change_1h": 15.5,
      "price_change_24h": 120.0,
      "volume_1h": 5000,
      "volume_24h": 80000,
      "liquidity": 85000,
      "tx_1h": 45,
      "tx_24h": 320,
      "source": "dexscreener",
      "confidence": 0.72,
      "event_type": "SECONDARY_MARKET"
    }
    """
    
    def __init__(self):
        pass
    
    def normalize_dexscreener(self, raw_pair: Dict, source: str = "dexscreener") -> Dict:
        """
        Normalize DexScreener pair data.
        
        Args:
            raw_pair: Raw pair data from DexScreener API
            source: Data source identifier
            
        Returns:
            Normalized pair event dict
        """
        # ================================================================
        # PRICE CHANGE EXTRACTION (H1/H24 ONLY)
        # ================================================================
        # DexScreener PUBLIC API provides: h1, h6, h24 (m5 is unreliable)
        price_change = raw_pair.get('priceChange', {})
        price_change_1h = self._safe_float(price_change.get('h1', 0))
        price_change_6h = self._safe_float(price_change.get('h6', 0))
        price_change_24h = self._safe_float(price_change.get('h24', 0))
        
        # ================================================================
        # VOLUME EXTRACTION (H1/H24 ONLY)
        # ================================================================
        volume = raw_pair.get('volume', {})
        
        vol_1h_raw = volume.get('h1')
        vol_24h_raw = volume.get('h24', 0)
        
        # Extract h1 and h24 volumes directly from API
        volume_1h = self._safe_float(vol_1h_raw) if vol_1h_raw and vol_1h_raw > 0 else None
        volume_24h = self._safe_float(vol_24h_raw, 0)
        
        # Extract liquidity
        liquidity_obj = raw_pair.get('liquidity', {})
        liquidity = self._safe_float(liquidity_obj.get('usd', 0))
        
        # ================================================================
        # TRANSACTION COUNT EXTRACTION (H1/H24 ONLY)
        # ================================================================
        tx_obj = raw_pair.get('txns', {})
        h1_txns = tx_obj.get('h1', {})
        h24_txns = tx_obj.get('h24', {})
        
        # Extract h1 and h24 transaction counts (buys + sells) directly from API
        tx_1h_raw = h1_txns.get('buys', 0) + h1_txns.get('sells', 0) if h1_txns else 0
        tx_24h_raw = h24_txns.get('buys', 0) + h24_txns.get('sells', 0) if h24_txns else 0
        
        tx_1h = tx_1h_raw if tx_1h_raw > 0 else None
        tx_24h = tx_24h_raw
        
        # Extract addresses
        pair_address = raw_pair.get('pairAddress', '')
        base_token = raw_pair.get('baseToken', {})
        quote_token = raw_pair.get('quoteToken', {})
        
        token0 = base_token.get('address', '')
        token1 = quote_token.get('address', '')
        
        # Extract chain and DEX
        chain = self._normalize_chain(raw_pair.get('chainId', 'unknown'))
        dex_id = raw_pair.get('dexId', 'unknown')
        
        # Calculate confidence score (0.0 - 1.0)
        confidence = self._calculate_confidence(
            liquidity=liquidity,
            volume_24h=volume_24h,
            tx_count=tx_24h,
            has_price_change=bool(price_change_1h)
        )
        
        # Determine event type
        event_type = self._determine_event_type(
            price_change_1h=price_change_1h,
            volume_1h=volume_1h,
            tx_1h=tx_1h,
            created_at=raw_pair.get('pairCreatedAt')
        )
        
        # Calculate age in minutes
        age_minutes = None
        created_at = raw_pair.get('pairCreatedAt')
        if created_at:
            try:
                created_time = datetime.fromtimestamp(created_at / 1000)
                age_minutes = (datetime.now() - created_time).total_seconds() / 60
            except:
                pass
        
        return {
            # Core identifiers
            "chain": chain,
            "dex": dex_id,
            "pair_address": pair_address,
            "token0": token0,
            "token1": token1,
            
            # Price metrics
            "price_change_1h": price_change_1h,
            "price_change_6h": price_change_6h,
            "price_change_24h": price_change_24h,
            "current_price": self._safe_float(raw_pair.get('priceUsd', 0)),
            
            # Volume metrics
            "volume_1h": volume_1h,
            "volume_24h": volume_24h,
            
            # Liquidity
            "liquidity": liquidity,
            
            # Transaction counts
            "tx_1h": tx_1h,
            "tx_24h": tx_24h,
            
            # Metadata
            "source": source,
            "confidence": confidence,
            "event_type": event_type,
            "age_minutes": age_minutes,
            
            # Token info (for display)
            "token_name": base_token.get('name', 'UNKNOWN'),
            "token_symbol": base_token.get('symbol', 'UNKNOWN'),
            
            # Raw data (optional, for debugging)
            "_raw": raw_pair,
        }
    
    def normalize_dextools(self, raw_pair: Dict, source: str = "dextools") -> Dict:
        """
        Normalize DEXTools pair data.
        
        Args:
            raw_pair: Raw pair data from DEXTools API
            source: Data source identifier
            
        Returns:
            Normalized pair event dict
        """
        # DEXTools uses different structure
        # Extract metrics
        metrics = raw_pair.get('metrics', {})
        
        price_change_1h = self._safe_float(metrics.get('price_change_1h', 0))
        price_change_24h = self._safe_float(metrics.get('price_change_24h', 0))
        
        volume_24h = self._safe_float(metrics.get('volume_24h', 0))
        liquidity = self._safe_float(metrics.get('liquidity', 0))
        
        # DEXTools doesn't provide h1 volume/tx data reliably
        volume_1h = None
        tx_1h = None
        
        # Extract addresses
        pair_address = raw_pair.get('id', {}).get('pair', '')
        token_address = raw_pair.get('id', {}).get('token', '')
        
        # DEXTools structure doesn't always have token0/token1 explicitly
        token0 = token_address
        token1 = ''  # Usually paired with WETH/USDC
        
        # Extract chain
        chain = self._normalize_chain(raw_pair.get('id', {}).get('chain', 'unknown'))
        dex_id = raw_pair.get('dex', {}).get('name', 'unknown')
        
        # Calculate confidence
        rank = raw_pair.get('dextools_rank', 9999)
        confidence = self._calculate_confidence_dextools(
            rank=rank,
            liquidity=liquidity,
            volume_24h=volume_24h
        )
        
        # Event type
        event_type = "DEXTOOLS_TOP_GAINER" if rank <= 50 else "SECONDARY_MARKET"
        
        return {
            # Core identifiers
            "chain": chain,
            "dex": dex_id,
            "pair_address": pair_address,
            "token0": token0,
            "token1": token1,
            
            # Price metrics
            "price_change_1h": price_change_1h,
            "price_change_6h": None,
            "price_change_24h": price_change_24h,
            "current_price": self._safe_float(raw_pair.get('price', 0)),
            
            # Volume metrics
            "volume_1h": volume_1h,
            "volume_24h": volume_24h,
            
            # Liquidity
            "liquidity": liquidity,
            
            # Transaction counts
            "tx_1h": tx_1h,
            "tx_24h": None,
            
            # Metadata
            "source": source,
            "confidence": confidence,
            "event_type": event_type,
            "age_minutes": None,  # DEXTools doesn't provide creation time
            "dextools_rank": rank,  # Special field for DEXTools
            
            # Token info
            "token_name": raw_pair.get('name', 'UNKNOWN'),
            "token_symbol": raw_pair.get('symbol', 'UNKNOWN'),
            
            # Raw data
            "_raw": raw_pair,
        }
    
    def _normalize_chain(self, chain_id: str) -> str:
        """Normalize chain identifier."""
        chain_map = {
            'base': 'base',
            'ether': 'ethereum',
            'ethereum': 'ethereum',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'polygon': 'polygon',
            'blast': 'blast',
        }
        return chain_map.get(chain_id.lower(), chain_id.lower())
    
    def _safe_float(self, value, default=0.0) -> float:
        """Safely convert to float."""
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0) -> int:
        """Safely convert to int."""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _calculate_confidence(self, liquidity: float, volume_24h: float, 
                             tx_count: int, has_price_change: bool) -> float:
        """
        Calculate confidence score (0.0 - 1.0) for DexScreener data.
        
        Higher confidence = more complete and reliable data.
        """
        score = 0.0
        
        # Liquidity check
        if liquidity >= 50000:
            score += 0.3
        elif liquidity >= 20000:
            score += 0.2
        elif liquidity >= 5000:
            score += 0.1
        
        # Volume check
        if volume_24h >= 100000:
            score += 0.3
        elif volume_24h >= 50000:
            score += 0.2
        elif volume_24h >= 10000:
            score += 0.1
        
        # Transaction count
        if tx_count >= 100:
            score += 0.2
        elif tx_count >= 50:
            score += 0.15
        elif tx_count >= 20:
            score += 0.1
        
        # Has price change data
        if has_price_change:
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_confidence_dextools(self, rank: int, liquidity: float, volume_24h: float) -> float:
        """
        Calculate confidence score for DEXTools data.
        
        DEXTools top 50 ranks are highly confident.
        """
        score = 0.0
        
        # Rank-based confidence (DEXTools ranking is strong signal)
        if rank <= 10:
            score += 0.5
        elif rank <= 30:
            score += 0.4
        elif rank <= 50:
            score += 0.3
        elif rank <= 100:
            score += 0.2
        
        # Liquidity
        if liquidity >= 50000:
            score += 0.3
        elif liquidity >= 20000:
            score += 0.2
        
        # Volume
        if volume_24h >= 100000:
            score += 0.2
        elif volume_24h >= 50000:
            score += 0.1
        
        return min(1.0, score)
    
    def _determine_event_type(self, price_change_1h: float,
                             volume_1h: float, tx_1h: int, created_at: Optional[int]) -> str:
        """
        Determine event type based on h1 metrics only.
        
        Types:
        - NEW_PAIR: Recently created (< 1 hour)
        - PRICE_SPIKE: Strong price increase (>= 100% in 1h)
        - VOLUME_SPIKE: High volume activity (>= $10k in 1h)
        - SECONDARY_MARKET: General breakout signal
        """
        # Check if new pair (< 60 minutes old)
        if created_at:
            try:
                age_seconds = (datetime.now().timestamp() * 1000 - created_at) / 1000
                if age_seconds < 3600:  # < 1 hour
                    return "NEW_PAIR"
            except:
                pass
        
        # Check for price spike (h1 only)
        if price_change_1h and price_change_1h >= 100:  # >= 100% in 1 hour
            return "PRICE_SPIKE"
        
        # Check for volume spike (h1 only)
        if volume_1h and volume_1h >= 10000:  # $10k+ in 1 hour
            return "VOLUME_SPIKE"
        
        # Default
        return "SECONDARY_MARKET"
