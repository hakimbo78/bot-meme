"""
Unified Operator Dashboard for Multi-Chain Meme Coin Monitoring Bot

A comprehensive read-only Streamlit dashboard that integrates all monitoring modes:
- SNIPER: High-risk early token detection
- TRADE/TRADE-EARLY: Standard alert signals
- RUNNING: Post-launch rally detection

Features:
- Mobile-friendly responsive design
- User authentication with password protection
- Color-coded token cards by mode
- Expandable token details
- Auto-refresh every 30 seconds
- Filter by chain, mode, score, liquidity

IMPORTANT: This is a READ-ONLY dashboard. No trading execution.
"""
import streamlit as st
import time
from datetime import datetime
import json
from pathlib import Path

# Import dashboard modules
from dashboard_config import (
    get_dashboard_config, 
    get_color, 
    get_icon,
    DASHBOARD_CONFIG
)
from dashboard_state import get_dashboard_state, DashboardState
from dashboard_auth import (
    DashboardAuth,
    check_authentication,
    get_current_user,
    logout,
    login_page
)

# Page configuration
st.set_page_config(
    page_title="Operator Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_custom_css():
    """Load custom CSS for responsive design."""
    st.markdown("""
    <style>
    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    
    /* Header styles */
    .dashboard-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    .dashboard-title {
        color: #FF4B4B;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    
    .dashboard-subtitle {
        color: #888;
        font-size: 0.9rem;
        margin: 0;
    }
    
    /* Token card styles */
    .token-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #252540 100%);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .token-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    
    .token-card.sniper { border-left-color: #FF4B4B; }
    .token-card.trade { border-left-color: #28A745; }
    .token-card.trade_early { border-left-color: #FFC107; }
    .token-card.running { border-left-color: #007BFF; }
    
    .token-name {
        font-size: 1.1rem;
        font-weight: 600;
        color: #fff;
        margin: 0;
    }
    
    .token-symbol {
        color: #888;
        font-size: 0.85rem;
    }
    
    .token-address {
        font-family: monospace;
        font-size: 0.7rem;
        color: #666;
        cursor: pointer;
    }
    
    .token-address:hover {
        color: #FF4B4B;
    }
    
    .token-score {
        font-size: 1.5rem;
        font-weight: 700;
    }
    
    .token-metric {
        display: inline-block;
        background: rgba(255,255,255,0.05);
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        margin: 0.25rem;
        font-size: 0.8rem;
    }
    
    /* Mode badge */
    .mode-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .mode-badge.sniper { background: #FF4B4B; color: #fff; }
    .mode-badge.trade { background: #28A745; color: #fff; }
    .mode-badge.trade_early { background: #FFC107; color: #000; }
    .mode-badge.running { background: #007BFF; color: #fff; }
    
    /* Stats cards */
    .stat-card {
        background: linear-gradient(135deg, #252540 0%, #1e1e2e 100%);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #fff;
    }
    
    .stat-label {
        font-size: 0.8rem;
        color: #888;
        text-transform: uppercase;
    }
    
    /* Warning badge */
    .warning-badge {
        background: rgba(255,75,75,0.2);
        color: #FF4B4B;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        margin: 0.25rem;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .dashboard-title {
            font-size: 1.4rem;
        }
        
        .token-card {
            padding: 0.75rem;
        }
        
        .token-score {
            font-size: 1.2rem;
        }
        
        .stat-value {
            font-size: 1.5rem;
        }
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Progress bar for scores */
    .score-bar {
        height: 6px;
        border-radius: 3px;
        background: rgba(255,255,255,0.1);
        overflow: hidden;
        margin-top: 0.5rem;
    }
    
    .score-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s ease;
    }
    </style>
    """, unsafe_allow_html=True)


def render_header(state: DashboardState, user: dict):
    """Render dashboard header with stats."""
    stats = state.get_stats()
    
    # Header row
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        # Market Focus Indicator
        focus = state.get_market_focus()
        focus_chain = focus.get('chain')
        confidence = focus.get('confidence', 0) * 100
        
        focus_html = ""
        if focus_chain and confidence >= 65:
            focus_html = f"<span style='color:#FFC107; font-size:1.2rem; margin-left:1rem'>🔥 Focus: {focus_chain.upper()} ({confidence:.0f}%)</span>"
        
        st.markdown(f"""
        <div class="dashboard-header">
            <h1 class="dashboard-title">🎯 Operator Dashboard {focus_html}</h1>
            <p class="dashboard-subtitle">
                Multi-Chain Meme Coin Monitoring | 
                Last refresh: {stats['last_refresh_formatted']} |
                Logged in as: {user.get('name', 'Unknown')} ({user.get('role', 'viewer')})
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Quick stats & Intelligence
        stat_cols = st.columns(4)
        
        with stat_cols[0]:
            st.metric("Total", stats['total_tokens'], delta=None)
        
        with stat_cols[1]:
            st.metric("🔥 Sniper", stats['sniper_count'])
        
        with stat_cols[2]:
            st.metric("🔵 Running", stats['running_count'])
        
        with stat_cols[3]:
            # Conviction average (mock)
            st.metric("🧠 Conviction", "Avg 72")
    
    # Intelligence Panels
    intel_col1, intel_col2 = st.columns(2)
    
    with intel_col1:
        st.markdown("### 🔥 Narrative Radar")
        narratives = state.active_narratives
        if narratives:
            for n in narratives[:5]:
                name = n.get('name', 'UNKNOWN')
                stats = n.get('stats', {})
                trend_emoji = "↗️" if stats.get('trend') == 'RISING' else "➡️"
                conf = int(stats.get('confidence', 0) * 100)
                st.markdown(f"**{name}** {trend_emoji} `Conf: {conf}%`")
                st.progress(stats.get('confidence', 0))
        else:
            st.caption("No active narratives detected")
            
    with intel_col2:
        st.markdown("### 🧠 Smart Money Heatmap")
        sm_stats = state.smart_money_stats
        t1 = sm_stats.get('tier1_total', 0)
        t2 = sm_stats.get('tier2_total', 0)
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Tier 1 Wallets", t1, delta="High Conviction")
        with c2:
            st.metric("Tier 2 Wallets", t2, delta="Early Entry")
            
        st.caption("Tracking repeat winners and early survivors")
    
    st.markdown("---")
    
    with col3:
        # Refresh and logout buttons
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔄 Refresh", use_container_width=True):
                state.refresh()
                st.rerun()
        
        with col_btn2:
            if st.button("🚪 Logout", use_container_width=True):
                logout(st)
                st.rerun()


def render_sidebar_filters(state: DashboardState):
    """Render sidebar with filter options."""
    st.sidebar.markdown("## 🔍 Filters")
    
    # Chain filter
    available_chains = state.get_chains()
    if available_chains:
        chain_filter = st.sidebar.multiselect(
            "Chain",
            options=available_chains,
            default=available_chains,
            help="Filter by blockchain"
        )
    else:
        chain_filter = None
    
    st.sidebar.markdown("---")
    
    # Mode filter
    mode_options = ["All", "SNIPER", "TRADE", "TRADE-EARLY", "RUNNING"]
    mode_filter = st.sidebar.selectbox(
        "Mode",
        options=mode_options,
        index=0,
        help="Filter by alert mode"
    )
    
    if mode_filter == "All":
        mode_filter = None
    else:
        mode_filter = mode_filter.lower().replace("-", "_")
    
    st.sidebar.markdown("---")
    
    # Score filter
    min_score = st.sidebar.slider(
        "Minimum Score",
        min_value=0,
        max_value=100,
        value=0,
        help="Filter tokens below this score"
    )
    
    # Liquidity filter
    min_liquidity = st.sidebar.number_input(
        "Min Liquidity (USD)",
        min_value=0,
        value=0,
        step=1000,
        help="Filter tokens below this liquidity"
    )
    
    st.sidebar.markdown("---")
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox(
        "Auto-refresh (30s)",
        value=True,
        help="Automatically refresh data every 30 seconds"
    )
    
    if auto_refresh:
        st.sidebar.caption("⏱️ Auto-refresh enabled")
    
    return {
        "chain_filter": chain_filter,
        "mode_filter": mode_filter,
        "min_score": min_score,
        "min_liquidity": min_liquidity,
        "auto_refresh": auto_refresh
    }


def render_token_card(token: dict):
    """Render a single token card."""
    mode = token.get("mode", "unknown")
    icon = get_icon(mode)
    color = get_color(mode)
    
    # Score color based on value
    score = token.get("score", 0)
    if score >= 80:
        score_color = "#28A745"
    elif score >= 60:
        score_color = "#FFC107"
    else:
        score_color = "#DC3545"
    
    # Build warnings list
    warnings = []
    if token.get("high_risk"):
        warnings.append("⚠️ High Risk")
    if token.get("high_concentration"):
        warnings.append("⚠️ High Concentration")
            if token.get("killswitch_triggered"):
                warnings.append("🛑 Kill Switch")
            
            # Market Intel Warnings
            pattern = token.get("pattern_insight", {})
            if pattern.get("confidence_label") == "HIGH" and "DUMP" in pattern.get("matched_outcomes", {}):
                dump_prob = pattern["matched_outcomes"]["DUMP"]
                if dump_prob > 50:
                    warnings.append(f"❌ High Dump Risk ({dump_prob}%)")
                    
            if token.get("rotation_bonus", 0) > 0:
                warnings.append(f"🔄 Rotation Bonus +{token['rotation_bonus']}")

            warning_html = "".join([f'<span class="warning-badge">{w}</span>' for w in warnings])
            
            # Expand details
            with st.expander(f"{icon} **{token.get('name', 'Unknown')}** ({token.get('symbol', '???')}) - Score: {score}", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Solana source badge
                    source_badge = ""
                    source = token.get('source', '')
                    if source == 'pumpfun':
                        source_badge = "🧪 Pump.fun"
                    elif source == 'raydium':
                        source_badge = "💧 Raydium"
                    elif source == 'jupiter':
                        source_badge = "🪐 Jupiter"
                    
                    # DEX badge
                    dex_badge = ""
                    dex_type = token.get('dex_type', 'uniswap_v2')
                    if dex_type == 'uniswap_v3':
                        fee_tier = token.get('fee_tier', 3000)
                        fee_percent = fee_tier / 10000  # Convert basis points to percent
                        dex_badge = f" | **V3 ({fee_percent:.1f}%)**"
                    
                    source_html = f" | **Source:** {source_badge}" if source_badge else ""
                    
                    # Secondary market badge
                    secondary_badge = ""
                    if token.get('signal_type') == 'secondary_market':
                        secondary_badge = " | **Secondary**"
                        # Add trigger icons
                        triggers = token.get('triggers', {}).get('active_triggers', [])
                        if triggers:
                            trigger_icons = []
                            for trigger in triggers:
                                if trigger == 'volume_spike':
                                    trigger_icons.append('📈')
                                elif trigger == 'liquidity_growth':
                                    trigger_icons.append('💰')
                                elif trigger == 'price_breakout':
                                    trigger_icons.append('🚀')
                                elif trigger == 'holder_acceleration':
                                    trigger_icons.append('👥')
                            if trigger_icons:
                                secondary_badge += f" {' '.join(trigger_icons)}"
                    
                    st.markdown(f"""
                    **Address:** `{token.get('address', 'N/A')[:20]}...`  
                    **Chain:** {token.get('chain', 'Unknown').upper()}{source_html}{dex_badge}{secondary_badge}  
                    **Mode:** <span class="mode-badge {mode}">{mode.upper()}</span>  
                    **Age:** {token.get('age_display', 'N/A')}  
                    **Alert Time:** {token.get('alert_time', 'N/A')}
                    """, unsafe_allow_html=True)
                    
                    # Pattern Match Bar
                    if pattern and pattern.get("confidence_label") != "NO_MATCH":
                        sim = pattern.get("pattern_similarity", 0)
                        conf = pattern.get("confidence_label", "LOW")
                        st.markdown(f"**🧠 Pattern Match:** {sim}% ({conf})")
                        st.progress(sim / 100.0)
                        
                        # Outcomes
                        outcomes = pattern.get("matched_outcomes", {})
                        if outcomes:
                            out_str = " | ".join([f"{k}: {v}%" for k, v in outcomes.items()])
                            st.caption(f"Historic: {out_str}")
                    
                    st.markdown("---")
                    
                    # Metrics row
                    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                    
                    with metrics_col1:
                        st.metric("Score", f"{score}/100")
                    
                    with metrics_col2:
                        liq = token.get("liquidity_usd", 0)
                        st.metric("Liquidity", f"${liq:,.0f}")
                    
                    with metrics_col3:
                        st.metric("Phase", token.get("phase", "Unknown").title())
                
                with col2:
                    # Status indicators
                    st.markdown("**Status:**")
                    
                    momentum = token.get("momentum_confirmed", False)
                    st.markdown(f"{'✅' if momentum else '❌'} Momentum Confirmed")
                    
                    upgraded = token.get("upgraded", False)
                    st.markdown(f"{'✅' if upgraded else '⏳'} Upgraded")
                    
                    holder_risk = token.get("holder_risk", 0)
                    st.markdown(f"👥 Top10: {holder_risk:.1f}%")
                    
                    if warnings:
                        st.markdown("---")
                        st.markdown("**Insights:**")
                        for w in warnings:
                            st.markdown(w)
                
                # SNIPER specific: Operator Protocol
                if mode == "sniper" and token.get("operator_protocol"):
                    st.markdown("---")
                    st.markdown("### 📋 Operator Protocol")
                    protocol = token.get("operator_protocol", {})
                    
                    proto_cols = st.columns(3)
                    with proto_cols[0]:
                        st.markdown(f"**Entry Size:** {protocol.get('entry_size', 'N/A')}")
                    with proto_cols[1]:
                        st.markdown(f"**Take Profit:** {protocol.get('tp_targets', 'N/A')}")
                    with proto_cols[2]:
                        st.markdown(f"**Exit Strategy:** {protocol.get('exit_strategy', 'N/A')}")
        
        # Raw data expander
        with st.expander("🔧 Raw Data"):
            st.json(token.get("_raw", {}))


def render_token_list(state: DashboardState, filters: dict):
    """Render the main token list."""
    tokens = state.get_all_tokens(
        chain_filter=filters.get("chain_filter"),
        mode_filter=filters.get("mode_filter"),
        min_score=filters.get("min_score", 0),
        min_liquidity=filters.get("min_liquidity", 0)
    )
    
    if not tokens:
        st.info("📭 No tokens found matching your filters. Try adjusting the filters or waiting for new alerts.")
        return
    
    # Display count
    st.markdown(f"### 📊 Showing {len(tokens)} tokens")
    
    # Group by mode
    mode_tabs = st.tabs(["🔥 SNIPER", "🟢 TRADE", "🟡 TRADE-EARLY", "🔵 RUNNING", "📋 ALL"])
    
    modes = ["sniper", "trade", "trade_early", "running", None]
    
    for tab, mode in zip(mode_tabs, modes):
        with tab:
            if mode is None:
                filtered = tokens
            else:
                filtered = [t for t in tokens if t.get("mode") == mode]
            
            if not filtered:
                st.info(f"No tokens in this category")
                continue
            
            for token in filtered[:DASHBOARD_CONFIG.get("max_cards_per_page", 20)]:
                render_token_card(token)


def main():
    """Main dashboard entry point."""
    load_custom_css()
    
    # Check authentication
    if not check_authentication(st):
        login_page(st)
        return
    
    # Get current user
    user = get_current_user(st)
    if not user:
        logout(st)
        st.rerun()
        return
    
    # Initialize state
    state = get_dashboard_state()
    
    # Refresh data on first load
    if state.last_refresh is None:
        state.refresh()
    
    # Render header
    render_header(state, user)
    
    # Render sidebar filters
    filters = render_sidebar_filters(state)
    
    # Render main content
    render_token_list(state, filters)
    
    # Auto-refresh logic
    if filters.get("auto_refresh", True):
        refresh_interval = DASHBOARD_CONFIG.get("auto_refresh_seconds", 30)
        
        # Check if we need to refresh
        if state.last_refresh:
            elapsed = time.time() - state.last_refresh
            if elapsed >= refresh_interval:
                state.refresh()
                st.rerun()
        
        # Show countdown (approximate)
        remaining = max(0, refresh_interval - (time.time() - (state.last_refresh or time.time())))
        st.sidebar.caption(f"⏱️ Next refresh in ~{int(remaining)}s")
        
        # Use Streamlit's auto-rerun for refresh
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
