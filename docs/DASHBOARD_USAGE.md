# Operator Dashboard - Usage Guide

A comprehensive read-only dashboard for monitoring the Multi-Chain Meme Coin Bot.

## 🚀 Quick Start

### Installation

1. **Install dependencies:**
   ```bash
   pip install streamlit plotly pandas bcrypt
   ```

2. **Create initial users:**
   ```bash
   python setup_users.py add -u admin -p yourpassword -r admin -n "Admin"
   ```

3. **Run the dashboard:**
   ```bash
   python run_dashboard.py
   ```

4. **Open in browser:**
   - http://localhost:8501

---

## 📱 Mobile Access

The dashboard is fully responsive and works on mobile devices:

1. **From your phone**, open your browser
2. Navigate to `http://YOUR_SERVER_IP:8501`
3. Login with your credentials
4. Use touch gestures to:
   - Tap cards to expand details
   - Scroll vertically through tokens
   - Use the sidebar (swipe from left) for filters

### Mobile Tips
- Enable "Desktop site" in browser settings for best experience
- Add to home screen for quick access
- Use Wi-Fi for faster chart loading

---

## 🔐 Authentication

### Default Credentials
After first run, default users are created:
- **admin** / admin123 (Administrator)
- **operator** / operator123 (Operator)

> ⚠️ **IMPORTANT**: Change these passwords immediately!

### Managing Users

**Add a new user:**
```bash
python setup_users.py add -u john -p secret123 -r operator -n "John Doe"
```

**Change password:**
```bash
python setup_users.py change-password -u admin -p newpassword
```

**List all users:**
```bash
python setup_users.py list
```

**Delete a user:**
```bash
python setup_users.py delete -u john
```

### User Roles
| Role | Description |
|------|-------------|
| `admin` | Full access, can manage users |
| `operator` | View all tokens and details |
| `viewer` | Read-only basic access |

---

## 🔒 HTTPS Setup

For secure access over the internet, enable HTTPS:

### Windows
```powershell
.\scripts\generate_ssl.ps1
python run_dashboard.py --https
```

### Linux/Mac
```bash
bash scripts/generate_ssl.sh
python run_dashboard.py --https
```

### Production SSL
For production, use Let's Encrypt:
```bash
certbot certonly --standalone -d yourdomain.com
```

Then update `.streamlit/config.toml`:
```toml
sslCertFile = "/etc/letsencrypt/live/yourdomain.com/fullchain.pem"
sslKeyFile = "/etc/letsencrypt/live/yourdomain.com/privkey.pem"
```

---

## 🎨 Dashboard Features

### Mode Colors

| Mode | Color | Icon | Description |
|------|-------|------|-------------|
| SNIPER | 🔴 Red | 🔥 | High-risk early tokens (< 3 min) |
| TRADE | 🟢 Green | 🟢 | Strong signals meeting all criteria |
| TRADE-EARLY | 🟡 Yellow | 🟡 | Pending momentum confirmation |
| RUNNING | 🔵 Blue | 🔵 | Post-launch rally detection |

### Filters

- **Chain**: Filter by blockchain (Base, Ethereum, Blast)
- **Mode**: Show only specific alert types
- **Min Score**: Hide tokens below threshold
- **Min Liquidity**: Filter by minimum USD liquidity

### Token Details

Each token card shows:
- Name, symbol, and contract address
- Score (0-100) with color indicator
- Liquidity in USD
- Market phase (Launch, Early Growth, Mature)
- Momentum confirmation status
- Holder concentration risk
- Alert timestamp

#### SNIPER Tokens
Additional details for SNIPER alerts:
- 📋 Operator Protocol (entry size, TP targets, exit strategy)
- ⚠️ Warning badges (high risk, high concentration)
- 🛑 Kill-switch status

---

## ⚙️ Configuration

### Auto-Refresh
Dashboard auto-refreshes every 30 seconds by default.
Toggle in sidebar: ☐ Auto-refresh (30s)

### Customization

Edit `dashboard_config.py` to customize:
```python
DASHBOARD_CONFIG = {
    "auto_refresh_seconds": 30,  # Change refresh interval
    "max_cards_per_page": 20,    # Cards per page
    "colors": {...},             # Custom color scheme
}
```

---

## 🖥️ Command Line Options

```bash
python run_dashboard.py [options]

Options:
  --https         Enable HTTPS (requires SSL certificates)
  --port 8501     Port number (default: 8501)
  --host 0.0.0.0  Host address (default: 0.0.0.0)
  --no-browser    Don't open browser automatically
  --debug         Enable debug logging
```

### Examples

```bash
# Basic HTTP
python run_dashboard.py

# HTTPS on custom port
python run_dashboard.py --https --port 443

# Production mode
python run_dashboard.py --https --port 443 --host 0.0.0.0 --no-browser
```

---

## 🛡️ Security Notes

> ⚠️ **READ-ONLY**: This dashboard is strictly informational.

- ❌ No private keys stored
- ❌ No wallet connections
- ❌ No transaction signing
- ❌ No trading execution
- ✅ Passwords are hashed (bcrypt)
- ✅ HTTPS available for encrypted transport
- ✅ Session-based authentication

---

## 🔧 Troubleshooting

### Dashboard won't start
```bash
# Check if dependencies are installed
pip install -r requirements.txt

# Check port availability
netstat -an | grep 8501
```

### Login not working
```bash
# Reset users file
rm dashboard_users.json
python run_dashboard.py  # Creates default users
```

### HTTPS certificate errors
```bash
# Regenerate certificates
rm -rf certs/
./scripts/generate_ssl.sh
```

### No tokens showing
- Ensure the bot is running and generating alerts
- Check cooldown files exist in `sniper/`, `running/` directories
- Try clicking "Refresh" button

---

## 📁 File Structure

```
bot-meme/
├── dashboard.py            # Main dashboard
├── dashboard_config.py     # Configuration
├── dashboard_state.py      # State management
├── dashboard_auth.py       # Authentication
├── dashboard_styles.css    # Custom CSS
├── dashboard_users.json    # User credentials
├── run_dashboard.py        # Launcher
├── setup_users.py          # User management CLI
├── .streamlit/
│   └── config.toml         # Streamlit config
├── scripts/
│   ├── generate_ssl.sh     # SSL generator (Linux)
│   └── generate_ssl.ps1    # SSL generator (Windows)
├── certs/                  # SSL certificates
│   ├── cert.pem
│   └── key.pem
└── docs/
    └── DASHBOARD_USAGE.md  # This file
```

---

## 📞 Support

For issues or feature requests, contact the development team.

Last updated: 2025-12-27
