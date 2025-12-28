
import unittest
import time
import os
import shutil
from core.rotation_engine import RotationEngine
from core.pattern_memory import PatternMemory
from core.pattern_matcher import PatternMatcher

class TestMarketIntel(unittest.TestCase):
    
    def setUp(self):
        # Setup temporary DB
        self.test_db = "data/test_patterns.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        self.memory = PatternMemory(self.test_db)
        self.matcher = PatternMatcher(self.memory)
        self.rotation = RotationEngine({'window_minutes': 5, 'min_confidence': 0.5})
        
    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
    def test_rotation_dominance(self):
        print("\nTesting Rotation Engine...")
        
        # Simulate Solana dominance
        for _ in range(5):
            self.rotation.add_event('solana', 'TRADE', 85)
            self.rotation.add_event('solana', 'SNIPER', 90)
            
        # Add some noise
        self.rotation.add_event('base', 'INFO', 40)
        
        insight = self.rotation.get_rotation_insight()
        print(f"Insight: {insight}")
        
        self.assertEqual(insight['rotation_bias'], 'solana')
        self.assertTrue(insight['confidence'] > 0.6)
        
        # Check bonus
        bonus = self.rotation.get_score_bonus('solana')
        self.assertEqual(bonus, 5)
        
    def test_pattern_matching(self):
        print("\nTesting Pattern Matching...")
        
        # Add historical patterns
        # Pattern 1: High score, High liq -> SUCCESS
        self.memory.add_pattern(
            chain='solana', source='raydium',
            initial_score=90, liquidity=50000,
            momentum_confirmed=True, holder_concentration=10,
            phase='TRADE', outcome='SUCCESS_3X'
        )
        # Pattern 2: Similar to 1
        self.memory.add_pattern(
            chain='solana', source='raydium',
            initial_score=85, liquidity=45000,
            momentum_confirmed=True, holder_concentration=12,
            phase='TRADE', outcome='SUCCESS_2X'
        )
        # Pattern 3: Low liq -> DUMP
        self.memory.add_pattern(
            chain='solana', source='pumpfun',
            initial_score=40, liquidity=500,
            momentum_confirmed=False, holder_concentration=80,
            phase='INFO', outcome='DUMP'
        )
        
        # Test Match: Strong token
        strong_token = {
            'chain': 'solana',
            'score': 88,
            'liquidity_usd': 48000,
            'momentum_confirmed': True,
            'holder_risk': 11
        }
        
        match = self.matcher.match_token(strong_token)
        print(f"Strong Token Match: {match}")
        
        self.assertTrue(match['pattern_similarity'] > 80)
        self.assertIn('SUCCESS_3X', match['matched_outcomes'])
        
        # Test Match: Weak token
        weak_token = {
            'chain': 'solana',
            'score': 42,
            'liquidity_usd': 600,
            'momentum_confirmed': False,
            'holder_risk': 75
        }
        
        match_weak = self.matcher.match_token(weak_token)
        print(f"Weak Token Match: {match_weak}")
        
        self.assertIn('DUMP', match_weak['matched_outcomes'])

if __name__ == '__main__':
    unittest.main()
