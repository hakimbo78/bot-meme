#!/bin/bash

# Deployment Script for Meme Bot & Dashboard
# Target OS: Ubuntu 22.04 LTS (VPS)
# User: Hakim

set -e

echo "🚀 Starting Deployment Setup..."

# 1. System Updates
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv python3-pip git screen

# 2. Project Setup
PROJECT_DIR="/home/hakim/bot-meme"
echo "📂 Setting up project directory at $PROJECT_DIR..."

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Project directory not found! Please upload files first."
    exit 1
fi

cd $PROJECT_DIR

# 3. Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 4. Dependencies
echo "⬇️ Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install streamlit watchdog web3

# 5. Dashboard Service (Systemd)
echo "🖥️ Configuring Dashboard Service..."
cat <<EOF | sudo tee /etc/systemd/system/meme-dashboard.service
[Unit]
Description=Meme Bot Dashboard
After=network.target

[Service]
User=hakim
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 6. Bot Service (Systemd)
echo "🤖 Configuring Bot Service..."
cat <<EOF | sudo tee /etc/systemd/system/meme-bot.service
[Unit]
Description=Meme Trading Bot
After=network.target

[Service]
User=hakim
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python main.py --all-chains
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable & Start Services
echo "🔄 Reloading Systemd..."
sudo systemctl daemon-reload
sudo systemctl enable meme-dashboard
sudo systemctl enable meme-bot

echo "▶️ Starting Dashboard..."
sudo systemctl restart meme-dashboard

# Note: Bot service is enabled but not auto-started to allow manual config check first
# sudo systemctl start meme-bot

echo "---------------------------------------------------"
echo "✅ Deployment Setup Complete!"
echo "---------------------------------------------------"
echo "👉 Dashboard Configured on port 8501"
echo "👉 Bot Service created (meme-bot.service) but NOT started."
echo "   Run 'sudo systemctl start meme-bot' when ready."
echo "   Monitor with 'journalctl -u meme-bot -f'"
echo "---------------------------------------------------"
