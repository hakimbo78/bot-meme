"""
Solana TX Priority Detector

Analyzes Solana transactions for priority signals:
- High compute units consumed (>200k)
- Priority fees (fee - base_fee)
- Jito tip detection via system transfers

READ-ONLY informational system.
NO trading execution.

Output:
- priority_score (max 50)
- is_priority flag
- priority_reasons list
"""

import time
from typing import Dict, List, Optional, Any

# Known Jito tip accounts (as of 2025)
JITO_TIP_ACCOUNTS = [
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PvwucfZ2bU7gRe",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
    "ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49",
    "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
    "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
    "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
    "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT"
]

# Base fee for Solana transactions (lamports)
SOLANA_BASE_FEE = 5000  # 0.000005 SOL


class SolanaPriorityDetector:
    """
    Detects priority transactions on Solana.
    
    Features:
    - Compute unit spike detection
    - Priority fee calculation
    - Jito tip detection
    
    Scoring:
    - High compute: +15 points
    - Priority fee: +20 points
    - Jito tip: +15 points
    - Max: 50 points
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize priority detector.
        
        Args:
            config: Optional configuration dict with thresholds
        """
        self.config = config or {}
        
        # Thresholds (from config or defaults)
        self.compute_threshold = self.config.get('compute_threshold', 200000)  # 200k units
        self.priority_fee_threshold = self.config.get('priority_fee_threshold', 10000)  # 0.00001 SOL
        self.min_jito_tip = self.config.get('min_jito_tip', 10000)  # 0.00001 SOL
        
        # Scoring weights
        self.score_compute = self.config.get('score_compute', 15)
        self.score_priority_fee = self.config.get('score_priority_fee', 20)
        self.score_jito_tip = self.config.get('score_jito_tip', 15)
        self.max_score = 50
        
        # Cache for preventing duplicate processing
        self.processed_txs = {}
        self.cache_max_size = 1000
        
    def analyze_transaction(self, tx_data: Dict) -> Dict:
        """
        Analyze a transaction for priority signals.
        
        Args:
            tx_data: Transaction data dict containing:
                - signature: str
                - meta: dict with fee, computeUnitsConsumed
                - transaction: dict with message containing instructions
        
        Returns:
            Dict with:
                - priority_score: int (0-50)
                - is_priority: bool
                - priority_reasons: List[str]
                - compute_units: int
                - priority_fee: int (lamports)
                - jito_tip: int (lamports)
                - jito_tip_account: Optional[str]
        """
        signature = tx_data.get('signature', '')
        
        # Check cache
        if signature in self.processed_txs:
            return self.processed_txs[signature]
        
        result = {
            'priority_score': 0,
            'is_priority': False,
            'priority_reasons': [],
            'compute_units': 0,
            'priority_fee': 0,
            'jito_tip': 0,
            'jito_tip_account': None
        }
        
        try:
            # Extract metadata
            meta = tx_data.get('meta', {})
            transaction = tx_data.get('transaction', {})
            
            # 1. Check compute units consumed
            compute_units = meta.get('computeUnitsConsumed', 0)
            result['compute_units'] = compute_units
            
            if compute_units > self.compute_threshold:
                result['priority_score'] += self.score_compute
                result['priority_reasons'].append(
                    f"High compute: {compute_units:,} units (>{self.compute_threshold:,})"
                )
            
            # 2. Check priority fee
            total_fee = meta.get('fee', SOLANA_BASE_FEE)
            priority_fee = max(0, total_fee - SOLANA_BASE_FEE)
            result['priority_fee'] = priority_fee
            
            if priority_fee > self.priority_fee_threshold:
                result['priority_score'] += self.score_priority_fee
                priority_sol = priority_fee / 1e9
                result['priority_reasons'].append(
                    f"Priority fee: {priority_sol:.6f} SOL"
                )
            
            # 3. Check for Jito tips
            jito_info = self._detect_jito_tip(transaction)
            if jito_info['detected']:
                result['jito_tip'] = jito_info['amount']
                result['jito_tip_account'] = jito_info['account']
                result['priority_score'] += self.score_jito_tip
                tip_sol = jito_info['amount'] / 1e9
                result['priority_reasons'].append(
                    f"Jito tip: {tip_sol:.6f} SOL to {jito_info['account'][:8]}..."
                )
            
            # Cap score at max
            result['priority_score'] = min(result['priority_score'], self.max_score)
            result['is_priority'] = result['priority_score'] > 0
            
            # Cache result
            self._cache_result(signature, result)
            
            return result
            
        except Exception as e:
            print(f"[PRIORITY] Error analyzing transaction: {e}")
            return result
    
    def _detect_jito_tip(self, transaction: Dict) -> Dict:
        """
        Detect Jito tip in transaction instructions.
        
        Jito tips are system transfers to known Jito accounts.
        
        Args:
            transaction: Transaction dict
        
        Returns:
            Dict with:
                - detected: bool
                - amount: int (lamports)
                - account: str (recipient)
        """
        result = {
            'detected': False,
            'amount': 0,
            'account': None
        }
        
        try:
            message = transaction.get('message', {})
            instructions = message.get('instructions', [])
            account_keys = message.get('accountKeys', [])
            
            # Look for system transfers to Jito accounts
            for ix in instructions:
                # Check if this is a system program transfer
                program_id_index = ix.get('programIdIndex')
                if program_id_index is not None:
                    program_id = account_keys[program_id_index] if program_id_index < len(account_keys) else None
                    
                    # System Program: 11111111111111111111111111111111
                    if program_id == "11111111111111111111111111111111":
                        # Check destination account
                        accounts = ix.get('accounts', [])
                        if len(accounts) >= 2:
                            to_index = accounts[1]
                            to_account = account_keys[to_index] if to_index < len(account_keys) else None
                            
                            if to_account in JITO_TIP_ACCOUNTS:
                                # Parse transfer amount from instruction data
                                # System transfer instruction format: [2, 0, 0, 0, amount_bytes...]
                                data = ix.get('data', '')
                                if data:
                                    try:
                                        # Decode base58 data and extract amount
                                        # Simplified - real implementation would decode properly
                                        # For now, flag as detected with minimum tip
                                        result['detected'] = True
                                        result['amount'] = self.min_jito_tip
                                        result['account'] = to_account
                                        break
                                    except:
                                        pass
            
            return result
            
        except Exception as e:
            print(f"[PRIORITY] Error detecting Jito tip: {e}")
            return result
    
    def batch_analyze(self, transactions: List[Dict]) -> List[Dict]:
        """
        Analyze multiple transactions for priority signals.
        
        Args:
            transactions: List of transaction dicts
        
        Returns:
            List of analysis results
        """
        results = []
        for tx in transactions:
            result = self.analyze_transaction(tx)
            results.append(result)
        
        return results
    
    def get_priority_summary(self, tx_results: List[Dict]) -> Dict:
        """
        Get summary of priority signals across multiple transactions.
        
        Args:
            tx_results: List of transaction analysis results
        
        Returns:
            Dict with:
                - total_txs: int
                - priority_txs: int
                - avg_priority_score: float
                - max_priority_score: int
                - total_jito_tips: int (lamports)
        """
        if not tx_results:
            return {
                'total_txs': 0,
                'priority_txs': 0,
                'avg_priority_score': 0,
                'max_priority_score': 0,
                'total_jito_tips': 0
            }
        
        priority_txs = [r for r in tx_results if r.get('is_priority', False)]
        priority_scores = [r.get('priority_score', 0) for r in priority_txs]
        
        return {
            'total_txs': len(tx_results),
            'priority_txs': len(priority_txs),
            'avg_priority_score': sum(priority_scores) / len(priority_scores) if priority_scores else 0,
            'max_priority_score': max(priority_scores) if priority_scores else 0,
            'total_jito_tips': sum(r.get('jito_tip', 0) for r in priority_txs)
        }
    
    def _cache_result(self, signature: str, result: Dict):
        """Cache transaction result to prevent duplicate processing."""
        if len(self.processed_txs) >= self.cache_max_size:
            # Remove oldest 20% of entries
            remove_count = int(self.cache_max_size * 0.2)
            keys_to_remove = list(self.processed_txs.keys())[:remove_count]
            for key in keys_to_remove:
                del self.processed_txs[key]
        
        self.processed_txs[signature] = result
    
    def clear_cache(self):
        """Clear transaction cache."""
        self.processed_txs.clear()
