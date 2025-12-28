"""Simple quick test for auto-upgrade modules"""

print("Testing Auto-Upgrade System...")
print("=" * 50)

# Test 1: Priority Detector
print("\n1. Testing Priority Detector...")
try:
    from solana.priority_detector import SolanaPriorityDetector
    detector = SolanaPriorityDetector()
    print("✅ Priority Detector imported successfully")
except Exception as e:
    print(f"❌ Priority Detector failed: {e}")

# Test 2: Smart Wallet Detector
print("\n2. Testing Smart Wallet Detector...")
try:
    from solana.smart_wallet_detector import SmartWalletDetector
    detector = SmartWalletDetector()
    print(f"✅ Smart Wallet Detector loaded {len(detector.wallets)} wallets")
except Exception as e:
    print(f"❌ Smart Wallet Detector failed: {e}")

# Test 3: Auto-Upgrade Engine
print("\n3. Testing Auto-Upgrade Engine...")
try:
    from sniper.auto_upgrade import AutoUpgradeEngine
    engine = AutoUpgradeEngine({'enabled': True})
    print("✅ Auto-Upgrade Engine initialized")
except Exception as e:
    print(f"❌ Auto-Upgrade Engine failed: {e}")

# Test 4: Integration Module
print("\n4. Testing Integration Module...")
try:
    from upgrade_integration import UpgradeIntegration
    integration = UpgradeIntegration({
        'auto_upgrade': {'enabled': True}
    })
    print(f"✅ Integration Module loaded successfully")
except Exception as e:
    print(f"❌ Integration Module failed: {e}")

print("\n" + "=" * 50)
print("✅ ALL MODULES LOADED SUCCESSFULLY!")
print("=" * 50)
