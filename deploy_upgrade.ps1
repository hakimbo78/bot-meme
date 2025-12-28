# Deployment Script for Auto-Upgrade System to VPS
# Target: hakim@38.47.176.142:/home/hakim/bot-meme/

$VPS_HOST = "hakim@38.47.176.142"
$VPS_PATH = "/home/hakim/bot-meme"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Deploying Auto-Upgrade System to Production VPS" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Files and directories to deploy
$files = @(
    # New modules
    "solana/priority_detector.py",
    "solana/smart_wallet_detector.py",
    "solana/__init__.py",
    "sniper/auto_upgrade.py",
    "upgrade_integration.py",
    "telegram_alerts_ext.py",
    
    # Data
    "data/smart_wallets.json",
    
    # Updated files
    "config.py",
    "chains.yaml",
    "sniper/__init__.py",
    
    # Documentation
    "AUTO_UPGRADE_README.md",
    "DEPLOYMENT_CHECKLIST.md",
    "IMPLEMENTATION_SUMMARY.md",
    "QUICK_START.md",
    
    # Tests
    "test_auto_upgrade.py",
    "test_quick.py"
)

Write-Host "Files to deploy:" -ForegroundColor Yellow
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file (NOT FOUND)" -ForegroundColor Red
    }
}
Write-Host ""

# Confirm deployment
$confirm = Read-Host "Deploy these files to $VPS_HOST`:$VPS_PATH? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Deployment cancelled." -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "Starting deployment..." -ForegroundColor Cyan

# Deploy each file
$deployed = 0
$failed = 0

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "Deploying: $file" -ForegroundColor Gray
        
        # Get directory path
        $dir = Split-Path $file -Parent
        if ($dir) {
            # Create directory on VPS first
            ssh $VPS_HOST "mkdir -p $VPS_PATH/$dir" 2>$null
        }
        
        # Copy file
        scp $file "${VPS_HOST}:${VPS_PATH}/$file" 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            $deployed++
        } else {
            Write-Host "  Failed to deploy: $file" -ForegroundColor Red
            $failed++
        }
    }
}

Write-Host ""
Write-Host "Deployment Summary:" -ForegroundColor Cyan
Write-Host "  Deployed: $deployed files" -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Failed: $failed files" -ForegroundColor Red
}

Write-Host ""
Write-Host "Restarting bot service..." -ForegroundColor Cyan
ssh $VPS_HOST "sudo systemctl restart meme-bot"

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Checking service status..." -ForegroundColor Cyan
ssh $VPS_HOST "sudo systemctl status meme-bot --no-pager -l"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitor logs with:" -ForegroundColor Yellow
Write-Host "  ssh $VPS_HOST 'sudo journalctl -u meme-bot -f'" -ForegroundColor Gray
Write-Host ""
Write-Host "Check for auto-upgrade logs:" -ForegroundColor Yellow
Write-Host "  ssh $VPS_HOST 'sudo journalctl -u meme-bot -n 100 | grep -E \"[AUTO-UPGRADE]|[PRIORITY]|[SMART_WALLET]\"'" -ForegroundColor Gray
