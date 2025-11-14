# Quick Restart Guide

When you unplug your ESP32 and want to restart everything, follow these steps:

## Method 1: Use the Restart Script (Easiest)

```bash
cd /Users/jingyu/Documents/Arduino/sketch_nov2a
./restart_all.sh
```

This will:
- Stop all existing services
- Start the backend server
- Start the BLE bridge
- Show you the status

## Method 2: Manual Restart

### Step 1: Stop Everything
```bash
./stop_all.sh
```

Or manually:
```bash
pkill -f "uvicorn.*server:app"
pkill -f "ble_bridge"
```

### Step 2: Start Backend Server
```bash
cd backend
python3 -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```
*(Keep this terminal open, or run in background with `&`)*

### Step 3: Start BLE Bridge
In a new terminal:
```bash
cd backend
python3 ble_bridge.py
```
*(Keep this terminal open, or run in background with `&`)*

### Step 4: Power On ESP32
- Plug in your ESP32-S3
- Wait 5-10 seconds for it to boot
- The bridge will automatically connect

## Check Status

```bash
./status.sh
```

This shows:
- Backend server status
- BLE bridge status
- Database statistics

## Verify Everything Works

1. **Check backend:**
   ```bash
   curl http://localhost:8000/status
   ```

2. **Check bridge connection:**
   ```bash
   tail -f /tmp/ble_bridge.log
   ```
   You should see: `Found device: CogniPet` and `Connected to CogniPet`

3. **Test data transmission:**
   - On ESP32: Hold Button 1 + Button 3 for 2 seconds
   - Check: `curl http://localhost:8000/api/assessments | python3 -m json.tool`

## Troubleshooting

### Backend won't start
- Check if port 8000 is in use: `lsof -i:8000`
- Kill the process: `lsof -ti:8000 | xargs kill -9`

### Bridge can't find device
- Make sure ESP32 is powered on
- Check Bluetooth is enabled on your Mac
- Wait 10 seconds after powering on ESP32
- Check Serial Monitor - should show "BLE advertising started"

### Services keep stopping
- Run in background: Add `&` at end of command
- Or use `nohup`: `nohup python3 ble_bridge.py > /tmp/ble_bridge.log 2>&1 &`

## Quick Reference

| Command | What it does |
|---------|-------------|
| `./restart_all.sh` | Restart everything |
| `./stop_all.sh` | Stop everything |
| `./status.sh` | Check status |
| `tail -f /tmp/ble_bridge.log` | Watch bridge logs |
| `curl http://localhost:8000/api/assessments` | View assessments |

## Typical Workflow

1. Unplug ESP32
2. Run `./stop_all.sh` (optional, but clean)
3. Plug ESP32 back in
4. Run `./restart_all.sh`
5. Wait 10 seconds
6. Test: Press Button 1+3 on ESP32
7. Verify: `curl http://localhost:8000/api/assessments`

That's it! 🚀

