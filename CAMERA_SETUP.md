# Camera Setup for Posture Detection

## macOS Camera Permissions

On macOS, you need to grant camera permissions to Terminal/Python.

### Step 1: Grant Camera Permissions

1. **Open System Settings** (or System Preferences on older macOS)
2. Go to **Privacy & Security** → **Camera**
3. Enable camera access for:
   - **Terminal** (if running from terminal)
   - **Python** (if available in the list)
   - **VS Code** or your IDE (if running from there)

### Step 2: Test Camera Access

```bash
cd /Users/jingyu/Documents/Arduino/sketch_nov2a
python3 backend/test_camera.py
```

You should see:
```
✓ Camera 0 opened successfully
✓ Successfully read frame
```

### Step 3: Start Posture Monitoring

Once camera permissions are granted:

```bash
# Option 1: Use the helper script
./start_posture_monitoring.sh

# Option 2: Manual start
# Check status
curl http://localhost:8000/api/posture/status

# Start the service
curl -X POST http://localhost:8000/api/posture/start

# Check if camera is running
curl http://localhost:8000/api/posture/status | python3 -m json.tool
```

### Step 4: Verify Camera is Active

Check the status endpoint:
```bash
curl http://localhost:8000/api/posture/status | python3 -m json.tool
```

Look for:
- `"camera_opened": true` - Camera is active
- `"service_running": true` - Service is running
- `"camera_accessible": true` - Camera can be accessed

### Step 5: Monitor in Real-Time

**Option A: Watch API endpoint**
```bash
watch -n 2 'curl -s http://localhost:8000/api/posture/current | python3 -m json.tool'
```

**Option B: Check dashboard**
1. Open: `http://localhost:8000/`
2. Go to **Sleep Monitoring** tab
3. Look at the **Posture** card
4. Position yourself in front of camera
5. Wait 1-2 seconds for detection

**Option C: Check logs**
```bash
tail -f /tmp/cognipet_backend.log | grep -i posture
```

## Troubleshooting

### "Camera not accessible"
- **Grant permissions**: System Settings → Privacy & Security → Camera
- **Close other apps**: Make sure no other app is using the camera
- **Restart terminal**: After granting permissions, restart your terminal

### "Camera failed to properly initialize"
- **Check permissions**: macOS may need explicit permission
- **Try different camera index**: Some systems use camera 1 instead of 0
  ```bash
  export POSTURE_VIDEO_SOURCE="1"
  ./restart_all.sh
  ```

### "Service not running"
- **Check if model file exists**: `ls -lh best_model.pt`
- **Check server logs**: `tail -20 /tmp/cognipet_backend.log`
- **Manually start**: `curl -X POST http://localhost:8000/api/posture/start`

### "No detections"
- **Position yourself in front of camera**
- **Ensure good lighting**
- **Wait 1-2 seconds** for detection
- **Check confidence threshold** (default 0.5, can be adjusted)

## Quick Start Commands

```bash
# 1. Test camera
python3 backend/test_camera.py

# 2. Check posture status
curl http://localhost:8000/api/posture/status | python3 -m json.tool

# 3. Start monitoring
curl -X POST http://localhost:8000/api/posture/start

# 4. Get current posture
curl http://localhost:8000/api/posture/current | python3 -m json.tool

# 5. Watch real-time
watch -n 1 'curl -s http://localhost:8000/api/posture/current | python3 -m json.tool'
```

## Using IP Webcam (Alternative)

If you prefer to use a phone camera via IP webcam:

1. **Install IP Webcam app** on your phone
2. **Start the server** in the app
3. **Note the IP address** (e.g., `http://192.168.1.100:8080/video`)
4. **Set environment variable**:
   ```bash
   export POSTURE_VIDEO_SOURCE="http://192.168.1.100:8080/video"
   ```
5. **Restart server**:
   ```bash
   ./restart_all.sh
   ```

