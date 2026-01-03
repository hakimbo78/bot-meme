#!/usr/bin/env python3
"""
Test script for chain-type-specific configuration
"""

import sys
sys.path.insert(0, '/home/hakim/bot-meme')

from trading.config_manager import ConfigManager

print("=" * 60)
print("CHAIN-TYPE-SPECIFIC CONFIG TEST")
print("=" * 60)

# Test EVM (Base)
print("\n📊 BASE (EVM) Configuration:")
print(f"  Budget: ${ConfigManager.get_budget('base')}")
print(f"  Max Positions: {ConfigManager.get_max_positions('base')}")
exit_strategy = ConfigManager.get_exit_strategy('base')
print(f"  Take Profit: {exit_strategy.get('take_profit_percent')}%")
print(f"  Stop Loss: {exit_strategy.get('stop_loss_percent')}%")
print(f"  Moonbag Sell: {exit_strategy.get('take_profit_sell_percent')}%")

# Test Solana
print("\n📊 SOLANA Configuration:")
print(f"  Budget: ${ConfigManager.get_budget('solana')}")
print(f"  Max Positions: {ConfigManager.get_max_positions('solana')}")
exit_strategy = ConfigManager.get_exit_strategy('solana')
print(f"  Take Profit: {exit_strategy.get('take_profit_percent')}%")
print(f"  Stop Loss: {exit_strategy.get('stop_loss_percent')}%")
print(f"  Moonbag Sell: {exit_strategy.get('take_profit_sell_percent')}%")

# Test chain type detection
print("\n🔍 Chain Type Detection:")
print(f"  base → {ConfigManager.get_chain_type('base')}")
print(f"  ethereum → {ConfigManager.get_chain_type('ethereum')}")
print(f"  solana → {ConfigManager.get_chain_type('solana')}")

print("\n✅ Configuration test complete!")
print("=" * 60)
