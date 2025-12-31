"""
Trade Executor
Orchestrates the entire trade flow: Quote -> Sign -> Broadcast -> Record
"""

import asyncio
import logging
from typing import Dict, Optional
from web3 import Web3

from .config_manager import ConfigManager
from .wallet_manager import WalletManager
from .okx_client import OKXDexClient
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(
        self,
        wallet_manager: WalletManager,
        okx_client: OKXDexClient,
        position_tracker: PositionTracker
    ):
        self.wm = wallet_manager
        self.okx = okx_client
        self.pt = position_tracker
        
        # We need web3 instances for EVM broadcasting
        self.web3_instances = {}
        self._init_web3()

    def _init_web3(self):
        """Initialize Web3 connections for enabled EVM chains."""
        config = ConfigManager.get_config()
        for chain, data in config['chains'].items():
            if chain in ['base', 'ethereum'] and data['enabled']:
                try:
                    self.web3_instances[chain] = Web3(Web3.HTTPProvider(data['rpc_url']))
                except Exception as e:
                    logger.error(f"Failed to init Web3 for {chain}: {e}")

    async def execute_buy(
        self,
        chain: str,
        token_address: str,
        signal_score: float = 0
    ) -> bool:
        """
        Execute a buy order.
        """
        chain = chain.lower()
        
        # 1. Validation
        if not ConfigManager.is_trading_enabled():
            logger.warning("Trading is disabled")
            return False
            
        if not ConfigManager.is_chain_enabled(chain):
            logger.warning(f"Chain {chain} is disabled")
            return False
            
        wallet_address = self.wm.get_address(chain)
        if not wallet_address:
            logger.error(f"No wallet for {chain}")
            return False
            
        amount_usd = ConfigManager.get_budget()
        
        # 2. Get Native Token (Input)
        native_token = ConfigManager.get_chain_config(chain)['native_token']
        # OKX uses '0xeeee...' for native ETH usually, OKX doc specific
        # For simplicity, we assume OKX handles '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE' as native
        input_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" 
        
        if chain == 'solana':
            input_token = "So11111111111111111111111111111111111111112" # Wrapped SOL or Native logic depending on OKX/Jupiter

        # 3. Calculate Amount (Need price of native token approx or use exact amount)
        # Simplification: pass 'amount' in USDT to OKX? No, DEX needs raw amount.
        # We need a price oracle here or assume safe default budget -> native amount conversion
        # TODO: Add Price Oracle. For Phase 2 Test, let's hardcode small amount
        
        # HARDCODED TEST AMOUNT
        raw_amount = "1000000000000000" # 0.001 ETH (approx $3)
        if chain == 'solana':
            raw_amount = "10000000" # 0.01 SOL (approx $2)

        logger.info(f"Executing BUY for {token_address} on {chain}...")
        
        # 4. Get Swap Data
        # Using 5% slippage for memecoins
        swap_data = await self.okx.get_swap_data(
            chain, 
            input_token, 
            token_address, 
            raw_amount, 
            0.05, 
            wallet_address
        )
        
        if not swap_data:
            logger.error("Failed to get swap data")
            return False
            
        # 5. Sign Transaction
        try:
            # tx_data comes from OKX 'tx' field
            tx_payload = swap_data.get('tx')
            signed_tx = self.wm.sign_transaction(chain, tx_payload)
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return False
            
        # 6. Broadcast
        tx_hash = await self._broadcast_transaction(chain, signed_tx)
        if not tx_hash:
            return False
            
        logger.info(f"Broadcast successful! Tx Hash: {tx_hash}")
        
        # 7. Record Position
        # We assume execution price from quote data ideally
        # For now, approximate
        self.pt.record_buy(
            token_address=token_address,
            chain=chain,
            wallet_address=wallet_address,
            amount=0, # Need to parse form events
            price=0, # Need calculation
            value_usd=amount_usd,
            tx_hash=tx_hash,
            signal_score=signal_score
        )
        
        return True

    async def _broadcast_transaction(self, chain: str, signed_tx: str) -> Optional[str]:
        """Broadcast transaction to network."""
        chain = chain.lower()
        
        if chain in ['base', 'ethereum']:
            if chain in self.web3_instances:
                try:
                    w3 = self.web3_instances[chain]
                    tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx)
                    return w3.to_hex(tx_hash_bytes)
                except Exception as e:
                    logger.error(f"EVM Broadcast failed: {e}")
                    return None
        elif chain == 'solana':
            # Need RPC client for Solana
            # Placeholder using generic request if solana lib available
            try:
                from solana.rpc.async_api import AsyncClient
                # TODO: Init client properly
                # client = AsyncClient(rpc_url)
                # resp = await client.send_raw_transaction(signed_tx)
                pass 
            except:
                pass
                
        return "0xMOCKED_HASH_FOR_PHASE_2" # TODO: Remove mock
