"""
Smart Wallet Clustering & Detection

Tracks known profitable wallets and scores based on historical success.

Database structure:
- Wallet address
- Success rate (wins / total trades)
- Early entry count
- Avg profit multiplier
- Tier (1=elite, 2=good, 3=average)

READ-ONLY informational system.
NO trading execution.

Output:
- smart_wallet_score (max 40)
- is_smart_money flag
- smart_wallet_reasons list
"""

import json
import time
from typing import Dict, List, Optional, Set
from pathlib import Path


class SmartWalletDetector:
    """
    Detect and score known profitable wallets.
    
    Features:
    - Wallet database with historical performance
    - Tier-based scoring
    - Early entry detection
    - Success rate tracking
    
    Scoring:
    - Tier 1 (elite): +40 points
    - Tier 2 (good): +25 points
    - Tier 3 (average): +15 points
    - Max: 40 points (multiple wallets don't stack)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize smart wallet detector.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        
        # Database path
        self.db_path = Path(self.config.get('db_path', 'data/smart_wallets.json'))
        
        # Scoring weights
        self.score_tier1 = self.config.get('score_tier1', 40)
        self.score_tier2 = self.config.get('score_tier2', 25)
        self.score_tier3 = self.config.get('score_tier3', 15)
        self.max_score = 40
        
        # Thresholds for tier classification
        self.tier1_min_success = self.config.get('tier1_min_success', 0.70)  # 70% win rate
        self.tier1_min_trades = self.config.get('tier1_min_trades', 10)
        self.tier2_min_success = self.config.get('tier2_min_success', 0.50)  # 50% win rate
        self.tier2_min_trades = self.config.get('tier2_min_trades', 5)
        
        # Load wallet database
        self.wallets = self._load_database()
        
        # Cache for quick lookups
        self.tier_cache = self._build_tier_cache()
        
        print(f"[SMART_WALLET] Loaded {len(self.wallets)} wallets from database")
    
    def _load_database(self) -> Dict:
        """
        Load wallet database from JSON file.
        
        Returns:
            Dict mapping wallet address to wallet data
        """
        if not self.db_path.exists():
            # Create empty database
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            empty_db = {}
            with open(self.db_path, 'w') as f:
                json.dump(empty_db, f, indent=2)
            return empty_db
        
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"[SMART_WALLET] Error loading database: {e}")
            return {}
    
    def _build_tier_cache(self) -> Dict[int, Set[str]]:
        """
        Build cache mapping tier levels to wallet addresses.
        
        Returns:
            Dict with tier -> set of addresses
        """
        cache = {1: set(), 2: set(), 3: set()}
        
        for address, data in self.wallets.items():
            tier = self._calculate_tier(data)
            if tier:
                cache[tier].add(address.lower())
        
        return cache
    
    def _calculate_tier(self, wallet_data: Dict) -> Optional[int]:
        """
        Calculate wallet tier based on performance.
        
        Args:
            wallet_data: Wallet performance data
        
        Returns:
            Tier level (1, 2, 3) or None if not qualified
        """
        total_trades = wallet_data.get('total_trades', 0)
        wins = wallet_data.get('wins', 0)
        
        if total_trades == 0:
            return None
        
        success_rate = wins / total_trades
        
        # Tier 1: Elite (70%+ success, 10+ trades)
        if success_rate >= self.tier1_min_success and total_trades >= self.tier1_min_trades:
            return 1
        
        # Tier 2: Good (50%+ success, 5+ trades)
        if success_rate >= self.tier2_min_success and total_trades >= self.tier2_min_trades:
            return 2
        
        # Tier 3: Average (any success, 3+ trades)
        if total_trades >= 3 and wins > 0:
            return 3
        
        return None
    
    def analyze_wallets(self, wallet_addresses: List[str]) -> Dict:
        """
        Analyze a list of wallet addresses for smart money signals.
        
        Args:
            wallet_addresses: List of wallet addresses to check
        
        Returns:
            Dict with:
                - smart_wallet_score: int (0-40)
                - is_smart_money: bool
                - smart_wallet_reasons: List[str]
                - detected_wallets: List[Dict] with wallet details
                - highest_tier: Optional[int]
        """
        result = {
            'smart_wallet_score': 0,
            'is_smart_money': False,
            'smart_wallet_reasons': [],
            'detected_wallets': [],
            'highest_tier': None
        }
        
        if not wallet_addresses:
            return result
        
        # Normalize addresses
        normalized = [addr.lower() for addr in wallet_addresses]
        
        # Check each tier (start with highest)
        for tier in [1, 2, 3]:
            tier_wallets = self.tier_cache.get(tier, set())
            matches = tier_wallets.intersection(normalized)
            
            if matches:
                # Found smart wallets in this tier
                result['highest_tier'] = tier
                
                # Add score based on tier
                if tier == 1:
                    result['smart_wallet_score'] = self.score_tier1
                    tier_name = "ELITE"
                elif tier == 2:
                    result['smart_wallet_score'] = self.score_tier2
                    tier_name = "GOOD"
                else:
                    result['smart_wallet_score'] = self.score_tier3
                    tier_name = "AVERAGE"
                
                # Build reason
                for wallet_addr in matches:
                    wallet_data = self.wallets.get(wallet_addr, {})
                    total_trades = wallet_data.get('total_trades', 0)
                    wins = wallet_data.get('wins', 0)
                    success_rate = (wins / total_trades * 100) if total_trades > 0 else 0
                    
                    result['smart_wallet_reasons'].append(
                        f"{tier_name} wallet: {wallet_addr[:8]}... ({wins}/{total_trades} wins, {success_rate:.1f}%)"
                    )
                    
                    result['detected_wallets'].append({
                        'address': wallet_addr,
                        'tier': tier,
                        'tier_name': tier_name,
                        'total_trades': total_trades,
                        'wins': wins,
                        'success_rate': success_rate,
                        'avg_profit_multiplier': wallet_data.get('avg_profit_multiplier', 0),
                        'early_entries': wallet_data.get('early_entries', 0)
                    })
                
                # Stop at first tier match (highest tier wins)
                break
        
        result['is_smart_money'] = result['smart_wallet_score'] > 0
        
        return result
    
    def add_wallet(self, address: str, performance: Dict) -> bool:
        """
        Add or update a wallet in the database.
        
        Args:
            address: Wallet address
            performance: Dict with:
                - total_trades: int
                - wins: int
                - avg_profit_multiplier: float
                - early_entries: int (optional)
        
        Returns:
            True if successful
        """
        try:
            normalized_addr = address.lower()
            
            # Update wallet data
            self.wallets[normalized_addr] = {
                'address': address,
                'total_trades': performance.get('total_trades', 0),
                'wins': performance.get('wins', 0),
                'avg_profit_multiplier': performance.get('avg_profit_multiplier', 0),
                'early_entries': performance.get('early_entries', 0),
                'last_updated': int(time.time())
            }
            
            # Save to file
            with open(self.db_path, 'w') as f:
                json.dump(self.wallets, f, indent=2)
            
            # Rebuild tier cache
            self.tier_cache = self._build_tier_cache()
            
            return True
            
        except Exception as e:
            print(f"[SMART_WALLET] Error adding wallet: {e}")
            return False
    
    def remove_wallet(self, address: str) -> bool:
        """
        Remove a wallet from the database.
        
        Args:
            address: Wallet address to remove
        
        Returns:
            True if successful
        """
        try:
            normalized_addr = address.lower()
            
            if normalized_addr in self.wallets:
                del self.wallets[normalized_addr]
                
                # Save to file
                with open(self.db_path, 'w') as f:
                    json.dump(self.wallets, f, indent=2)
                
                # Rebuild tier cache
                self.tier_cache = self._build_tier_cache()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"[SMART_WALLET] Error removing wallet: {e}")
            return False
    
    def get_wallet_info(self, address: str) -> Optional[Dict]:
        """
        Get information about a specific wallet.
        
        Args:
            address: Wallet address
        
        Returns:
            Wallet data dict or None if not found
        """
        normalized_addr = address.lower()
        wallet_data = self.wallets.get(normalized_addr)
        
        if wallet_data:
            tier = self._calculate_tier(wallet_data)
            wallet_data['tier'] = tier
            return wallet_data
        
        return None
    
    def get_tier_stats(self) -> Dict:
        """
        Get statistics about wallets by tier.
        
        Returns:
            Dict with tier -> count mapping
        """
        stats = {
            'tier1': len(self.tier_cache.get(1, set())),
            'tier2': len(self.tier_cache.get(2, set())),
            'tier3': len(self.tier_cache.get(3, set())),
            'total': len(self.wallets)
        }
        return stats
