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
            
        # DEBUG: Log response structure
        logger.info(f"DEBUG SWAP DATA KEYS: {list(swap_data.keys())}")
            
        # 5. Sign Transaction
        try:
            # Extract transaction payload based on chain
            if chain == 'solana':
                # OKX returns nested structure for Solana: {'tx': {'data': 'base64...'}}
                tx_dict = swap_data.get('tx', {})
                if isinstance(tx_dict, dict):
                    tx_payload = tx_dict.get('data')
                else:
                    tx_payload = tx_dict  # Fallback if format changes
                    
                if not tx_payload:
                    logger.error("No transaction data found in OKX response")
                    return False
                    
                logger.info(f"DEBUG TX PAYLOAD (Solana): {tx_payload[:100]}...")
            else:
                # EVM chains: OKX returns tx object directly
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
        # Extract amount from OKX response
        try:
            router_result = swap_data.get('routerResult', {})
            # toTokenAmount is the estimated output amount (in raw units)
            token_amount_raw = router_result.get('toTokenAmount', '0')
            token_amount = float(token_amount_raw)
            
            # Estimate price (USD Budget / Amount)
            # This is 'price per raw unit', useful for calculations
            price_est = amount_usd / token_amount if token_amount > 0 else 0
            
        except Exception as e:
            logger.error(f"Failed to parse swap result: {e}")
            token_amount = 0
            price_est = 0

        self.pt.record_buy(
            token_address=token_address,
            chain=chain,
            wallet_address=wallet_address,
            amount=token_amount, # Raw amount stored
            price=price_est, 
            value_usd=amount_usd,
            tx_hash=tx_hash,
            signal_score=signal_score
        )
        
        return True

        return True

    async def execute_sell(
        self,
        chain: str,
        token_address: str,
        amount_raw: float,
        position_id: int
    ) -> bool:
        """Execute a sell order (TP/SL)."""
        chain = chain.lower()
        wallet_address = self.wm.get_address(chain)
        
        # Native token is output (we are selling token -> native)
        native_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        if chain == 'solana':
            native_token = "So11111111111111111111111111111111111111112"
            
        # Format amount (inputs are raw units, OKX expects integer string)
        amount_str = str(int(amount_raw))
        
        logger.info(f"Executing SELL for Pos {position_id} ({amount_str} units) on {chain}...")
        
        try:
            # 1. Get Swap Data
            swap_data = await self.okx.get_swap_data(
                chain,
                token_address, # Input is the token
                native_token,  # Output is native
                amount_str,
                10.0, # High slippage for urgent exit (10%)
                wallet_address
            )
            
            if not swap_data:
                logger.error("Failed to get swap data for sell")
                return False
                
            # 2. Sign
            if chain == 'solana':
                tx_payload = swap_data.get('tx', {}).get('data')
            else:
                tx_payload = swap_data.get('tx')
                
            signed_tx = self.wm.sign_transaction(chain, tx_payload)
            
            # 3. Broadcast
            tx_hash = await self._broadcast_transaction(chain, signed_tx)
            
            if not tx_hash:
                return False
                
            # 4. Record Sell
            # Estimate value from output amount
            router_result = swap_data.get('routerResult', {})
            output_amount_raw = float(router_result.get('toTokenAmount', '0'))
            
            # Rough price estimation (Native Price * Output Amount).
            # We don't have native price easily. 
            # We can use the 'value_usd' of the position and PnL% from OKX quote potentially?
            # Or just assume output value.
            # Ideally we fetch native price.
            # valid_usd = output_amount_raw * NATIVE_PRICE
            
            # For now, let's use the 'current_value_usd' from tracker if available, 
            # or just leave value_usd calculation to the tracker update logic.
            # Actually, `record_sell` needs value_usd.
            
            # Let's use a very rough estimate or 0. Tracker handles PnL.
            # Better: In run_position_monitor, we know the estimated value from the Quote check that triggered this!
            # But we don't pass it here.
            
            self.pt.record_sell(
                position_id=position_id,
                amount=amount_raw,
                price=0, # Unknown without native price
                value_usd=0, # Unknown without native price
                tx_hash=tx_hash
            )
            
            logger.info(f"SELL Broadcast successful! Tx Hash: {tx_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Sell execution failed: {e}")
            return False

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
            try:
                from solana.rpc.async_api import AsyncClient
                import base64
                
                # Use public RPC or custom one
                rpc_url = "https://api.mainnet-beta.solana.com"
                
                async with AsyncClient(rpc_url) as client:
                    # Solana lib expects bytes
                    tx_bytes = base64.b64decode(signed_tx)
                    
                    # Send
                    resp = await client.send_raw_transaction(tx_bytes)
                    
                    if resp.value:
                        return str(resp.value)
                    else:
                        logger.error(f"Solana Broadcast Error: {resp}")
                        return None
                        
            except Exception as e:
                logger.error(f"Solana Broadcast Exception: {e}")
                return None
                
        return None
