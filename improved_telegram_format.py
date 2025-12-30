"""
Improved Telegram Alert Format for Manual Audit V2

Creates a clean, readable, and comprehensive Telegram report including:
- All 6 audit steps
- TokenSniffer analysis
- Better formatting with emojis and sections
- Cleaner layout
"""

def create_improved_telegram_message(audit_report: dict) -> str:
    """
    Create improved, readable Telegram message.
    
    Format:
    - Header with token info
    - Quick Summary (scores at a glance)
    - Detailed sections (collapsible)
    - Final recommendation
    """
    
    chain = audit_report['chain'].upper()
    token_address = audit_report['token_address']
    analysis = audit_report['analysis']
    score_data = audit_report['score_data']
    security_score = audit_report['security_score']
    tokensniffer_result = audit_report.get('tokensniffer_result')
    overall_risk = audit_report['overall_risk']
    recommendation = audit_report['recommendation']
    
    # Risk emoji
    risk_emoji = {
        'LOW': '🟢',
        'MEDIUM': '🟡',
        'HIGH': '🔴',
        'CRITICAL': '⛔',
        'VERY_LOW': '🟢'
    }
    
    # === HEADER ===
    message = f"""🔍 *MANUAL TOKEN AUDIT REPORT*

*Chain:* {chain}
*Token:* {analysis.get('name', 'UNKNOWN')} (`{analysis.get('symbol', '???')}`)
*Address:* `{token_address[:8]}...{token_address[-6:]}`

"""
    
    # === QUICK SUMMARY ===
    message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *QUICK SUMMARY*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Security Score
    sec_emoji = '🟢' if security_score >= 80 else '🟡' if security_score >= 50 else '🔴'
    message += f"{sec_emoji} *Security Score:* `{security_score}/100`\n"
    
    # TokenSniffer Score (if available)
    if tokensniffer_result:
        ts_score = tokensniffer_result.get('overall_score', 0)
        ts_emoji = '🟢' if ts_score >= 80 else '🟡' if ts_score >= 60 else '🔴'
        message += f"{ts_emoji} *TokenSniffer Score:* `{ts_score}/100`\n"
    
    # Trading Score
    final_score = score_data.get('score', 0)
    verdict = score_data.get('verdict', 'UNKNOWN')
    score_emoji = '🟢' if final_score >= 75 else '🟡' if final_score >= 60 else '🔴'
    message += f"{score_emoji} *Trading Score:* `{final_score:.0f}/100` ({verdict})\n"
    
    # Overall Risk
    message += f"\n{risk_emoji.get(overall_risk, '⚪')} *Overall Risk:* *{overall_risk}*\n"
    
    # === MARKET DATA ===
    message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💧 *MARKET DATA*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    if chain == 'SOLANA':
        liquidity_sol = analysis.get('liquidity_sol', 0)
        message += f"💰 *Liquidity:* `{liquidity_sol:.2f} SOL`\n"
    else:
        liquidity_usd = analysis.get('liquidity_usd', 0)
        age_minutes = analysis.get('age_minutes', 0)
        message += f"💰 *Liquidity:* `${liquidity_usd:,.0f}`\n"
        message += f"⏰ *Age:* `{age_minutes/60:.1f} hours`\n"
    
    # === SECURITY CHECKS ===
    message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ *SECURITY CHECKS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    if chain != 'SOLANA':
        renounced = analysis.get('renounced', False)
        is_honeypot = analysis.get('is_honeypot', False)
        has_mint = analysis.get('has_mint_function', False)
        
        message += f"{'✅' if renounced else '❌'} Ownership Renounced\n"
        message += f"{'✅' if not is_honeypot else '⚠️'} Not a Honeypot\n"
        message += f"{'✅' if not has_mint else '⚠️'} No Mint Function\n"
    
    # === TOKENSNIFFER ANALYSIS ===
    if tokensniffer_result and chain != 'SOLANA':
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 *TOKENSNIFFER ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        # Swap Analysis
        swap = tokensniffer_result.get('swap_analysis', {})
        if not swap.get('is_honeypot', False):
            message += f"✅ Token is sellable\n"
        else:
            message += f"⚠️ Honeypot detected!\n"
        
        buy_fee = swap.get('buy_fee_percent', 0)
        sell_fee = swap.get('sell_fee_percent', 0)
        message += f"💸 Buy Fee: `{buy_fee:.1f}%` | Sell Fee: `{sell_fee:.1f}%`\n"
        
        # Contract Analysis
        contract = tokensniffer_result.get('contract_analysis', {})
        if contract.get('is_verified'):
            message += f"✅ Contract Verified\n"
        if contract.get('ownership_renounced'):
            message += f"✅ Ownership Renounced\n"
        
        # Holder Analysis
        holder = tokensniffer_result.get('holder_analysis', {})
        creator_pct = holder.get('creator_wallet_percent', 0)
        top10_pct = holder.get('top10_holders_percent', 0)
        
        if creator_pct < 5:
            message += f"✅ Creator holds `{creator_pct:.1f}%` (< 5%)\n"
        else:
            message += f"⚠️ Creator holds `{creator_pct:.1f}%` (≥ 5%)\n"
        
        if top10_pct < 70:
            message += f"✅ Top 10 holders: `{top10_pct:.1f}%` (< 70%)\n"
        else:
            message += f"⚠️ Top 10 holders: `{top10_pct:.1f}%` (≥ 70%)\n"
        
        # Liquidity Lock
        liq = tokensniffer_result.get('liquidity_analysis', {})
        liq_locked = liq.get('liquidity_locked_percent', 0)
        if liq_locked >= 95:
            message += f"✅ Liquidity Locked: `{liq_locked:.0f}%`\n"
        elif liq_locked > 0:
            message += f"⚠️ Liquidity Locked: `{liq_locked:.0f}%`\n"
        else:
            message += f"❌ Liquidity Not Locked\n"
    
    # === RISK FLAGS ===
    risk_flags = score_data.get('risk_flags', [])
    if risk_flags:
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *RISK FLAGS*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        for flag in risk_flags[:5]:  # Limit to 5 flags
            message += f"• {flag}\n"
    
    # === RECOMMENDATION ===
    message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *RECOMMENDATION*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{recommendation}

"""
    
    # === FOOTER ===
    message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ _Manual audit - Always DYOR before trading_
_Not financial advice_
"""
    
    return message


# Test
if __name__ == "__main__":
    # Sample audit report
    test_report = {
        'chain': 'base',
        'token_address': '0x4B6104755AfB5Da4581B81C552DA3A25608c73B8',
        'analysis': {
            'name': 'Ski Mask Kitten',
            'symbol': 'SKITTEN',
            'liquidity_usd': 100736,
            'age_minutes': 120,
            'renounced': True,
            'is_honeypot': False,
            'has_mint_function': False
        },
        'score_data': {
            'score': 65,
            'verdict': 'WATCH',
            'risk_flags': ['Snapshot only', 'Score capped at 65']
        },
        'security_score': 100,
        'tokensniffer_result': {
            'overall_score': 90,
            'swap_analysis': {
                'is_honeypot': False,
                'buy_fee_percent': 0,
                'sell_fee_percent': 0
            },
            'contract_analysis': {
                'is_verified': True,
                'ownership_renounced': True
            },
            'holder_analysis': {
                'creator_wallet_percent': 0,
                'top10_holders_percent': 14.22
            },
            'liquidity_analysis': {
                'liquidity_locked_percent': 99.99
            }
        },
        'overall_risk': 'LOW',
        'recommendation': '✅ LOW RISK - Suitable for trading with standard risk management'
    }
    
    message = create_improved_telegram_message(test_report)
    print(message)
