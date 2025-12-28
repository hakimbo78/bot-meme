# Production Deployment Checklist

## Pre-Deployment (Local)
- [x] **Code Audit**: Verify `main.py` imports/logic.
- [x] **Testing**: Run `test_phase5.py` and `test_market_intel.py`.
- [x] **Config Check**: Ensure `config.py` has correct RPC placeholders (not secrets).
- [ ] **Requirements**: Ensure `requirements.txt` is up to date.

## Deployment Steps (VPS)
1. **File Transfer**:
   - Upload `bot-meme/` folder to `/home/hakim/bot-meme`.
   - Ensure `deploy.sh` is executable (`chmod +x deploy.sh`).

2. **Run Setup**:
   ```bash
   ./deploy.sh
   # This installs Python 3.10, venv, dependencies, and systemd services.
   ```

3. **Environment Config**:
   - Create `.env` file if using one (not currently in config.py, but good practice).
   - Edit `config.py` on VPS if RPC keys differ.

4. **Start Services**:
   ```bash
   sudo systemctl start meme-bot
   ```

5. **Verify**:
   - **Dashboard**: Visit `http://<VPS_IP>:8501`.
   - **Logs**: `journalctl -u meme-bot -f`.
   - **Alerts**: Check Telegram for startup message (add one if missing).

## Post-Deployment Monitoring
- **Watchdog**: Verify `meme-bot` restarts on crash (simulated by `kill pid`).
- **Disk Usage**: Monitor `data/patterns.db` size.
- **Resource Usage**: Check CPU/RAM with `htop`.

## Rollback Plan
If failure occurs:
1. `sudo systemctl stop meme-bot meme-dashboard`
2. Revert code changes.
3. Use backup config.
