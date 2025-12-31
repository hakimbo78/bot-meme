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
        
        # DEBUG: Log what OKX sent us
        logger.info(f"EVM TX DICT KEYS: {list(tx_dict.keys())}")
        
        # OKX response has: data, from, gas, gasPrice, maxPriorityFeePerGas, to, value (all strings)
        # web3.py needs: to, value, data, gas, nonce, chainId, and either gasPrice OR (maxFeePerGas + maxPriorityFeePerGas)
        
        # Chain ID mapping
        chain_ids = {
            'base': 8453,
            'ethereum': 1,
            'bsc': 56,
            'arbitrum': 42161
        }
        chain_id = chain_ids.get(chain.lower(), 1)
        
        # Build transaction dict
        tx_to_sign = {
            'to': tx_dict.get('to'),
            'value': int(tx_dict.get('value', '0')),  # OKX returns string
            'data': tx_dict.get('data', '0x'),
            'gas': int(tx_dict.get('gas', '200000')),  # OKX uses 'gas' not 'gasLimit'
            'chainId': chain_id,
            'nonce': 0,  # Placeholder - in production, fetch from RPC
        }
        
        # Gas pricing
        if 'maxPriorityFeePerGas' in tx_dict:
            # EIP-1559 transaction
            max_priority_fee = int(tx_dict['maxPriorityFeePerGas'])
            
            # OKX might not provide maxFeePerGas, calculate it
            if 'gasPrice' in tx_dict:
                base_fee = int(tx_dict['gasPrice']) - max_priority_fee
                max_fee = base_fee + (max_priority_fee * 2)  # Conservative estimate
            else:
                max_fee = max_priority_fee * 3  # Fallback
                
            tx_to_sign['maxFeePerGas'] = max_fee
            tx_to_sign['maxPriorityFeePerGas'] = max_priority_fee
            tx_to_sign['type'] = 2  # EIP-1559
        elif 'gasPrice' in tx_dict:
            # Legacy transaction
            tx_to_sign['gasPrice'] = int(tx_dict['gasPrice'])

        logger.info(f"TX TO SIGN: {tx_to_sign}")

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
            import base64
            
            keypair = wallet['keypair']
            tx_bytes = base64.b64decode(tx_base64)
            
            logger.info(f"Transaction bytes length: {len(tx_bytes)}")
            
            # Manual signing approach for Solana
            # Solana transaction format:
            # [1 byte: num_signatures][signatures: 64*num_sigs][message]
            # For unsigned tx from OKX, signatures are usually zeros
            
            # Extract number of signatures (first byte)
            if len(tx_bytes) < 1:
                raise ValueError("Transaction too short")
                
            num_signatures = tx_bytes[0]
            logger.info(f"Number of signatures expected: {num_signatures}")
            
            # Calculate where message starts
            # 1 byte (num_sigs) + 64 * num_sigs (signature bytes)
            signature_section_len = 1 + (64 * num_signatures)
            
            if len(tx_bytes) < signature_section_len:
                raise ValueError(f"Transaction too short for {num_signatures} signatures")
            
            # Extract message (everything after signatures)
            message_bytes = tx_bytes[signature_section_len:]
            logger.info(f"Message bytes length: {len(message_bytes)}")
            
            # Sign the message
            signature = keypair.sign_message(message_bytes)
            signature_bytes = bytes(signature)
            logger.info(f"Signature bytes length: {len(signature_bytes)}")
            
            # Reconstruct transaction with our signature
            # Put our signature first (replacing first placeholder)
            signed_tx_bytes = bytearray()
            signed_tx_bytes.append(num_signatures)  # Keep same number of signatures
            signed_tx_bytes.extend(signature_bytes)  # Our signature (64 bytes)
            
            # Add remaining placeholder signatures if there were more than 1
            if num_signatures > 1:
                # Keep other signatures as-is (they were placeholders or other signers)
                remaining_sigs = tx_bytes[1 + 64: signature_section_len]
                signed_tx_bytes.extend(remaining_sigs)
            
            # Add the message back
            signed_tx_bytes.extend(message_bytes)
            
            # Encode back to base64
            signed_tx_base64 = base64.b64encode(bytes(signed_tx_bytes)).decode('utf-8')
            
            logger.info(f"Successfully signed transaction manually")
            logger.info(f"Signed tx length: {len(signed_tx_bytes)}")
            
            return signed_tx_base64
            
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
