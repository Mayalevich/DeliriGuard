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

---

# ESP32 New Features Testing Guide

This section covers testing the new features implemented on the ESP32 device:
- Assessment Scheduling & Reminders
- Adaptive Difficulty System
- Local Data Persistence & Recovery
- Assessment History Viewer

## Prerequisites

- ESP32 device with latest firmware uploaded
- Serial Monitor open (115200 baud)
- BLE bridge running (optional, for full system test)

---

## Backdoor Shortcuts (Easier to Trigger!)

All backdoors have been made **much easier** to trigger:

### Improvements:
- ✅ **Reduced hold time**: 1.5 seconds (was 2 seconds)
- ✅ **More forgiving**: Allows brief button releases (up to 200ms)
- ✅ **Visual feedback**: Progress bar shows how long to hold
- ✅ **Faster feedback**: Shows message after 0.5 seconds

### Available Backdoors:

1. **Assessment Backdoor** (BTN1 + BTN2)
   - Hold both buttons for **1.5 seconds**
   - Shows "Assessment..." with progress bar
   - Triggers cognitive assessment immediately

2. **Diagnostics Backdoor** (BTN2 + BTN3)
   - Hold both buttons for **1.5 seconds**
   - Shows "Diagnostics..." with progress bar
   - Opens diagnostics mode

3. **Test Data Backdoor** (BTN1 + BTN3)
   - Hold both buttons for **1.5 seconds**
   - Shows "Test Data..." with progress bar
   - Sends test assessment data via BLE

**Tip**: If you briefly release a button (within 200ms), it won't cancel! This makes it much easier to hold both buttons.

---

## 1. Assessment Scheduling & Reminders

### Test Scheduling System

**Default Behavior:**
- Default interval: 6 hours
- Reminders check every 60 seconds
- Reminder shows when assessment is due

**Quick Test (1-hour interval):**
1. Open `cognipet_esp32.ino`
2. Find `initializeSchedule()` function
3. Temporarily change: `schedule.interval_hours = prefs.getUChar("sched_interval", 1);` (change 6 to 1)
4. Upload to ESP32
5. Complete an assessment
6. Wait 1 hour (or see "Force Reminder" method below)

**Force Reminder Immediately:**
1. After completing an assessment, add this to `loop()` temporarily:
   ```cpp
   schedule.lastAssessmentTime = millis() - 3600000UL; // Set to 1 hour ago
   ```
2. Reboot device
3. Wait ~1 minute for reminder check
4. Device should show reminder

**Test Reminder Display:**
- ✅ Orange blinking LED (every 500ms)
- ✅ LCD shows: "Time for Assessment!" or "Assessment! OVERDUE"
- ✅ RGB backlight: Orange glow

**Test Reminder Actions:**
- **Button 1**: Start assessment immediately
- **Button 2**: Skip (adds 1 hour to schedule)
- **Button 3**: Postpone (adds 30 minutes to schedule)

**Expected Serial Output:**
```
Schedule initialized: interval=6h, last=12345678
Assessment marked complete, schedule updated
```

---

## 2. Adaptive Difficulty System

### Test Difficulty Adjustment

**Test High Performance (Difficulty Increases):**
1. Run 3-5 assessments with high scores (9-12/12)
2. Watch Serial Monitor for:
   ```
   Adjusting difficulty: score=11, avg=10.2
   New difficulty: mem_len=4, mem_time=700, att_trials=6, exec_len=4
   ```
3. Next assessment should have:
   - Longer memory sequences (4-5 items)
   - Shorter display time (400-700ms)
   - More attention trials (6-7)
   - Longer executive sequences (4-5 items)

**Test Low Performance (Difficulty Decreases):**
1. Run 3-5 assessments with low scores (0-5/12)
2. Watch Serial Monitor for:
   ```
   Adjusting difficulty: score=3, avg=4.0
   New difficulty: mem_len=2, mem_time=1000, att_trials=3, exec_len=3
   ```
3. Next assessment should have:
   - Shorter memory sequences (2-3 items)
   - Longer display time (800-1200ms)
   - Fewer attention trials (3-4)
   - Shorter executive sequences (3 items)

**Verify Difficulty Changes:**
- Memory test: Check sequence length and display speed
- Attention test: Count number of trials and delay ranges
- Executive test: Check sequence length

**Expected Serial Output:**
```
Adaptive difficulty initialized
Adjusting difficulty: score=10, avg=8.5
New difficulty: mem_len=3, mem_time=800, att_trials=5, exec_len=4
```

---

## 3. Local Data Persistence & Recovery

### Test Assessment History Storage

**Test Storage:**
1. Run 2-3 assessments
2. Check Serial Monitor for:
   ```
   Stored assessment to history (index 2, count 3)
   ```
3. Reboot device
4. Check Serial Monitor for:
   ```
   Loaded 3 assessments from NVS
   ```

**Test BLE Queueing (When BLE is Down):**
1. **Stop BLE bridge** or turn off Bluetooth on computer
2. Run 2-3 assessments
3. Do some pet interactions (feed, play, clean)
4. Check Serial Monitor for:
   ```
   Queued interaction (count: 3)
   ✗ Cannot send: device not connected
   ```
5. **Start BLE bridge** or reconnect Bluetooth
6. Watch Serial Monitor for:
   ```
   BLE connected, retrying pending data...
   Retried and sent pending assessment (timestamp: 12345678)
   Retried and sent pending interaction (timestamp: 12345679)
   ```

**Test Serial Export:**
1. Open Serial Monitor (115200 baud)
2. Type: `EXPORT` and press Enter
3. You should see:
   ```
   === ASSESSMENT HISTORY EXPORT ===
   Format: timestamp,orientation,memory,attention,executive,total,avg_time_ms,alert_level,synced
   12345678,3,3,3,3,12,2000,0,1
   12345679,2,2,2,2,8,3000,1,1
   === END EXPORT ===
   Total assessments: 2
   Pending interactions: 0
   ```

**Test Auto-Retry:**
- When BLE reconnects, pending data should automatically retry
- Check Serial Monitor every 5 seconds for retry attempts
- All unsynced assessments (last 10) will be retried

---

## 4. Assessment History Viewer

### Access History Viewer

**Method:**
1. Enter pet mode (normal operation)
2. **Long press Button 3** (hold for 1+ second) → Opens menu
3. Navigate to **Stats menu** (Button 1 or 2)
4. **Hold Button 1 for 1 second** → History viewer opens

### Navigate History

**Controls:**
- **Button 1**: Scroll to **older** assessments (higher index)
- **Button 2**: Scroll to **newer** assessments (lower index), or toggle graph when at most recent
- **Button 3**: Exit history viewer

**Display Format:**
- **Line 1**: `#1 Score:12/12` (assessment number and total score)
- **Line 2**: `^ O:3 M:3 A:3` (trend arrow + breakdown) or `O:3 M:3 A:3 E:3` (full breakdown)

**Test Features:**

1. **View Details:**
   - Should show assessment number, score, and breakdown
   - Most recent is #1, older ones are #2, #3, etc.

2. **Test Trends:**
   - Run 2+ assessments with different scores
   - Check for trend arrows:
     - `^` = improving (score higher than previous)
     - `v` = declining (score lower than previous)
     - `=` = stable (same score)

3. **Test Graph View:**
   - At most recent assessment (#1), press **Button 2**
   - Should toggle to graph view showing last 8 scores
   - Characters: `|` (high), `=` (medium-high), `-` (medium-low), `.` (low)
   - Graph shows for 3 seconds, then returns to detail view

4. **Test Auto-Scroll:**
   - Wait 5 seconds without pressing buttons
   - Should automatically advance to next (older) assessment

**Expected Behavior:**
- Empty history: Shows "No history yet / Complete tests!"
- With history: Shows scrollable list with trends
- Graph view: Shows visual trend over time

---

## Quick Test Checklist

Use this checklist to verify all features:

### Scheduling & Reminders
- [ ] Complete assessment, wait for reminder (or force it)
- [ ] Verify reminder shows on LCD with blinking LED
- [ ] Test Button 1 (start assessment)
- [ ] Test Button 2 (skip 1 hour)
- [ ] Test Button 3 (postpone 30 min)
- [ ] Check Serial Monitor for schedule updates

### Adaptive Difficulty
- [ ] Run 3 assessments with high scores (9-12)
- [ ] Check Serial Monitor for difficulty increases
- [ ] Verify next assessment has harder tests
- [ ] Run 3 assessments with low scores (0-5)
- [ ] Check Serial Monitor for difficulty decreases
- [ ] Verify next assessment has easier tests

### Data Persistence
- [ ] Run 2-3 assessments
- [ ] Check Serial Monitor for "Stored assessment to history"
- [ ] Reboot device
- [ ] Check Serial Monitor for "Loaded X assessments from NVS"
- [ ] Disconnect BLE, run assessments
- [ ] Check Serial Monitor for "Queued interaction"
- [ ] Reconnect BLE
- [ ] Check Serial Monitor for "Retried and sent pending"
- [ ] Type `EXPORT` in Serial Monitor
- [ ] Verify CSV output appears

### History Viewer
- [ ] Access via menu (Stats → hold Button 1)
- [ ] Scroll through assessments (Button 1/2)
- [ ] Verify trend arrows appear (^/v/=)
- [ ] Toggle graph view (Button 2 at #1)
- [ ] Test auto-scroll (wait 5 seconds)
- [ ] Exit viewer (Button 3)

---

## Troubleshooting

### Reminders Not Showing
- Check if `schedule.remindersEnabled` is true
- Verify interval has passed (check `schedule.lastAssessmentTime`)
- Check Serial Monitor for schedule status

### Difficulty Not Adjusting
- Need at least 2-3 assessments for trend calculation
- Check Serial Monitor for "Adjusting difficulty" messages
- Verify scores are being recorded correctly

### History Not Persisting
- Check NVS storage (last 10 assessments saved)
- Verify `loadAssessmentHistory()` is called in `setup()`
- Check Serial Monitor for "Loaded X assessments" message

### BLE Retry Not Working
- Verify BLE is actually connected (`deviceConnected == true`)
- Check Serial Monitor for retry attempts
- Ensure pending data exists (check queue count)

### History Viewer Not Accessible
- Must be in pet mode (not assessment mode)
- Navigate: Menu → Stats → Hold Button 1
- Check if assessments exist (need at least 1)

---

## Serial Monitor Commands

| Command | Description |
|---------|-------------|
| `EXPORT` | Export all assessment history as CSV |

---

## Expected Serial Output Examples

**Scheduling:**
```
Schedule initialized: interval=6h, last=12345678
Assessment marked complete, schedule updated
```

**Adaptive Difficulty:**
```
Adaptive difficulty initialized
Adjusting difficulty: score=10, avg=8.5
New difficulty: mem_len=4, mem_time=700, att_trials=6, exec_len=4
```

**Data Persistence:**
```
Stored assessment to history (index 2, count 3)
Loaded 3 assessments from NVS
Queued interaction (count: 2)
BLE connected, retrying pending data...
Retried and sent pending assessment (timestamp: 12345678)
```

---

## Integration Testing

**Full System Test:**
1. Start backend server
2. Start BLE bridge
3. Run assessments on ESP32
4. Verify data appears in backend
5. Disconnect BLE, run more assessments
6. Reconnect BLE, verify auto-retry works
7. Check web dashboard for all data
8. Test history viewer on device
9. Export data via Serial Monitor

