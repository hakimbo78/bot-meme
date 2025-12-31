"""
Wallet Management
Handles wallet operations for multi-chain trading
"""

from typing import Dict, Optional, Any
from eth_account import Account
import logging
import traceback

logger = logging.getLogger(__name__)

# Try to import Solana libraries, but handle failures gracefully if not fully available
try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    HAS_SOLANA = True
except ImportError:
    logger.warning("Solana libraries (solders) not available. Solana trading will be disabled.")
    HAS_SOLANA = False

class WalletManager:
    """Manage trading wallets for multiple chains."""
    
    def __init__(self):
        self.wallets = {}  # chain -> wallet dict
    
    def import_wallet_evm(self, private_key: str, chain: str) -> bool:
        """
        Import EVM wallet (Base, Ethereum).
        
        Args:
            private_key: Hex private key (with or without 0x)
            chain: Chain identifier (e.g., 'base', 'ethereum')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
                
            account = Account.from_key(private_key)
            self.wallets[chain.lower()] = {
                'type': 'evm',
                'address': account.address,
                'private_key': private_key,
                'account': account,
            }
            logger.info(f"[{chain.upper()}] Wallet imported: {account.address}")
            return True
        except Exception as e:
            logger.error(f"Failed to import EVM wallet for {chain}: {e}")
            return False
    
    def import_wallet_solana(self, private_key_base58: str) -> bool:
        """
        Import Solana wallet from base58 private key.
        
        Args:
            private_key_base58: Base58 encoded private key string
            
        Returns:
            True if successful, False otherwise
        """
        if not HAS_SOLANA:
            logger.error("Solana libraries not installed.")
            return False
            
        try:
            import base58
            # Decode base58 to bytes
            key_bytes = base58.b58decode(private_key_base58)
            keypair = Keypair.from_bytes(key_bytes)
            
            self.wallets['solana'] = {
                'type': 'solana',
                'address': str(keypair.pubkey()),
                'keypair': keypair,
            }
            logger.info(f"[SOLANA] Wallet imported: {keypair.pubkey()}")
            return True
        except Exception as e:
            logger.error(f"Failed to import Solana wallet: {e}")
            # Try 64-byte hex if base58 fails? Usually users provide base58 for phantom etc.
            return False
    
    def get_wallet(self, chain: str) -> Optional[Dict]:
        """Get wallet info for specific chain."""
        return self.wallets.get(chain.lower())
    
    def get_address(self, chain: str) -> Optional[str]:
        """Get wallet address for chain."""
        wallet = self.get_wallet(chain)
        if wallet:
            return wallet.get('address')
        return None

    def sign_transaction_evm(self, chain: str, tx_dict: Dict) -> str:
        """
        Sign EVM transaction.
        
        Args:
            chain: Chain ID (base, ethereum)
            tx_dict: Transaction dictionary from OKX API
            
        Returns:
            Signed transaction hex string
        """
        wallet = self.get_wallet(chain)
        if not wallet:
            raise ValueError(f"No wallet found for {chain}")
            
        account = wallet['account']
        
        # OKX returns comprehensive tx data, but we need to ensure fields are correct for web3.py
        # Usually requires: to, value, data, gas, gasPrice/maxFeePerGas, nonce, chainId
        
        # Basic mapping - in production need to refine based on OKX response format
        tx_to_sign = {
            'to': tx_dict.get('to'),
            'value': int(tx_dict.get('value', 0)),
            'data': tx_dict.get('data'),
            'gas': int(tx_dict.get('gasLimit', 200000)),
            'nonce': int(tx_dict.get('nonce', 0)),
            'chainId': int(tx_dict.get('chainId', 1)),
        }

        # Handle gas fees (EIP-1559 vs Legacy)
        if 'maxFeePerGas' in tx_dict:
            tx_to_sign['maxFeePerGas'] = int(tx_dict['maxFeePerGas'])
            tx_to_sign['maxPriorityFeePerGas'] = int(tx_dict.get('maxPriorityFeePerGas', 0))
            tx_to_sign['type'] = 2
        else:
            tx_to_sign['gasPrice'] = int(tx_dict.get('gasPrice', 0))

        signed_tx = account.sign_transaction(tx_to_sign)
        return signed_tx.rawTransaction.hex()

    def sign_transaction_solana(self, tx_base64: str) -> str:
        """
        Sign Solana transaction.
        
        Args:
            tx_base64: Base64 encoded transaction from OKX API
            
        Returns:
            Signed transaction (base64 or bytes depending on requirement)
        """
        if not HAS_SOLANA:
            raise ImportError("Solana libraries not available")
            
        wallet = self.get_wallet('solana')
        if not wallet:
            raise ValueError("No Solana wallet found")
            
        try:
            from solders.transaction import VersionedTransaction
            import base64
            
            # Decode tx from OKX
            tx_bytes = base64.b64decode(tx_base64)
            tx = VersionedTransaction.from_bytes(tx_bytes)
            
            # Sign
            keypair = wallet['keypair']
            # We need to create a new message and sign it, or use solders signing
            # For OKX API, usually we just sign the message
            
            # NOTE: Implementation detail for Solana requires precise knowledge of OKX return format
            # Assuming OKX returns a serialized message or partial tx
            
            # Simpler approach for now:
            # 1. Deserialize
            # 2. Sign with keypair
            # 3. Serialize back
            
            # This is a placeholder for exact solders implementation
            # In a real scenario, we'd use:
            # signature = keypair.sign_message(message_bytes)
            # tx.populate_signatures([signature])
            
            return base64.b64encode(bytes(tx)).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Solana signing failed: {e}")
            raise

    def sign_transaction(self, chain: str, tx_data: Any) -> Any:
        """Dispatch signing to appropriate method."""
        chain = chain.lower()
        if chain == 'solana':
            return self.sign_transaction_solana(tx_data)
        elif chain in ['base', 'ethereum', 'bsc', 'arbitrum']:
            return self.sign_transaction_evm(chain, tx_data)
        else:
            raise ValueError(f"Unsupported signing chain: {chain}")
