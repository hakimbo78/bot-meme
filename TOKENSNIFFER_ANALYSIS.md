# 🔬 TokenSniffer-Style Security Analysis

## Overview

Saya telah menambahkan **TokenSniffer-style comprehensive security analysis** ke bot, yang memberikan audit mendalam seperti yang dilakukan oleh TokenSniffer.com.

---

## 🎯 Fitur Yang Ditambahkan

### **1. Swap Analysis (Honeypot Detection)** 📊
Menggunakan API honeypot.is untuk mendeteksi:
- ✅ **Is Honeypot?** - Apakah token bisa dijual atau tidak
- ✅ **Buy Fee** - Persentase fee saat buy (harus < 5%)
- ✅ **Sell Fee** - Persentase fee saat sell (harus < 5%)
- ✅ **Swap Simulation** - Simulasi buy/sell berhasil atau tidak

**Contoh Output:**
```
📊 Swap Analysis (Honeypot Detection):
  ✅ Token is sellable (not a honeypot)
  ✅ Buy fee is less than 5% (0.0%)
  ✅ Sell fee is less than 5% (0.0%)
```

---

### **2. Contract Analysis** 📜
Memeriksa keamanan smart contract:
- ✅ **Contract Verified** - Source code terverifikasi di block explorer
- ✅ **Ownership Renounced** - Owner sudah renounce atau tidak ada owner
- ✅ **Special Permissions** - Creator tidak punya permission khusus
- ✅ **Mint Function** - Apakah bisa mint token baru
- ✅ **Pause Function** - Apakah bisa pause trading
- ✅ **Blacklist Function** - Apakah bisa blacklist wallet

**Contoh Output:**
```
📜 Contract Analysis:
  ✅ Verified contract source
  ✅ Ownership renounced or no owner contract
  ✅ Creator not authorized for special permission
```

---

### **3. Holder Analysis** 👥
Analisis distribusi holder:
- ✅ **Tokens Burned** - Persentase token yang dibakar
- ✅ **Creator Wallet** - Persentase token di wallet creator (harus < 5%)
- ✅ **Max Holder** - Holder terbesar (harus < 5%)
- ✅ **Top 10 Holders** - Total top 10 holders (harus < 70%)
- ✅ **Holder Count** - Jumlah total holder

**Contoh Output:**
```
👥 Holder Analysis:
  🔥 Tokens burned: 2.61%
  ✅ Creator wallet < 5% of supply (0%)
  ✅ All holders < 5% of supply
  ✅ Top 10 holders < 70% of supply (14.22%)
```

---

### **4. Liquidity Analysis** 💧
Memeriksa likuiditas dan lock status:
- ✅ **Current Liquidity** - Likuiditas saat ini dalam USD
- ✅ **Liquidity Locked** - Persentase liquidity yang di-lock
- ✅ **Lock Duration** - Berapa lama liquidity di-lock
- ✅ **Multiple Pools** - Jumlah pool yang terdeteksi

**Contoh Output:**
```
💧 Liquidity Analysis:
  ✅ Adequate current liquidity ($100,703)
  ✅ At least 95% of liquidity locked/burned (99.99%)
  ✅ Multiple DEX pools detected (Uniswap V2, V3)
```

---

## 📊 Overall Score Calculation

Bot menghitung **TokenSniffer Score (0-100)** berdasarkan:

### **Scoring System:**
```
Base Score: 100 points

Deductions:
- Honeypot detected: -50 points
- High buy fee (≥5%): -5 points
- High sell fee (≥5%): -5 points
- Contract not verified: -10 points
- Ownership not renounced: -15 points
- Creator has special permissions: -10 points
- Creator wallet ≥5%: -10 points
- Top 10 holders ≥70%: -10 points
- Liquidity not locked: -10 points
```

### **Risk Levels:**
- **90-100**: VERY_LOW (Excellent - Very safe)
- **75-89**: LOW (Good - Safe for trading)
- **60-74**: MEDIUM (Moderate - Trade with caution)
- **40-59**: HIGH (High risk - Extreme caution)
- **0-39**: CRITICAL (Do not trade)

---

## 🚀 Cara Menggunakan

### **Method 1: Demo Script**
```bash
python demo_tokensniffer.py base 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8
```

### **Method 2: Programmatic**
```python
from tokensniffer_analyzer import TokenSnifferAnalyzer
from multi_scanner import MultiChainScanner
from config import CHAIN_CONFIGS

# Initialize
scanner = MultiChainScanner(['base'], CHAIN_CONFIGS.get('chains', {}))
adapter = scanner.get_adapter('base')
ts_analyzer = TokenSnifferAnalyzer(adapter.w3, 'base')

# Run analysis
result = ts_analyzer.analyze_comprehensive('0x4B6104755AfB5Da4581B81C552DA3A25608c73B8')

# Get score
print(f"Score: {result['overall_score']}/100")
print(f"Risk: {result['risk_level']}")
```

---

## 📋 Contoh Output Lengkap

```
================================================================================
                    TOKENSNIFFER-STYLE SECURITY ANALYSIS
================================================================================

Chain: BASE
Token: 0x4B6104755AfB5Da4581B81C552DA3A25608c73B8

Running comprehensive security checks...

────────────────────────────────────────────────────────────────────────────────
📊 SWAP ANALYSIS (Honeypot Detection)
────────────────────────────────────────────────────────────────────────────────
  ✅ Token is sellable (not a honeypot)
  ✅ Buy fee is less than 5% (0.0%)
  ✅ Sell fee is less than 5% (0.0%)

────────────────────────────────────────────────────────────────────────────────
📜 CONTRACT ANALYSIS
────────────────────────────────────────────────────────────────────────────────
  ✅ Verified contract source
  ✅ Ownership renounced or no owner contract
  ✅ Creator not authorized for special permission

────────────────────────────────────────────────────────────────────────────────
👥 HOLDER ANALYSIS
────────────────────────────────────────────────────────────────────────────────
  🔥 Tokens burned: 2.61%
  ✅ Creator wallet < 5% of supply (0%)
  ✅ All holders < 5% of supply
  ✅ Top 10 holders < 70% of supply (14.22%)

────────────────────────────────────────────────────────────────────────────────
💧 LIQUIDITY ANALYSIS
────────────────────────────────────────────────────────────────────────────────
  ✅ Adequate current liquidity ($100,703)
  ✅ At least 95% of liquidity locked/burned (99.99%)

================================================================================
                              OVERALL ASSESSMENT
================================================================================

TokenSniffer Score: 90/100
Risk Level: VERY_LOW

✅ EXCELLENT - Very safe for trading

================================================================================
```

---

## 🔗 API Dependencies

TokenSniffer analyzer menggunakan 2 API eksternal:

### **1. Honeypot.is API**
- **URL**: `https://api.honeypot.is/v2/IsHoneypot`
- **Purpose**: Honeypot detection, buy/sell fee simulation
- **Free**: Yes (with rate limits)

### **2. GoPlus Security API**
- **URL**: `https://api.gopluslabs.io/api/v1/token_security/{chain_id}`
- **Purpose**: Contract verification, holder analysis, liquidity checks
- **Free**: Yes (with rate limits)

---

## ⚠️ Limitasi

1. **API Rate Limits**: Kedua API memiliki rate limit, jangan spam request
2. **Chain Support**: Hanya support chain yang didukung oleh GoPlus (Ethereum, Base, BSC, Polygon)
3. **Data Accuracy**: Bergantung pada akurasi API eksternal
4. **Network Errors**: Jika API down, analysis akan skip dengan warning

---

## 🆚 Perbandingan dengan TokenSniffer.com

| Feature | TokenSniffer.com | Bot Kita |
|---------|------------------|----------|
| Honeypot Detection | ✅ | ✅ |
| Buy/Sell Fee Check | ✅ | ✅ |
| Contract Verification | ✅ | ✅ |
| Ownership Check | ✅ | ✅ |
| Holder Analysis | ✅ | ✅ |
| Liquidity Lock Check | ✅ | ✅ |
| Overall Score | ✅ | ✅ |
| Real-time Updates | ✅ | ⚠️ (On-demand) |
| Historical Data | ✅ | ❌ |
| Source Code Analysis | ✅ | ⚠️ (Via API) |

---

## 🎓 Kesimpulan

Bot sekarang memiliki kemampuan audit security yang **setara dengan TokenSniffer**, memberikan:

1. ✅ **Honeypot Detection** - Deteksi scam token
2. ✅ **Contract Security** - Verifikasi keamanan contract
3. ✅ **Holder Distribution** - Analisis distribusi holder
4. ✅ **Liquidity Analysis** - Cek liquidity lock
5. ✅ **Overall Score** - Score 0-100 seperti TokenSniffer

**Hasil audit sekarang lebih komprehensif dan akurat!** 🚀

---

## 📝 Files Added

1. **tokensniffer_analyzer.py** - Core TokenSniffer-style analyzer
2. **demo_tokensniffer.py** - Demo script untuk testing
3. **TOKENSNIFFER_ANALYSIS.md** - Dokumentasi ini

---

## 🔄 Next Steps

Untuk mengintegrasikan ke manual_audit.py:
1. Import TokenSnifferAnalyzer
2. Tambahkan Step 3.5 untuk TokenSniffer analysis
3. Include TokenSniffer score di Telegram report
4. Combine dengan existing security score untuk final verdict

**Status**: ✅ Core functionality complete, ready for integration
