#!/bin/bash
# Reset processed signatures in scanner state

cd /home/hakim/bot-meme

echo "🔄 Restarting meme-bot service to reset scanner state..."
sudo systemctl restart meme-bot

echo "⏳ Waiting 2s for service to start..."
sleep 2

echo "📋 Checking service status..."
sudo systemctl status meme-bot --no-pager | head -20

echo "✅ Service restarted - scanner state reset"
