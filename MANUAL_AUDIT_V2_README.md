# 🚀 Manual Audit V2 - Fully Integrated TokenSniffer Analysis

## Overview

`manual_audit_v2.py` adalah versi lengkap dari manual audit tool yang sudah **fully integrated** dengan TokenSniffer-style comprehensive security analysis.

---

## 🎯 Fitur Lengkap

### **6 Steps Comprehensive Audit:**

1. **📊 STEP 1: ON-CHAIN ANALYSIS**
   - Token Name, Symbol, Decimals
   - Total Supply
   - Contract Address

2. **💧 STEP 2: LIQUIDITY & MARKET ANALYSIS**
   - Pair Address
   - Liquidity in USD
   - Token Age
   - Liquidity Assessment

3. **🛡️ STEP 3: SECURITY AUDIT**
   - Ownership Renounced
   - Honeypot Detection
   - Mint Function Check
   - Pause Function Check
   - Blacklist Function Check
   - Security Score (0-100)

4. **🔬 STEP 3.5: TOKENSNIFFER-STYLE ANALYSIS** ⭐ NEW!
   - **📊 Swap Analysis (Honeypot Detection)**
     - Token sellable check
     - Buy fee verification
     - Sell fee verification
   - **📜 Contract Analysis**
     - Contract verification
     - Ownership status
     - Special permissions
   - **👥 Holder Analysis**
     - Tokens burned
     - Creator wallet percentage
     - Top holders distribution
   - **💧 Liquidity Analysis**
     - Current liquidity
     - Liquidity locked percentage
     - Multiple pools detection
   - **TokenSniffer Score (0-100)**

5. **⚖️ STEP 4: COMPREHENSIVE RISK SCORING**
   - Final Score (0-100)
   - Verdict (TRADE/WATCH/INFO/SKIP)
   - Risk Flags

6. **💡 STEP 5: TRADING RECOMMENDATION**
   - Overall Risk Level
   - Trading Recommendation
   - Key Insights

---

## 🚀 Cara Menggunakan

### **Command Line:**
```bash
# Audit lengkap dengan TokenSniffer analysis
python manual_audit_v2.py base 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8

# Tanpa kirim ke Telegram
python manual_audit_v2.py base 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8 --no-telegram

# Ethereum
python manual_audit_v2.py ethereum 0x6982508145454Ce325dDbE47a25d4ec3d2311933

# Solana
python manual_audit_v2.py solana 9BB62h9yHqMq9EkUNs2nH8P3Cc8wZ79S96H9FofAyxYw
```

---

## 📊 Contoh Output Lengkap

```
================================================================================
                             🔍 AUDITING BASE TOKEN
================================================================================

Token Address: 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8

────────────────────────────────────────────────────────────────────────────────
📊 STEP 1: ON-CHAIN ANALYSIS
────────────────────────────────────────────────────────────────────────────────
Fetching token data from BASE RPC...
✅ Found pair: 0xa46d5090499eFB9c5dD7d95F7ca69F996b9Fb761
✅ Analysis complete

Token Name:     Ski Mask Kitten
Symbol:         SKITTEN
Decimals:       18
Total Supply:   1,000,000,000

────────────────────────────────────────────────────────────────────────────────
💧 STEP 2: LIQUIDITY & MARKET ANALYSIS
────────────────────────────────────────────────────────────────────────────────
Pair Address:   0xa46d5090499eFB9c5dD7d95F7ca69F996b9Fb761
Liquidity:      $100,736.09
Age:            0.0 minutes (0.0 hours)
Assessment:     EXCELLENT - High liquidity

────────────────────────────────────────────────────────────────────────────────
🛡️  STEP 3: SECURITY AUDIT
────────────────────────────────────────────────────────────────────────────────
Ownership Renounced:  ✅ YES
Honeypot Detected:    ✅ NO
Mint Function:        ✅ NO
Pause Function:       ✅ NO
Blacklist Function:   ✅ NO

Security Score:       100/100 (HIGH)

────────────────────────────────────────────────────────────────────────────────
🔬 STEP 3.5: TOKENSNIFFER-STYLE ANALYSIS
────────────────────────────────────────────────────────────────────────────────
Running comprehensive security checks...

📊 Swap Analysis (Honeypot Detection):
  ✅ Token is sellable (not a honeypot)
  ✅ Buy fee is less than 5% (0.0%)
  ✅ Sell fee is less than 5% (0.0%)

📜 Contract Analysis:
  ✅ Verified contract source
  ✅ Ownership renounced or no owner contract
  ✅ Creator not authorized for special permission

👥 Holder Analysis:
  ✅ Creator wallet < 5% of supply (0%)
  ✅ All holders < 5% of supply
  ✅ Top 10 holders < 70% of supply (14.22%)

💧 Liquidity Analysis:
  ✅ Adequate current liquidity ($100,703)
  ✅ At least 95% of liquidity locked/burned (99.99%)

TokenSniffer Score:   90/100 (VERY_LOW)

────────────────────────────────────────────────────────────────────────────────
⚖️  STEP 4: COMPREHENSIVE RISK SCORING
────────────────────────────────────────────────────────────────────────────────
Final Score:    65.0/100
Verdict:        WATCH

⚠️  Risk Flags Detected:
  • ⚠️ Snapshot only (no momentum confirmation)
  • Score capped at 65 (momentum not confirmed, was 105)

────────────────────────────────────────────────────────────────────────────────
💡 STEP 5: TRADING RECOMMENDATION
────────────────────────────────────────────────────────────────────────────────
Overall Risk:   LOW

✅ LOW RISK - Suitable for trading with standard risk management

📋 Key Insights:
  • Very new token - higher volatility expected

================================================================================
                                ✅ AUDIT COMPLETE
================================================================================
```

---

## 🆚 Perbedaan dengan V1

| Feature | manual_audit.py (V1) | manual_audit_v2.py (V2) |
|---------|----------------------|-------------------------|
| Basic Security Audit | ✅ | ✅ |
| Ownership Detection | ✅ (Improved) | ✅ (Improved) |
| **TokenSniffer Analysis** | ❌ | ✅ **NEW!** |
| Honeypot Detection | ❌ | ✅ |
| Buy/Sell Fee Check | ❌ | ✅ |
| Contract Verification | ❌ | ✅ |
| Holder Distribution | ❌ | ✅ |
| Liquidity Lock Check | ❌ | ✅ |
| TokenSniffer Score | ❌ | ✅ |
| Total Steps | 5 | 6 |

---

## 📈 Scoring System

### **Security Score (Step 3)**
- Base: 100 points
- Deductions: Ownership, Honeypot, Mint, Pause, Blacklist

### **TokenSniffer Score (Step 3.5)**
- Base: 100 points
- Deductions: Honeypot (-50), Fees (-5 each), Not verified (-10), Not renounced (-15), Special permissions (-10), Bad holder distribution (-10 each), Liquidity not locked (-10)

### **Final Trading Score (Step 4)**
- Combined score from all factors
- Includes momentum and market conditions

---

## 🔗 API Dependencies

V2 menggunakan API eksternal untuk TokenSniffer analysis:
1. **Honeypot.is API** - Honeypot detection & fee simulation
2. **GoPlus Security API** - Contract verification, holder & liquidity analysis

**Note**: Kedua API gratis dengan rate limits. Jika API down, Step 3.5 akan skip dengan warning.

---

## 💡 Rekomendasi Penggunaan

### **Untuk Audit Cepat:**
```bash
python manual_audit_v2.py base 0x... --no-telegram
```

### **Untuk Audit Lengkap + Telegram:**
```bash
python manual_audit_v2.py base 0x...
```

### **Untuk Batch Audit:**
```python
from manual_audit_v2 import ManualTokenAuditor
import asyncio

async def batch_audit():
    auditor = ManualTokenAuditor()
    
    tokens = [
        ('base', '0x...'),
        ('ethereum', '0x...'),
    ]
    
    for chain, address in tokens:
        await auditor.audit_token(chain, address, send_telegram=False)

asyncio.run(batch_audit())
```

---

## ⚠️ Important Notes

1. **Rate Limits**: TokenSniffer analysis menggunakan external APIs yang memiliki rate limits. Jangan spam audit terlalu cepat.

2. **Network Errors**: Jika API down, Step 3.5 akan skip tapi audit tetap lanjut ke step berikutnya.

3. **Chain Support**: TokenSniffer analysis hanya support chains yang didukung GoPlus (Ethereum, Base, BSC, Polygon). Solana belum support.

4. **Accuracy**: TokenSniffer score bergantung pada akurasi API eksternal. Selalu cross-check dengan sumber lain.

---

## 🎓 Kesimpulan

**manual_audit_v2.py** adalah versi paling lengkap dari audit tool dengan:
- ✅ 6 steps comprehensive analysis
- ✅ TokenSniffer-style security checks
- ✅ Honeypot detection
- ✅ Holder distribution analysis
- ✅ Liquidity lock verification
- ✅ Dual scoring system (Security + TokenSniffer)

**Gunakan V2 untuk audit paling komprehensif!** 🚀

---

## 📝 Migration dari V1 ke V2

Jika Anda sudah terbiasa dengan V1, cukup ganti command:

**V1:**
```bash
python manual_audit.py base 0x...
```

**V2:**
```bash
python manual_audit_v2.py base 0x...
```

Output akan sama, tapi dengan tambahan **Step 3.5: TokenSniffer Analysis**!
