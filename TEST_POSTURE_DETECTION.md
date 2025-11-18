# Testing Posture Detection Feature

## Prerequisites

1. **Model File**: Ensure `best_model.pt` exists in project root or backend directory
2. **Dependencies**: OpenCV and Ultralytics should be installed
3. **Video Source**: Camera or IP webcam available

## Step 1: Check if Posture Detection Service is Running

### Check Server Logs
```bash
tail -f /tmp/cognipet_backend.log | grep -i posture
```

Look for:
- ✅ `✓ Posture detection model loaded` - Model loaded successfully
- ✅ `Posture detection service started` - Service is running
- ⚠️ `Posture detector not initialized` - Model file missing or dependencies unavailable
- ⚠️ `Posture detection will be disabled` - Service will continue without posture detection

### Check API Status
```bash
curl http://localhost:8000/api/posture/statistics
```

Expected response:
```json
{
  "total_detections": 0,
  "posture_distribution": {},
  "runtime_seconds": 0
}
```

If service is running, you'll see `runtime_seconds` increasing.

## Step 2: Verify Model File Location

```bash
# Check if model file exists
ls -lh best_model.pt backend/best_model.pt 2>/dev/null

# Check file size (should be several MB)
du -h best_model.pt 2>/dev/null || du -h backend/best_model.pt 2>/dev/null
```

The code looks for the model in:
1. Project root: `best_model.pt` (in the project root directory)
2. Backend directory: `backend/best_model.pt` (in the backend subdirectory)

## Step 3: Test Video Source

### Test Default Camera (Camera 0)
```bash
# Set environment variable (optional, 0 is default)
export POSTURE_VIDEO_SOURCE="0"

# Restart server
./restart_all.sh
```

### Test IP Webcam
```bash
# Set IP webcam URL
export POSTURE_VIDEO_SOURCE="http://192.168.1.100:8080/video"

# Restart server
./restart_all.sh
```

### Test Specific Camera Index
```bash
# Try different camera indices (0, 1, 2, etc.)
export POSTURE_VIDEO_SOURCE="1"
./restart_all.sh
```

## Step 4: Test API Endpoints

### Get Current Posture
```bash
curl http://localhost:8000/api/posture/current
```

**Expected responses:**

**No detection yet:**
```json
{
  "status": "no_detection",
  "message": "No posture detected yet"
}
```

**Posture detected:**
```json
{
  "posture": "Good-Style",
  "class_name": "goodstyle",
  "confidence": 0.85,
  "detected_at": "2024-01-15T10:30:45.123456"
}
```

### Get Posture Statistics
```bash
curl http://localhost:8000/api/posture/statistics | python3 -m json.tool
```

**Expected response:**
```json
{
  "total_detections": 150,
  "posture_distribution": {
    "Good-Style": {
      "count": 120,
      "percentage": 80.0,
      "raw_class": "goodstyle"
    },
    "Bad-Style": {
      "count": 30,
      "percentage": 20.0,
      "raw_class": "badstyle"
    }
  },
  "runtime_seconds": 300,
  "last_detection_at": "2024-01-15T10:35:00.123456"
}
```

### Get Posture History
```bash
curl http://localhost:8000/api/posture/history?limit=10 | python3 -m json.tool
```

### Get Latest Posture from Database
```bash
curl http://localhost:8000/api/posture/latest | python3 -m json.tool
```

## Step 5: Test Sleep Score Integration

### Check if Posture Affects Sleep Score
```bash
# Get latest sleep sample
curl http://localhost:8000/api/latest | python3 -m json.tool | grep -E "(SleepScore|Posture|PostureConfidence)"
```

**Expected output:**
```json
{
  "SleepScore": 85.0,
  "Posture": "Bad-Style",
  "PostureConfidence": 0.92
}
```

**Note**: Bad posture should reduce sleep score by 10-20 points.

### Monitor Real-time Updates
```bash
# Watch for posture data in sleep samples
watch -n 2 'curl -s http://localhost:8000/api/latest | python3 -m json.tool | grep -E "(SleepScore|Posture)"'
```

## Step 6: Test Frontend Display

1. **Open Dashboard**: `http://localhost:8000/`
2. **Navigate to Sleep Monitoring tab**
3. **Check Posture Card**:
   - Should show `—` if no detection
   - Should show `✓ Good` (green) for good posture
   - Should show `✗ Bad` (red) for bad posture
   - Badge should appear below with confidence percentage

4. **Check Browser Console** (F12):
   - Look for WebSocket messages containing `Posture` field
   - Check for any JavaScript errors

## Step 7: Manual Testing Script

Create a test script to continuously check posture:

```bash
#!/bin/bash
# test_posture.sh

echo "Testing Posture Detection..."
echo "================================"

# Check if service is running
echo "1. Checking service status..."
STATUS=$(curl -s http://localhost:8000/api/posture/statistics)
if echo "$STATUS" | grep -q "runtime_seconds"; then
    echo "   ✅ Service is running"
else
    echo "   ❌ Service not responding"
    exit 1
fi

# Check current posture
echo "2. Checking current posture..."
CURRENT=$(curl -s http://localhost:8000/api/posture/current)
if echo "$CURRENT" | grep -q "posture"; then
    echo "   ✅ Posture detected:"
    echo "$CURRENT" | python3 -m json.tool
else
    echo "   ⚠️  No posture detected yet (this is normal if no one is in front of camera)"
fi

# Check statistics
echo "3. Checking statistics..."
STATS=$(curl -s http://localhost:8000/api/posture/statistics)
echo "$STATS" | python3 -m json.tool

# Check sleep score integration
echo "4. Checking sleep score integration..."
LATEST=$(curl -s http://localhost:8000/api/latest)
if echo "$LATEST" | grep -q "Posture"; then
    echo "   ✅ Posture data in sleep samples"
    echo "$LATEST" | python3 -m json.tool | grep -E "(SleepScore|Posture)"
else
    echo "   ⚠️  No posture data in sleep samples yet"
fi

echo ""
echo "Test complete!"
```

Run it:
```bash
chmod +x test_posture.sh
./test_posture.sh
```

## Step 8: Verify Database Storage

```bash
cd backend
python3 << 'EOF'
import sqlite3
from datetime import datetime

conn = sqlite3.connect('sleep_data.db')
cursor = conn.cursor()

# Check posture detections table
print("Posture Detections:")
cursor.execute("SELECT COUNT(*) FROM posture_detections")
count = cursor.fetchone()[0]
print(f"  Total records: {count}")

if count > 0:
    cursor.execute("SELECT * FROM posture_detections ORDER BY recorded_at DESC LIMIT 5")
    rows = cursor.fetchall()
    print("\n  Recent detections:")
    for row in rows:
        print(f"    - {row[2]} ({row[3]:.2f} confidence) at {row[1]}")

# Check if posture is in sleep samples
print("\nSleep Samples with Posture:")
cursor.execute("SELECT COUNT(*) FROM processed_samples WHERE posture IS NOT NULL")
count = cursor.fetchone()[0]
print(f"  Samples with posture: {count}")

if count > 0:
    cursor.execute("SELECT sleep_score, posture, posture_confidence, recorded_at FROM processed_samples WHERE posture IS NOT NULL ORDER BY recorded_at DESC LIMIT 5")
    rows = cursor.fetchall()
    print("\n  Recent samples:")
    for row in rows:
        print(f"    - Score: {row[0]:.1f}, Posture: {row[1]} ({row[2]:.2f}), Time: {row[3]}")

conn.close()
EOF
```

## Troubleshooting

### Issue: "Posture detector not initialized"
**Solution**: 
- Check if `best_model.pt` exists
- Verify file is not corrupted
- Check server logs for model loading errors

### Issue: "Failed to open video source"
**Solution**:
- Check camera permissions
- Try different camera index (0, 1, 2)
- For IP webcam, verify URL is accessible
- Test camera with: `python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera works' if cap.isOpened() else 'Camera failed'); cap.release()"`

### Issue: No posture detected
**Solution**:
- Ensure someone/something is in front of camera
- Check lighting conditions
- Verify camera is positioned correctly
- Check confidence threshold (default 0.5, can be adjusted via `POSTURE_CONFidence` env var)

### Issue: Posture not affecting sleep score
**Solution**:
- Verify posture service is running
- Check that `posture_service` is passed to `SleepPipeline`
- Check server logs for errors
- Verify posture data is in sleep samples

### Issue: Frontend not showing posture
**Solution**:
- Check browser console for errors
- Verify WebSocket connection is active
- Check that API returns posture data
- Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)

## Quick Test Checklist

- [ ] Model file exists and is accessible
- [ ] Server logs show "Posture detection model loaded"
- [ ] `/api/posture/statistics` returns data
- [ ] Camera/video source is accessible
- [ ] `/api/posture/current` returns posture when person is in frame
- [ ] Frontend displays posture status
- [ ] Sleep score changes when bad posture is detected
- [ ] Database stores posture detections
- [ ] Posture data appears in sleep samples

## Expected Behavior

1. **Service starts automatically** when server starts (if model available)
2. **Detections occur every 1 second** (configurable via `POSTURE_INTERVAL`)
3. **Bad posture reduces sleep score** by 10-20 points
4. **Frontend updates in real-time** via WebSocket
5. **Data is stored** in both `posture_detections` and `processed_samples` tables

