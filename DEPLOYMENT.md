# Deployment Guide - Meme Token Monitor Bot

## Server Details
- **IP**: 103.13.207.166
- **User**: hakim
- **Directory**: /home/hakim/bot-meme

---

## Step-by-Step Setup

### 1. SSH ke Server
```bash
ssh hakim@103.13.207.166
cd /home/hakim/bot-meme
```

### 2. Install Python Dependencies

**Option A: Gunakan venv baru (Recommended untuk Linux)**
```bash
# Hapus venv Windows
rm -rf .venv

# Buat venv baru
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

**Option B: Install global**
```bash
pip3 install -r requirements.txt
```

### 3. Setup Environment Variables
```bash
# Copy template
cp .env.example .env

# Edit dengan credentials Anda
nano .env
```

Isi file `.env`:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 4. Verify Installation
```bash
source .venv/bin/activate
python main.py --help
```

---

## Running the Bot

### Mode Normal (Operator Mode)
```bash
source .venv/bin/activate

# Single chain
python main.py --chains base

# All enabled chains
python main.py --all-chains
```

### Mode Sniper (HIGH RISK)
```bash
python main.py --all-chains --sniper-mode
```

---

## Run as Background Service (Recommended)

### Using Screen
```bash
# Install screen jika belum ada
sudo yum install screen -y  # CentOS/RHEL
# atau
sudo apt install screen -y  # Ubuntu/Debian

# Jalankan dalam screen
screen -S memebot
source .venv/bin/activate
python main.py --all-chains

# Detach: Ctrl+A, lalu D
# Reattach: screen -r memebot
```

### Using Systemd Service

1. Buat service file:
```bash
sudo nano /etc/systemd/system/memebot.service
```

2. Isi dengan:
```ini
[Unit]
Description=Meme Token Monitor Bot
After=network.target

[Service]
Type=simple
User=hakim
WorkingDirectory=/home/hakim/bot-meme
ExecStart=/home/hakim/bot-meme/.venv/bin/python main.py --all-chains
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable dan start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable memebot
sudo systemctl start memebot

# Check status
sudo systemctl status memebot

# View logs
sudo journalctl -u memebot -f
```

---

## Monitoring

### Check Bot Status
```bash
sudo systemctl status memebot
```

### View Live Logs
```bash
sudo journalctl -u memebot -f
```

### Restart Bot
```bash
sudo systemctl restart memebot
```

---

## Quick Commands Summary

| Command | Description |
|---------|-------------|
| `python main.py --help` | Show help |
| `python main.py --all-chains` | Run all chains |
| `python main.py --sniper-mode` | Enable sniper mode |
| `screen -r memebot` | Attach to screen |
| `sudo systemctl status memebot` | Check service status |
