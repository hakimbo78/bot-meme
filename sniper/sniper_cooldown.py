"""
Sniper Cooldown System - Persistent storage for preventing duplicate alerts

Features:
- Max 1 sniper alert per token address (EVER)
- Persists to JSON file (survives restarts)
- Rejects re-sniper attempts

The cooldown file is stored at sniper/sniper_cooldown.json by default.
"""
import json
import time
from pathlib import Path
from typing import Dict, Optional
from .sniper_config import get_sniper_config


class SniperCooldown:
    """
    Persistent cooldown system for sniper alerts.
    
    Once a token has been sniped (alert sent), it will NEVER be sniped again.
    This prevents spam and ensures operators only see first opportunities.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or get_sniper_config()
        self.cooldown_file = Path(self.config.get('cooldown_file', 'sniper/sniper_cooldown.json'))
        
        # In-memory cache: {token_address_lower: {timestamp, sniper_score, chain, ...}}
        self._sniped_tokens: Dict[str, Dict] = {}
        
        # Load from file on init
        self._load_from_file()
    
    def is_token_sniped(self, token_address: str) -> bool:
        """
        Check if token has already been sniped.
        
        Args:
            token_address: Token contract address
            
        Returns:
            True if already sniped (should skip), False if eligible
        """
        token_addr = token_address.lower()
        is_sniped = token_addr in self._sniped_tokens
        
        if is_sniped:
            print(f"[SNIPER] Cooldown: Token {token_addr[:10]}... already sniped, skipping")
        
        return is_sniped
    
    def mark_token_sniped(self, token_address: str, data: Dict = None) -> bool:
        """
        Mark token as sniped (alert sent).
        
        Args:
            token_address: Token contract address
            data: Optional data to store (score, chain, etc.)
            
        Returns:
            True if marked successfully, False if already existed
        """
        token_addr = token_address.lower()
        
        if token_addr in self._sniped_tokens:
            print(f"[SNIPER] Cooldown: Token {token_addr[:10]}... was already marked")
            return False
        
        # Store with metadata
        self._sniped_tokens[token_addr] = {
            'timestamp': time.time(),
            'sniped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            **(data or {})
        }
        
        # Persist to file
        self._save_to_file()
        
        print(f"[SNIPER] Cooldown: Marked {token_addr[:10]}... as sniped")
        return True
    
    def get_sniped_count(self) -> int:
        """Get total count of sniped tokens."""
        return len(self._sniped_tokens)
    
    def get_token_info(self, token_address: str) -> Optional[Dict]:
        """Get stored info for a sniped token."""
        return self._sniped_tokens.get(token_address.lower())
    
    def clear_all(self, confirm: bool = False) -> bool:
        """
        Clear all sniped tokens. DANGEROUS - requires confirmation.
        
        Args:
            confirm: Must be True to actually clear
            
        Returns:
            True if cleared, False if confirm was not True
        """
        if not confirm:
            print("[SNIPER] Cooldown: clear_all requires confirm=True")
            return False
        
        self._sniped_tokens = {}
        self._save_to_file()
        print("[SNIPER] Cooldown: All tokens cleared")
        return True
    
    def _load_from_file(self) -> None:
        """Load sniped tokens from persistence file."""
        try:
            if self.cooldown_file.exists():
                with open(self.cooldown_file, 'r') as f:
                    data = json.load(f)
                    self._sniped_tokens = data.get('tokens', {})
                    print(f"[SNIPER] Cooldown: Loaded {len(self._sniped_tokens)} sniped tokens from file")
            else:
                self._sniped_tokens = {}
                print("[SNIPER] Cooldown: No existing file, starting fresh")
        except Exception as e:
            print(f"[SNIPER] Cooldown: Error loading file: {e}")
            self._sniped_tokens = {}
    
    def _save_to_file(self) -> None:
        """Save sniped tokens to persistence file."""
        try:
            # Ensure directory exists
            self.cooldown_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with metadata
            data = {
                'version': 1,
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_count': len(self._sniped_tokens),
                'tokens': self._sniped_tokens
            }
            
            with open(self.cooldown_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[SNIPER] Cooldown: Error saving to file: {e}")
    
    def get_stats(self) -> Dict:
        """Get cooldown statistics."""
        tokens = self._sniped_tokens
        
        if not tokens:
            return {
                'total_sniped': 0,
                'oldest': None,
                'newest': None
            }
        
        timestamps = [t.get('timestamp', 0) for t in tokens.values()]
        
        return {
            'total_sniped': len(tokens),
            'oldest': min(timestamps) if timestamps else None,
            'newest': max(timestamps) if timestamps else None,
            'file_path': str(self.cooldown_file)
        }
