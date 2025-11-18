# Testing Posture Detection Integration

## Issue Fixed

The error you saw was because you were running the server from inside the `backend` directory. The command needs to be run from the **project root** directory.

## How to Run the Server

### 1. Navigate to Project Root
```bash
cd /Users/jingyu/Documents/Arduino/sketch_nov2a
```

### 2. Start the Server
```bash
python3 -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000
```

**Important**: Run this from the project root, NOT from inside the `backend` directory.

## Testing Posture Detection

### 1. Check if Model File Exists
```bash
ls -lh best_model.pt
# or
ls -lh backend/best_model.pt
```

The model file should be in either:
- Project root: `/Users/jingyu/Documents/Arduino/sketch_nov2a/best_model.pt`
- Backend directory: `/Users/jingyu/Documents/Arduino/sketch_nov2a/backend/best_model.pt`

### 2. Configure Video Source (Optional)

By default, it uses camera `0` (default webcam). To use an IP webcam:

```bash
export POSTURE_VIDEO_SOURCE="http://192.168.1.100:8080/video"
```

Or set it in your environment before starting the server.

### 3. Check Server Status

Once the server starts, check the logs:
- ✅ `✓ Posture detection model loaded` - Model loaded successfully
- ⚠️ `Posture detector not initialized` - Model file not found (service will continue without posture detection)
- ⚠️ `Posture detection service not available` - Service failed to start (non-critical)

### 4. Test API Endpoints

#### Get Current Posture
```bash
curl http://localhost:8000/api/posture/current
```

#### Get Posture Statistics
```bash
curl http://localhost:8000/api/posture/statistics
```

#### Get Posture History
```bash
curl http://localhost:8000/api/posture/history?limit=10
```

### 5. Test in Browser

1. Open the dashboard: `http://localhost:8000/`
2. Navigate to the **Sleep Monitoring** tab
3. Look for the **Posture** card next to the Sleep Score
4. You should see:
   - `✓ Good` (green) for good posture
   - `✗ Bad` (red) for bad posture
   - `—` (gray) if no detection yet

### 6. Verify Sleep Score Integration

1. Check that sleep score is being calculated with posture data
2. Bad posture should reduce the sleep score by 10-20 points
3. Check the WebSocket stream or API for posture data in sleep samples:

```bash
curl http://localhost:8000/api/latest | jq '.Posture, .PostureConfidence, .SleepScore'
```

## Troubleshooting

### Model Not Loading
- **Error**: `Failed to load posture detection model`
- **Solution**: 
  - Ensure `best_model.pt` exists in project root or backend directory
  - Check file permissions
  - The service will continue without posture detection if model is missing

### No Video Source
- **Error**: `Failed to open video source`
- **Solution**:
  - Check camera permissions
  - Verify camera index (try 0, 1, 2, etc.)
  - For IP webcam, verify URL is accessible

### Posture Not Showing in Frontend
- **Check**: Browser console for errors
- **Verify**: WebSocket connection is active
- **Test**: API endpoint directly to see if data is being generated

### Sleep Score Not Affected by Posture
- **Check**: Server logs for posture detection activity
- **Verify**: Posture service is running (`/api/posture/statistics`)
- **Note**: Posture only affects score when "Bad-Style" is detected

## Expected Behavior

1. **Posture Detection Service** starts automatically on server startup (if model available)
2. **Sleep Pipeline** queries posture service when calculating sleep scores
3. **Bad Posture** reduces sleep score by 10-20 points (based on confidence)
4. **Frontend** displays posture status in real-time
5. **Database** stores posture data with each sleep sample

## Manual Testing Steps

1. Start server from project root
2. Wait for posture detection to initialize
3. Position yourself in front of camera
4. Check dashboard for posture updates
5. Verify sleep score changes when bad posture is detected
6. Check database for stored posture data

