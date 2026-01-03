"""
Trade Executor
Orchestrates the entire trade flow: Quote -> Sign -> Broadcast -> Record
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from web3 import Web3

from .config_manager import ConfigManager
from .wallet_manager import WalletManager
from .okx_client import OKXDexClient
from .position_tracker import PositionTracker

logger = logging.getLogger(__name__)

class TradeExecutor:
    # Class-level lock to prevent race condition when checking position limits
    _position_lock = asyncio.Lock()
    
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
        for chain, data in config.get('chains', {}).items():
            if chain in ['base', 'ethereum'] and data.get('enabled', False):
                try:
                    self.web3_instances[chain] = Web3(Web3.HTTPProvider(data['rpc_url']))
                except Exception as e:
                    logger.error(f"Failed to init Web3 for {chain}: {e}")

    async def execute_buy(
        self,
        chain: str,
        token_address: str,
        signal_score: float = 0
    ) -> Tuple[bool, str]:
        """
        Execute a buy order.
        Returns: (Success, Message or TxHash)
        """
        chain = chain.lower()
        
        # 1. Validation
        if not ConfigManager.is_trading_enabled():
            return False, "Trading is disabled in config"
            
        if not ConfigManager.is_chain_enabled(chain):
            return False, f"Chain {chain} is disabled"
        
        # RE-BUY PREVENTION CHECK
        rebuy_config = ConfigManager.get_config()['trading'].get('rebuy_prevention', {})
        if rebuy_config.get('enabled', False):
            last_exit_price = self.pt.get_last_exit_price(token_address, chain)
            
            if last_exit_price:
                # Token was previously traded - check price drop
                # Get current price from token_data or fetch from API
                current_price = token_data.get('price_usd', 0) if token_data else 0
                
                if current_price > 0:
                    # Calculate price change from exit
                    price_ratio = (current_price / last_exit_price) * 100
                    min_drop = rebuy_config.get('min_drop_percent', 85)
                    max_allowed_ratio = 100 - min_drop  # 85% drop = 15% ratio
                    
                    if price_ratio > max_allowed_ratio:
                        drop_needed = 100 - price_ratio
                        return False, (
                            f"RE-BUY BLOCKED: Token previously exited at ${last_exit_price:.8f}. "
                            f"Current price ${current_price:.8f} ({price_ratio:.1f}% of exit). "
                            f"Needs {min_drop}% drop from exit (currently {drop_needed:.1f}%) to re-buy."
                        )
                    else:
                        logger.info(
                            f"✅ RE-BUY ALLOWED: Price dropped {100-price_ratio:.1f}% from exit "
                            f"(${last_exit_price:.8f} → ${current_price:.8f})"
                        )
        
        # CRITICAL SECTION: Check position limit with lock to prevent race condition
        async with TradeExecutor._position_lock:
            # Check position limits (chain-type aware)
            open_positions = self.pt.get_open_positions()
            max_positions = ConfigManager.get_max_positions(chain)
            
            if len(open_positions) >= max_positions:
                return False, f"Position limit reached ({len(open_positions)}/{max_positions}). Close positions before opening new ones."
            
            # Position check passed - continue with trade
            # (Recording will happen after broadcast, but slot is reserved by this lock)
        
        wallet_address = self.wm.get_address(chain)
        if not wallet_address:
            return False, f"No wallet configured for {chain}"
            
        amount_usd = ConfigManager.get_budget(chain)
        
        # 2. Get Native Token (Input)
        native_token = ConfigManager.get_chain_config(chain).get('native_token', 'ETH')
        input_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" 
        
        if chain == 'solana':
            input_token = "So11111111111111111111111111111111111111112"

        # 3. Calculate Amount
        # Rough Price Estimation (TODO: Live Oracle)
        # Using conservative price estimates to avoid overspending
        eth_price = 3500.0 
        sol_price = 200.0  
        
        if chain == 'solana':
            amount_sol = amount_usd / sol_price
            raw_amount = str(int(amount_sol * 1e9)) # Lamports
            logger.info(f"Targeting {amount_sol:.4f} SOL (${amount_usd})")
        else:
            amount_eth = amount_usd / eth_price
            raw_amount = str(int(amount_eth * 1e18)) # Wei
            logger.info(f"Targeting {amount_eth:.6f} ETH (${amount_usd})")

        logger.info(f"Executing BUY for {token_address} on {chain}...")
        
        # 4. Get Swap Data
        swap_data = await self.okx.get_swap_data(
            chain, 
            input_token, 
            token_address, 
            raw_amount, 
            15.0, # 15% Slippage (Targeting High Volatility Degen Tokens)
            wallet_address
        )
        
        if not swap_data:
            return False, "Failed to fetch swap data from OKX"
            
        # 5. Sign Transaction
        try:
            if chain == 'solana':
                tx_dict = swap_data.get('tx', {})
                if isinstance(tx_dict, dict):
                    tx_payload = tx_dict.get('data')
                else:
                    tx_payload = tx_dict
                    
                if not tx_payload:
                    return False, "No Solana tx data in response"
            else:
                tx_payload = swap_data.get('tx')
            
            signed_tx = self.wm.sign_transaction(chain, tx_payload)
        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return False, f"Signing failed: {str(e)}"
            
        # 6. Broadcast
        tx_hash = await self._broadcast_transaction(chain, signed_tx)
        if not tx_hash:
            return False, "Broadcast failed (Check RPC/Funds)"
            
        logger.info(f"Broadcast successful! Tx Hash: {tx_hash}")
        
        # 7. Record Position
        try:
            router_result = swap_data.get('routerResult', {})
            token_amount_raw = router_result.get('toTokenAmount', '0')
            token_amount = float(token_amount_raw)
            price_est = amount_usd / token_amount if token_amount > 0 else 0
        except Exception as e:
            logger.error(f"Failed to parse swap result: {e}")
            token_amount = 0
            price_est = 0

        self.pt.record_buy(
            token_address=token_address,
            chain=chain,
            wallet_address=wallet_address,
            amount=token_amount,
            price=price_est, 
            value_usd=amount_usd,
            tx_hash=tx_hash,
            signal_score=signal_score
        )
        
        return True, tx_hash

    async def execute_sell(
        self,
        chain: str,
        token_address: str,
        amount_raw: float,
        position_id: int,
        new_status: str = 'CLOSED'
    ) -> Tuple[bool, str]:
        """Execute a sell order (TP/SL)."""
        chain = chain.lower()
        wallet_address = self.wm.get_address(chain)
        
        native_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        if chain == 'solana':
            native_token = "So11111111111111111111111111111111111111112"
            
        # Format amount
        amount_str = str(int(amount_raw))
        
        logger.info(f"Executing SELL for Pos {position_id} ({amount_str} units) on {chain}...")
        logger.info(f"DEBUG: Using Wallet {wallet_address} for Swap") # DEBUG LINE
        
        try:
            # 1. Get Swap Data
            swap_data = await self.okx.get_swap_data(
                chain,
                token_address,
                native_token,
                amount_str,
                15.0, # 15% Slippage (For reliable exit)
                wallet_address
            )
            
            if not swap_data:
                return False, "Failed to get swap data"
                
            # 2. Sign
            if chain == 'solana':
                tx_payload = swap_data.get('tx', {}).get('data')
            else:
                tx_payload = swap_data.get('tx')
                
            signed_tx = self.wm.sign_transaction(chain, tx_payload)
            
            # 3. Broadcast
            tx_hash = await self._broadcast_transaction(chain, signed_tx)
            
            if not tx_hash:
                return False, "Broadcast failed"
                
            self.pt.record_sell(
                position_id=position_id,
                amount=amount_raw,
                price=0, 
                value_usd=0, 
                tx_hash=tx_hash,
                new_status=new_status
            )
            
            logger.info(f"SELL Broadcast successful! Tx Hash: {tx_hash}")
            return True, tx_hash
            
        except Exception as e:
            logger.error(f"Sell execution failed: {e}")
            return False, str(e)
    
    async def emergency_sell(self, position_id: int, reason: str = "Emergency Exit") -> bool:
        """
        Emergency sell for LP rugpull detection.
        Sells 100% of position immediately.
        
        Args:
            position_id: Position ID to exit
            reason: Reason for emergency exit (for logging)
            
        Returns:
            bool: True if successful
        """
        try:
            # Get position details from tracker
            position = self.pt.get_position(position_id)
            
            if not position:
                logger.error(f"Position {position_id} not found")
                return False
            
            chain = position['chain']
            token_address = position['token_address']
            entry_amount = float(position['entry_amount'])
            
            logger.warning(f"🚨 EMERGENCY EXIT: Position {position_id} - Reason: {reason}")
            
            # Execute 100% sell
            success, result = await self.execute_sell(
                chain=chain,
                token_address=token_address,
                amount_raw=entry_amount,
                position_id=position_id,
                new_status='EMERGENCY_EXIT'
            )
            
            if success:
                logger.info(f"✅ Emergency exit successful: {result}")
                # Record emergency exit reason in DB
                # (Position tracker already records the sell with EMERGENCY_EXIT status)
                return True
            else:
                logger.error(f"❌ Emergency exit failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Emergency sell error: {e}")
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
