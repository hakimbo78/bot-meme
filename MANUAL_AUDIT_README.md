# Manual Token Audit Tool

Alat audit manual yang komprehensif untuk menganalisis token di Base, Ethereum, dan Solana.

## Fitur Utama

### 🔍 Analisis Mendalam
- **On-Chain Analysis**: Mengambil data langsung dari blockchain
- **Security Audit**: Memeriksa ownership, honeypot, mint function, pause, blacklist
- **Liquidity Analysis**: Evaluasi likuiditas dan risiko slippage
- **Risk Scoring**: Skor keamanan dan trading score komprehensif
- **Trading Recommendation**: Rekomendasi berdasarkan analisis mendalam

### 🛡️ Security Checks

#### EVM (Base & Ethereum):
- ✅ Ownership Renounced
- ✅ Honeypot Detection
- ✅ Mint Function Check
- ✅ Pause Function Check
- ✅ Blacklist Function Check
- ✅ Liquidity Validation
- ✅ Contract Age Analysis

#### Solana:
- ✅ Metadata Resolution
- ✅ LP Validation
- ✅ Liquidity Analysis
- ✅ Token State Verification

### 📊 Scoring System

**Security Score (0-100)**:
- Ownership renounced: +30 points
- No honeypot: +50 points
- No mint function: +10 points
- No pause function: +5 points
- No blacklist: +5 points

**Trading Score (0-100)**:
- Menggunakan sistem scoring bot yang sudah ada
- Menggabungkan faktor liquidity, volume, age, dll

**Overall Risk Level**:
- 🟢 **LOW**: Aman untuk trading dengan risk management standar
- 🟡 **MEDIUM**: Cocok untuk trader berpengalaman
- 🔴 **HIGH**: Trade dengan sangat hati-hati, posisi kecil
- ⛔ **CRITICAL**: JANGAN TRADE - masalah keamanan kritis

## Cara Penggunaan

### Command Line

```bash
# Base Network
python manual_audit.py base 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b

# Ethereum Network
python manual_audit.py ethereum 0x6982508145454Ce325dDbE47a25d4ec3d2311933

# Solana Network
python manual_audit.py solana 9BB62h9yHqMq9EkUNs2nH8P3Cc8wZ79S96H9FofAyxYw

# Tanpa kirim ke Telegram
python manual_audit.py base 0x... --no-telegram
```

### Output Example

```
================================================================================
                        🔍 AUDITING BASE TOKEN
================================================================================

Token Address: 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b

────────────────────────────────────────────────────────────────────────────────
📊 STEP 1: ON-CHAIN ANALYSIS
────────────────────────────────────────────────────────────────────────────────
Fetching token data from BASE RPC...
✅ Analysis complete

Token Name:     Virtual Protocol
Symbol:         VIRTUAL
Decimals:       18
Total Supply:   1,000,000,000

────────────────────────────────────────────────────────────────────────────────
💧 STEP 2: LIQUIDITY & MARKET ANALYSIS
────────────────────────────────────────────────────────────────────────────────
Pair Address:   0x212f06742510AAd53239eFAd58117796dcb7e09E
Liquidity:      $1,234,567.89
Age:            1440.0 minutes (24.0 hours)
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
⚖️  STEP 4: COMPREHENSIVE RISK SCORING
────────────────────────────────────────────────────────────────────────────────
Final Score:    85.5/100
Verdict:        TRADE

✅ No major risk flags detected

────────────────────────────────────────────────────────────────────────────────
💡 STEP 5: TRADING RECOMMENDATION
────────────────────────────────────────────────────────────────────────────────
Overall Risk:   LOW

✅ LOW RISK - Suitable for trading with standard risk management

📋 Key Insights:
  (No critical issues detected)

================================================================================
                            ✅ AUDIT COMPLETE
================================================================================

✅ Audit report sent to Telegram
```

## Telegram Integration

Jika Telegram dikonfigurasi (`.env` memiliki `TELEGRAM_BOT_TOKEN` dan `TELEGRAM_CHAT_ID`), audit report akan otomatis dikirim ke Telegram dengan format:

```
🔍 MANUAL TOKEN AUDIT REPORT

Chain: BASE
Token: Virtual Protocol (VIRTUAL)
Address: 0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b

📊 Scores:
• Security Score: 100/100
• Trading Score: 85.5/100
• Verdict: TRADE

🛡️ Risk Assessment:
• Overall Risk: 🟢 LOW

💡 Recommendation:
✅ LOW RISK - Suitable for trading with standard risk management

⚠️ Manual audit - Always DYOR before trading.
```

## Interpretasi Hasil

### Security Score
- **90-100**: Sangat aman, semua security checks passed
- **70-89**: Aman, beberapa minor issues
- **50-69**: Moderate risk, perlu perhatian ekstra
- **0-49**: High risk, hindari atau trade dengan sangat hati-hati

### Trading Score
- **75-100**: TRADE - Signal kuat
- **60-74**: WATCH - Pantau perkembangan
- **40-59**: INFO - Informasi saja
- **0-39**: SKIP - Tidak recommended

### Risk Flags
Perhatikan risk flags yang muncul:
- 🔴 "Owner not renounced" - Pemilik masih bisa ubah kontrak
- 🔴 "Honeypot detected" - Tidak bisa dijual
- 🟡 "Low liquidity" - Slippage tinggi
- 🟡 "Very new token" - Volatilitas tinggi
- 🟡 "Mint function exists" - Supply bisa ditambah

## Tips Penggunaan

1. **Selalu audit sebelum trade**: Jangan percaya hype, verify sendiri
2. **Perhatikan liquidity**: Minimum $10,000 untuk trading aman
3. **Check ownership**: Renounced ownership = lebih aman
4. **Avoid honeypots**: Jika terdeteksi honeypot, JANGAN TRADE
5. **Risk management**: Bahkan token "LOW RISK" tetap perlu stop loss

## Troubleshooting

### "No adapter available"
- Pastikan RPC URL dikonfigurasi di `chains.yaml`
- Check koneksi internet

### "Failed to analyze token"
- Token address mungkin salah
- Token belum memiliki liquidity pool
- RPC timeout - coba lagi

### "Solana scanner not available"
- Install dependencies Solana: `pip install solders solana`
- Check Solana RPC di `chains.yaml`

## Advanced Usage

### Programmatic Usage

```python
from manual_audit import ManualTokenAuditor
import asyncio

async def audit_multiple_tokens():
    auditor = ManualTokenAuditor()
    
    tokens = [
        ('base', '0x...'),
        ('ethereum', '0x...'),
        ('solana', '9BB...')
    ]
    
    for chain, address in tokens:
        report = await auditor.audit_token(chain, address, send_telegram=False)
        if report:
            print(f"Risk: {report['overall_risk']}")
            print(f"Score: {report['score_data']['score']}")

asyncio.run(audit_multiple_tokens())
```

## Limitasi

- **RPC Rate Limits**: Jika terlalu banyak request, mungkin kena rate limit
- **Data Accuracy**: Data seakurat RPC provider
- **No Historical Data**: Hanya snapshot saat ini
- **Manual Process**: Tidak otomatis, harus run manual per token

## Keamanan

⚠️ **DISCLAIMER**: Tool ini hanya memberikan informasi teknis. Bukan financial advice. Selalu:
- DYOR (Do Your Own Research)
- Gunakan risk management
- Jangan invest lebih dari yang sanggup hilang
- Crypto trading berisiko tinggi

## Support

Untuk pertanyaan atau issues, check:
- Main bot documentation
- `README.md` di root project
- Telegram bot untuk notifikasi real-time
