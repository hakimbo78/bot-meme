"""
Running Cooldown System - Persistent storage for preventing duplicate alerts

Features:
- 60-minute cooldown between alerts for same token
- Persists to JSON file (survives restarts)
- Rejects re-alert attempts within cooldown

The cooldown file is stored at running/running_cooldown.json by default.
"""
import json
import time
from pathlib import Path
from typing import Dict, Optional
from .running_config import get_running_config


class RunningCooldown:
    """
    Persistent cooldown system for running token alerts.
    
    Enforces 60-minute cooldown between alerts for same token.
    This prevents spam while allowing re-alerting on sustained rallies.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or get_running_config()
        self.cooldown_minutes = self.config.get("cooldown_minutes", 60)
        self.cooldown_file = Path(self.config.get("cooldown_file", "running/running_cooldown.json"))
        
        # In-memory cache: {token_address_lower: {timestamp, running_score, chain, ...}}
        self._alerted_tokens: Dict[str, Dict] = {}
        
        # Load from file on init
        self._load_from_file()
    
    def is_on_cooldown(self, token_address: str) -> bool:
        """
        Check if token is on cooldown (was recently alerted).
        
        Args:
            token_address: Token contract address
            
        Returns:
            True if on cooldown (should skip), False if eligible for alert
        """
        token_addr = token_address.lower()
        
        # Clean expired entries first
        self._clean_expired()
        
        if token_addr not in self._alerted_tokens:
            return False
        
        entry = self._alerted_tokens[token_addr]
        cooldown_seconds = self.cooldown_minutes * 60
        elapsed = time.time() - entry.get("timestamp", 0)
        
        if elapsed < cooldown_seconds:
            remaining = int((cooldown_seconds - elapsed) / 60)
            print(f"[RUNNING] Cooldown: Token {token_addr[:10]}... on cooldown ({remaining}m remaining)")
            return True
        
        return False
    
    def mark_alerted(self, token_address: str, data: Dict = None) -> bool:
        """
        Mark token as alerted (start cooldown).
        
        Args:
            token_address: Token contract address
            data: Optional data to store (score, chain, etc.)
            
        Returns:
            True if marked successfully
        """
        token_addr = token_address.lower()
        
        # Store with metadata
        self._alerted_tokens[token_addr] = {
            "timestamp": time.time(),
            "alerted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **(data or {})
        }
        
        # Persist to file
        self._save_to_file()
        
        print(f"[RUNNING] Cooldown: Marked {token_addr[:10]}... (cooldown: {self.cooldown_minutes}m)")
        return True
    
    def get_alert_count(self) -> int:
        """Get total count of tokens in cooldown."""
        self._clean_expired()
        return len(self._alerted_tokens)
    
    def get_token_info(self, token_address: str) -> Optional[Dict]:
        """Get stored info for an alerted token."""
        return self._alerted_tokens.get(token_address.lower())
    
    def get_remaining_cooldown(self, token_address: str) -> int:
        """
        Get remaining cooldown time in minutes.
        
        Returns:
            Remaining minutes, or 0 if not on cooldown
        """
        token_addr = token_address.lower()
        
        if token_addr not in self._alerted_tokens:
            return 0
        
        entry = self._alerted_tokens[token_addr]
        cooldown_seconds = self.cooldown_minutes * 60
        elapsed = time.time() - entry.get("timestamp", 0)
        
        if elapsed >= cooldown_seconds:
            return 0
        
        return int((cooldown_seconds - elapsed) / 60)
    
    def clear_all(self, confirm: bool = False) -> bool:
        """
        Clear all cooldown entries. DANGEROUS - requires confirmation.
        
        Args:
            confirm: Must be True to actually clear
            
        Returns:
            True if cleared, False if confirm was not True
        """
        if not confirm:
            print("[RUNNING] Cooldown: clear_all requires confirm=True")
            return False
        
        self._alerted_tokens = {}
        self._save_to_file()
        print("[RUNNING] Cooldown: All entries cleared")
        return True
    
    def _clean_expired(self) -> int:
        """Remove expired cooldown entries."""
        current_time = time.time()
        cooldown_seconds = self.cooldown_minutes * 60
        
        expired = []
        for token_addr, entry in self._alerted_tokens.items():
            elapsed = current_time - entry.get("timestamp", 0)
            if elapsed >= cooldown_seconds:
                expired.append(token_addr)
        
        for token_addr in expired:
            del self._alerted_tokens[token_addr]
        
        if expired:
            self._save_to_file()
            
        return len(expired)
    
    def _load_from_file(self) -> None:
        """Load alerted tokens from persistence file."""
        try:
            if self.cooldown_file.exists():
                with open(self.cooldown_file, "r") as f:
                    data = json.load(f)
                    self._alerted_tokens = data.get("tokens", {})
                    print(f"[RUNNING] Cooldown: Loaded {len(self._alerted_tokens)} entries from file")
            else:
                self._alerted_tokens = {}
                print("[RUNNING] Cooldown: No existing file, starting fresh")
        except Exception as e:
            print(f"[RUNNING] Cooldown: Error loading file: {e}")
            self._alerted_tokens = {}
    
    def _save_to_file(self) -> None:
        """Save alerted tokens to persistence file."""
        try:
            # Ensure directory exists
            self.cooldown_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save with metadata
            data = {
                "version": 1,
                "cooldown_minutes": self.cooldown_minutes,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_count": len(self._alerted_tokens),
                "tokens": self._alerted_tokens
            }
            
            with open(self.cooldown_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"[RUNNING] Cooldown: Error saving to file: {e}")
    
    def get_stats(self) -> Dict:
        """Get cooldown statistics."""
        self._clean_expired()
        tokens = self._alerted_tokens
        
        if not tokens:
            return {
                "active_cooldowns": 0,
                "oldest": None,
                "newest": None,
                "cooldown_minutes": self.cooldown_minutes
            }
        
        timestamps = [t.get("timestamp", 0) for t in tokens.values()]
        
        return {
            "active_cooldowns": len(tokens),
            "oldest": min(timestamps) if timestamps else None,
            "newest": max(timestamps) if timestamps else None,
            "cooldown_minutes": self.cooldown_minutes,
            "file_path": str(self.cooldown_file)
        }
