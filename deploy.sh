#!/bin/bash
# Auto-deployment script with cache clearing
# Usage: ./deploy.sh

set -e

echo "🔄 Starting deployment..."

# Stop service
echo "⏸️  Stopping bot..."
sudo systemctl stop meme-bot

# Pull latest code
echo "📥 Pulling latest code..."
cd /home/hakim/bot-meme
git pull origin main

# Clear Python cache (CRITICAL for code updates)
echo "🧹 Clearing Python cache..."
find /home/hakim/bot-meme -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /home/hakim/bot-meme -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache cleared"

# Restart service
echo "🚀 Starting bot..."
sudo systemctl start meme-bot

# Wait and show status
sleep 2
echo ""
echo "📊 Bot status:"
sudo systemctl status meme-bot --no-pager -l

echo ""
echo "✅ Deployment complete!"
echo "📝 Monitor logs with: journalctl -u meme-bot -f"
