
import unittest
import time
from intelligence.narrative_engine import NarrativeEngine
from intelligence.smart_money_engine import SmartMoneyEngine, WalletCluster
from intelligence.conviction_engine import ConvictionEngine

class TestPhase5Analysis(unittest.TestCase):
    
    def setUp(self):
        self.narrative = NarrativeEngine()
        self.smart_money = SmartMoneyEngine()
        self.conviction = ConvictionEngine()
        
    def test_narrative_detection(self):
        print("\nTesting Narrative Engine...")
        
        # Test AI Agent narrative
        token = {'name': 'AgentSmith', 'symbol': 'AGENT'}
        
        # Hit it 6 times to trigger trend
        for _ in range(6):
            result = self.narrative.analyze_token(token)
            
        print(f"Narrative Result: {result}")
        self.assertEqual(result['narrative'], 'AI_AGENT')
        self.assertEqual(result['trend'], 'RISING')
        self.assertTrue(result['confidence'] >= 1.0)
        
    def test_wallet_classification(self):
        print("\nTesting Wallet Cluster...")
        cluster = WalletCluster()
        
        wallet = "0x123"
        # Simulate Tier 1 behavior: 3 wins, 3 early entries
        cluster.update_wallet(wallet, True, True, False)
        cluster.update_wallet(wallet, True, True, False)
        cluster.update_wallet(wallet, True, True, False)
        
        tier = cluster.classify(wallet)
        print(f"Wallet Tier: {tier}")
        self.assertEqual(tier, 'TIER_1')
        
    def test_conviction_scoring(self):
        print("\nTesting Conviction Engine...")
        
        # Mock inputs
        n_data = {'narrative': 'AI_AGENT', 'confidence': 1.0, 'trend': 'RISING'}
        sm_data = {'tier1_wallets': 2, 'tier2_wallets': 1} # (2*15) + 5 = 35 pts (max)
        rot_data = {'rotation_bias': 'solana', 'confidence': 0.8, 'is_aligned': True} # 0.8 * 20 = 16 pts
        pat_data = {'pattern_similarity': 90} # 0.9 * 20 = 18 pts
        
        # Expected Score:
        # Narrative: 25 * 1.0 * 1.2 (boost) = 30 -> max 25
        # SM: 35
        # Rot: 16
        # Pat: 18
        # Total: 25 + 35 + 16 + 18 = 94
        
        result = self.conviction.calculate_conviction(n_data, sm_data, rot_data, pat_data)
        print(f"Conviction Result: {result}")
        
        self.assertTrue(result['conviction_score'] >= 90)
        self.assertEqual(result['verdict'], 'RARE ASYMMETRIC')

if __name__ == '__main__':
    unittest.main()
