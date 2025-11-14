# BLE Data Transmission Test Guide

This guide explains how to test the BLE data transmission from ESP32 to backend without manually triggering assessments.

## Quick Start

### Test Backend API Directly (Fastest)

This bypasses BLE and tests the backend directly:

```bash
cd backend
python3 test_ble_data.py --direct
```

This will:
- Send 1 test assessment with realistic scores
- Send 2 test interactions (feed, play)
- Verify data was stored in backend

### Send Multiple Test Assessments

```bash
python3 test_ble_data.py --direct --count 5
```

This sends 5 different test assessments with varying scores to test different scenarios.

### Verify Data in Backend

Check what data is currently stored:

```bash
python3 test_ble_data.py --verify
```

Or use curl:

```bash
# View assessments
curl http://localhost:8000/api/assessments | python3 -m json.tool

# View interactions
curl http://localhost:8000/api/interactions | python3 -m json.tool
```

## Test Scenarios

The test script includes 4 different assessment scenarios:

1. **Excellent Assessment** (Score 12/12)
   - All scores: 3/3
   - Alert Level: 0 (Green)
   - Response Time: 2000ms

2. **Moderate Assessment** (Score 8/12)
   - All scores: 2/3
   - Alert Level: 1 (Yellow)
   - Response Time: 3000ms

3. **Poor Assessment** (Score 4/12)
   - All scores: 1/3
   - Alert Level: 3 (Red)
   - Response Time: 5000ms

4. **Mixed Assessment** (Score 8/12)
   - Orientation: 3, Memory: 1, Attention: 2, Executive: 2
   - Alert Level: 1 (Yellow)
   - Response Time: 3500ms

## Usage Examples

### Basic Test
```bash
python3 test_ble_data.py --direct
```

### Test with Custom Backend URL
```bash
python3 test_ble_data.py --direct --backend-url http://192.168.1.100:8000
```

### Send 10 Assessments
```bash
python3 test_ble_data.py --direct --count 10
```

### Just Verify Existing Data
```bash
python3 test_ble_data.py --verify
```

## What Gets Tested

1. **Assessment Data**
   - Orientation score (0-3)
   - Memory score (0-3)
   - Attention score (0-3)
   - Executive function score (0-3)
   - Total score (0-12)
   - Average response time
   - Alert level (0-3)

2. **Interaction Data**
   - Interaction type (feed, play, clean, game)
   - Response time
   - Success/failure
   - Mood selection (optional)

## Expected Output

```
✓ Backend is running at http://localhost:8000

============================================================
Testing Backend API Directly
============================================================

--- Test 1/2 ---
Assessment: Score 12/12 (O:3 M:3 A:3 E:3) Alert: 0
✓ Data sent successfully: Assessment saved
  Interaction: feed, Success: True, Time: 450ms
✓ Data sent successfully: Interaction saved
  Interaction: play, Success: True, Time: 1200ms
✓ Data sent successfully: Interaction saved

============================================================
Results: 2/2 assessments sent successfully
============================================================

============================================================
Verifying Backend Data
============================================================

✓ Found 2 assessments in backend
  Latest: Score 8/12, Alert Level 1, Time: 2025-11-14T00:04:44.842664
✓ Found 5 interactions in backend
  Latest: play, Success: True, Time: 2025-11-14T00:04:45.659394
```

## Troubleshooting

### Backend Not Running
```
✗ Cannot connect to backend at http://localhost:8000
  Make sure the backend server is running:
  python -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000
```

**Solution:** Start the backend server first.

### Data Not Appearing
- Check backend logs for errors
- Verify database tables exist
- Try the `--verify` flag to check what's stored

### Import Errors
Make sure dependencies are installed:
```bash
pip install -r requirements.txt
```

## Integration with BLE Bridge

While this test script sends data directly to the backend API, it uses the same data format as the ESP32 device. This means:

1. **Backend Testing**: You can test the backend without needing the ESP32
2. **Data Format Validation**: The data format matches what the ESP32 sends
3. **Full System Testing**: Once backend works, test with real BLE bridge

To test the full BLE flow:
1. Start backend server
2. Start BLE bridge: `python3 ble_bridge.py`
3. Use actual ESP32 device to send data
4. Or use this test script to verify backend is working first

## Next Steps

After testing:
1. Verify data appears in the web dashboard: http://localhost:8000/
2. Check API endpoints return correct data
3. Test with actual ESP32 device via BLE bridge
4. Monitor backend logs for any errors

