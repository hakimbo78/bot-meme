#!/bin/bash
# Deploy Secondary Scanner Fix to VPS
# Run from VPS: bash deploy_secondary_fix.sh

echo "🚀 Deploying Secondary Scanner Fix..."
echo "======================================"

# Navigate to project directory
cd /home/hakim/bot-meme || exit 1

# Pull latest changes
echo "📥 Pulling latest changes from GitHub..."
git pull origin main

# Check if pull was successful
if [ $? -eq 0 ]; then
    echo "✅ Successfully pulled latest changes"
else
    echo "❌ Failed to pull changes"
    exit 1
fi

# Restart bot service
echo "🔄 Restarting bot-meme service..."
sudo systemctl restart bot-meme

# Wait for service to start
sleep 3

# Check service status
echo "📊 Checking service status..."
sudo systemctl status bot-meme --no-pager | head -20

# Show recent logs
echo ""
echo "📋 Recent logs (SECONDARY scanner):"
echo "======================================"
sudo journalctl -u bot-meme -n 50 | grep SECONDARY

echo ""
echo "✅ Deployment complete!"
echo ""
echo "💡 To monitor live logs:"
echo "   sudo journalctl -u bot-meme -f | grep SECONDARY"
