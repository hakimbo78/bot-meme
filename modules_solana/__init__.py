"""
Solana module for auto-upgrade system

Contains:
- Priority detector for TX analysis
- Smart wallet detector for tracking profitable wallets
"""

from .priority_detector import SolanaPriorityDetector
from .smart_wallet_detector import SmartWalletDetector

__all__ = ['SolanaPriorityDetector', 'SmartWalletDetector']
