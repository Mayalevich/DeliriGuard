# DeliriGuard: Complete Technical Walkthrough

This document provides a comprehensive technical explanation of how the entire DeliriGuard system works, from hardware sensors to the web dashboard.

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Component 1: Sleep Monitoring System](#component-1-sleep-monitoring-system)
3. [Component 2: Cognitive Assessment System](#component-2-cognitive-assessment-system)
4. [Data Flow & Processing](#data-flow--processing)
5. [Integration & Communication](#integration--communication)
6. [Frontend Dashboard](#frontend-dashboard)
7. [Database & Persistence](#database--persistence)

---

## System Architecture Overview

DeliriGuard is a **dual-component IoT healthcare monitoring system** that combines:

1. **Sleep Monitoring** (Arduino UNO R4 + Python Backend)
2. **Cognitive Assessment** (ESP32-S3 + BLE Bridge)

Both components feed data into a unified **FastAPI backend** that processes, stores, and serves data to a **web dashboard**.

```
┌─────────────────────────────────────────────────────────────────┐
│                         DeliriGuard System                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────┐      ┌──────────────────────┐        │
│  │  Component 1:        │      │  Component 2:        │        │
│  │  Sleep Monitoring    │      │  Cognitive Assessment│        │
│  │                      │      │                      │        │
│  │  Arduino UNO R4      │      │  ESP32-S3            │        │
│  │  (Piezo Sensors)     │      │  (CogniPet Device)   │        │
│  │         │            │      │         │            │        │
│  │         ↓            │      │         ↓            │        │
│  │  Serial (USB)        │      │  Bluetooth LE        │        │
│  │  115200 baud         │      │  (BLE Bridge)        │        │
│  └──────────┬───────────┘      └──────────┬───────────┘        │
│             │                              │                    │
│             └──────────┬───────────────────┘                    │
│                        ↓                                        │
│              ┌─────────────────────┐                            │
│              │  FastAPI Backend    │                            │
│              │  (Python)           │                            │
│              │                     │                            │
│              │  • Signal Processing│                            │
│              │  • Posture Detection│                            │
│              │  • Data Storage     │                            │
│              │  • WebSocket Server │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│         ┌───────────────┼───────────────┐                      │
│         ↓               ↓               ↓                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                   │
│  │ SQLite   │   │ WebSocket│   │ REST API │                   │
│  │ Database │   │ Stream   │   │ Endpoints│                   │
│  └──────────┘   └────┬─────┘   └────┬─────┘                   │
│                      │               │                          │
│                      └───────┬───────┘                          │
│                              ↓                                  │
│                    ┌──────────────────┐                         │
│                    │  Web Dashboard   │                         │
│                    │  (HTML/JS)       │                         │
│                    │  • Real-time UI  │                         │
│                    │  • Charts        │                         │
│                    │  • Analytics     │                         │
│                    └──────────────────┘                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component 1: Sleep Monitoring System

### Hardware Layer: Arduino UNO R4

**Firmware**: `sketch_nov2a.ino`

#### Sensor Configuration

The Arduino continuously reads 7 sensors at **10 Hz** (100ms intervals):

| Sensor | Pin | Type | Purpose |
|--------|-----|------|---------|
| Head Piezo | A3 | Analog | Head movement detection |
| Body Piezo | A4 | Analog | Body movement detection |
| Leg Piezo | A5 | Analog | Leg movement detection |
| Sound | A0 | Analog | Ambient noise level |
| Light | A1 | Analog | Room lighting conditions |
| Temperature | A2 | Analog | Room temperature |
| Button | D2 | Digital | User control (calibration reset) |

#### Data Acquisition Process

1. **Oversampling**: Each sensor reading uses oversampling to reduce noise:
   - Piezo sensors: **32 samples** averaged
   - Other sensors: **16 samples** averaged
   - 150μs delay between samples for ADC stabilization

2. **Serial Output**: Data is sent as CSV over USB Serial at **115200 baud**:
   ```cpp
   // Format: time_ms,head_raw,body_raw,leg_raw,sound_raw,light_raw,temp_raw,button_raw
   Serial.println("12345,512,498,501,245,678,523,1");
   ```

3. **Timing**: Uses `millis()` for precise 100ms intervals (10 Hz sampling rate)

#### Example Data Stream

```
time_ms,head_raw,body_raw,leg_raw,sound_raw,light_raw,temp_raw,button_raw
0,512,498,501,245,678,523,1
100,515,499,502,247,679,524,1
200,511,497,500,244,677,522,1
...
```

---

### Backend Processing: Python Pipeline

**File**: `backend/pipeline.py`

The backend receives raw sensor data and processes it through multiple stages:

#### Stage 1: Serial Communication

**Class**: `SerialReader`

- Opens serial port connection (configurable via `SLEEP_SERIAL_PORT` env var)
- Reads CSV lines at 115200 baud
- Handles connection errors gracefully
- Decodes UTF-8 with error tolerance

#### Stage 2: Raw Sample Parsing

**Class**: `RawSample` (dataclass)

Parses CSV line into structured data:
```python
RawSample(
    time_ms=12345,
    piezo={"head": 512, "body": 498, "leg": 501},
    sound=245,
    light=678,
    temp_raw=523,
    button=1
)
```

#### Stage 3: Calibration (Initial Setup)

**Process**: `_handle_calibration()`

When the system starts or is reset:

1. **Collects 30 samples** (~3 seconds) while patient is at rest
2. **Calculates baseline** for each piezo channel:
   ```python
   baseline = mean(calibration_samples)  # DC offset
   ```

3. **Estimates noise floor**:
   ```python
   for each sample:
       adjusted = max(0, raw - baseline)
       amplitude = adjusted * 6.0  # gain_vib
       acc2 += amplitude²
   idle_rms = sqrt(acc2 / count)
   ```

4. **Initializes adaptive thresholds**:
   ```python
   noise_ema = idle_rms * norm_gain
   vib_thresh = max(
       (noise_ema + 10.0) * region_mult,
       abs_move_thresh
   )
   ```

5. **Calibrates sound threshold**:
   ```python
   sound_thresh = sqrt(mean(sound_samples²)) + 10.0
   ```

#### Stage 4: Real-Time Signal Processing

**Process**: `process_sample()` → `_finalize_rms_window()`

For each incoming sample:

1. **Accumulation** (250ms windows):
   ```python
   adjusted = max(0, raw_adc - baseline)
   amplitude = adjusted * 6.0
   acc2 += amplitude²
   count += 1
   ```

2. **RMS Calculation** (every 250ms):
   ```python
   rms_raw = sqrt(acc2 / count)
   ```

3. **Spike Suppression**:
   ```python
   if rms_raw > 3.0 * prev_rms_raw:
       rms_raw = prev_rms_raw  # Suppress noise spikes
   ```

4. **Normalization**:
   ```python
   rms_norm = rms_raw * norm_gain
   # Head: 0.25, Body: 0.70, Leg: 1.00
   ```

5. **EMA Smoothing**:
   ```python
   rms_filtered = (0.25 * rms_norm) + (0.75 * rms_filtered)
   ```

6. **Adaptive Noise Tracking** (when idle):
   ```python
   if not moving:
       noise_ema = (0.95 * noise_ema) + (0.05 * rms_filtered)
   ```

7. **Dynamic Threshold Calculation**:
   ```python
   thresh = max(
       (noise_ema + 10.0) * region_mult,
       abs_move_thresh
   )
   ```

8. **Event Detection** (with hysteresis):
   ```python
   rising_edge = (not moving) and (rms_filtered > thresh + 2.0)
   falling_edge = moving and (rms_filtered < thresh - 2.0)
   
   if rising_edge:
       moving = True
       events_sec += 1
   elif falling_edge:
       moving = False
   ```

9. **Activity Classification**:
   ```python
   ratio = rms_filtered / max(noise_ema, 0.1)
   if ratio >= 2.5:
       activity_level = 2  # "Needs attention"
   elif ratio >= 1.5:
       activity_level = 1  # "Slight movement"
   else:
       activity_level = 0  # "Idle"
   ```

#### Stage 5: Processed Sample Generation

**Process**: `_build_processed_sample()` (every 1 second)

1. **Aggregates environmental data**:
   - Sound RMS (from accumulated squares)
   - Light average
   - Temperature (converted from ADC to °C)

2. **Calculates Sleep Score** (0-100):
   ```python
   score = 100.0
   
   # Factor 1: Movement events
   score -= total_events_min * 3.0
   
   # Factor 2: Movement intensity (weighted)
   weighted_rms = (head_rms * 2.0) + (body_rms * 1.5) + (leg_rms * 1.0)
   if weighted_rms > 2.0:
       score -= (weighted_rms - 2.0) * 5.0
   
   # Factor 3: Activity levels
   for channel in channels:
       if activity_level == 2:
           score -= 8.0
       elif activity_level == 1:
           score -= 3.0
   
   # Factor 4: Environmental noise
   if sound_rms > 150:
       score -= (sound_rms - 150) * 0.05
   
   # Factor 5: Posture (if available)
   if posture == "Bad-Style":
       score -= 10.0 + (confidence * 10.0)
   
   sleep_score = max(0.0, min(100.0, score))
   ```

3. **Creates ProcessedSample** object with all metrics

#### Stage 6: Posture Detection Integration

**Service**: `PostureDetectionService` (optional)

If posture detection is enabled:

1. **Camera Access**: Opens video source (default camera or IP webcam)
2. **YOLO Model**: Loads `best_model.pt` (YOLO v8 trained model)
3. **Frame Processing**: Every 1 second:
   - Captures frame from camera
   - Runs YOLO inference
   - Detects "Good-Style" or "Bad-Style" postures
   - Stores detection with confidence score
4. **Integration**: Current posture is queried during sleep score calculation

---

## Component 2: Cognitive Assessment System

### Hardware Layer: ESP32-S3

**Firmware**: `cognipet_esp32/cognipet_esp32.ino`

#### Device Features

- **LCD Display**: 16x2 character LCD with RGB backlight
- **3 Buttons**: User interaction and navigation
- **LED**: Visual feedback and reminders
- **Wi-Fi** (optional): For NTP time synchronization
- **Bluetooth LE**: Data transmission to backend

#### Cognitive Assessment Tests

The device performs 4 cognitive tests with **adaptive difficulty**:

1. **Orientation Test** (3 questions):
   - Day of week, time of day, location
   - Uses real-world time if Wi-Fi/NTP is synced
   - Score: 0-3 points

2. **Memory Test** (Simon Says):
   - Visual sequence memory
   - Button pattern repetition
   - **Adaptive**: Sequence length (2-5), display time (400-1200ms)
   - Score: 0-3 points

3. **Attention Test** (Reaction time):
   - Press button when star appears
   - Measures response time
   - **Adaptive**: Number of trials (3-7), delay ranges
   - Score: 0-3 points

4. **Executive Function Test** (Sequencing):
   - Order daily activities correctly
   - **Adaptive**: Sequence length (3-5 items)
   - Score: 0-3 points

**Total Score**: 0-12 points

#### Adaptive Difficulty Algorithm

```cpp
// Tracks last 5 assessment scores
float avg_score = mean(last_5_scores);

if (avg_score >= 9.0) {
    // High performance: Increase difficulty
    sequence_length = min(5, current_length + 1);
    display_time = max(400, current_time - 100);
} else if (avg_score <= 5.0) {
    // Low performance: Decrease difficulty
    sequence_length = max(2, current_length - 1);
    display_time = min(1200, current_time + 100);
}
```

#### Data Structures

**Assessment Result** (32 bytes):
```cpp
struct AssessmentResult {
    uint32_t timestamp;           // 4 bytes
    uint8_t orientation_score;    // 1 byte
    uint8_t memory_score;         // 1 byte
    uint8_t attention_score;      // 1 byte
    uint8_t executive_score;      // 1 byte
    uint8_t total_score;          // 1 byte
    uint16_t avg_response_time_ms; // 2 bytes
    uint8_t alert_level;          // 1 byte
    // padding to 32 bytes
};
```

**Interaction Log** (9 bytes):
```cpp
struct InteractionLog {
    uint32_t timestamp;        // 4 bytes
    uint8_t interaction_type;  // 1 byte (feed/play/clean/game)
    uint16_t response_time_ms; // 2 bytes
    uint8_t success;           // 1 byte
    int8_t mood_selected;      // 1 byte (signed, -1 = none)
};
```

#### BLE Advertisement

- **Device Name**: "CogniPet"
- **Service UUID**: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **Characteristics**:
  - Assessment: `beb5483e-36e1-4688-b7f5-ea07361b26a8`
  - Interaction: `1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e`

---

### BLE Bridge: Python Service

**File**: `backend/ble_bridge.py`

#### Connection Process

1. **Device Discovery**:
   ```python
   device = await BleakScanner.find_device_by_name("CogniPet")
   ```

2. **Connection**:
   ```python
   async with BleakClient(device) as client:
       # Subscribe to characteristics
   ```

3. **Notification Handlers**:
   ```python
   async def assessment_handler(sender, data):
       parsed = parse_assessment_data(data)  # Unpack 32-byte struct
       requests.post(ASSESSMENT_ENDPOINT, json=parsed)
   
   async def interaction_handler(sender, data):
       parsed = parse_interaction_data(data)  # Unpack 9-byte struct
       requests.post(INTERACTION_ENDPOINT, json=parsed)
   ```

#### Data Parsing

**Assessment Data** (32 bytes → dict):
```python
unpacked = struct.unpack("<IBBBBBHB", data[:12])
# I = uint32, B = uint8, H = uint16
return {
    "device_timestamp_ms": unpacked[0],
    "orientation_score": unpacked[1],
    "memory_score": unpacked[2],
    "attention_score": unpacked[3],
    "executive_score": unpacked[4],
    "total_score": unpacked[5],
    "avg_response_time_ms": unpacked[6],
    "alert_level": unpacked[7],
}
```

**Interaction Data** (9 bytes → dict):
```python
unpacked = struct.unpack("<IBHBb", data[:9])
# I = uint32, B = uint8, H = uint16, b = int8
return {
    "device_timestamp_ms": unpacked[0],
    "interaction_type": unpacked[1],
    "response_time_ms": unpacked[2],
    "success": bool(unpacked[3]),
    "mood_selected": unpacked[4] if unpacked[4] >= 0 else None,
}
```

#### HTTP Forwarding

Data is forwarded to FastAPI backend via HTTP POST:
- Assessment: `POST /api/cognitive-assessment`
- Interaction: `POST /api/pet-interaction`

---

## Data Flow & Processing

### Sleep Monitoring Data Flow

```
Arduino (10 Hz)
    ↓ Serial CSV
SerialReader.readline()
    ↓ RawSample
SleepPipeline.process_sample()
    ↓ Calibration (first 30 samples)
    ↓ Signal Processing (250ms windows)
    ↓ Event Detection (hysteresis)
    ↓ Activity Classification
    ↓ ProcessedSample (every 1 second)
    ↓
    ├─→ Database.save_processed_sample()
    └─→ BroadcastHub.publish()
            ↓
        WebSocket clients
            ↓
        Frontend Dashboard
```

### Cognitive Assessment Data Flow

```
ESP32-S3 (on assessment completion)
    ↓ BLE Notification (32 bytes)
BLE Bridge (notification handler)
    ↓ Parse struct → dict
    ↓ HTTP POST
FastAPI /api/cognitive-assessment
    ↓ database.save_cognitive_assessment()
    ↓ SQLite Database
    ↓
    Available via:
    - GET /api/assessments
    - WebSocket (if implemented)
    - Frontend Dashboard
```

### Posture Detection Data Flow

```
Camera (30 FPS)
    ↓ Frame capture
PostureDetectionService (every 1 second)
    ↓ YOLO inference
    ↓ Detection result
    ↓ Store in service state
    ↓
    ├─→ GET /api/posture/current
    ├─→ database.save_posture_detection()
    └─→ SleepPipeline (during score calculation)
            ↓
        Sleep score penalty (10-20 points)
```

---

## Integration & Communication

### FastAPI Backend Architecture

**File**: `backend/server.py`

#### Core Components

1. **BackendService**:
   - Manages `SleepPipeline`
   - Handles `SerialReader`
   - Coordinates data processing

2. **BroadcastHub**:
   - Manages WebSocket client connections
   - Publishes events to all connected clients
   - Thread-safe queue management

3. **PostureDetectionService**:
   - Optional service for camera-based posture detection
   - Runs asynchronously in background
   - Provides current posture state

#### WebSocket Streaming

**Endpoint**: `/stream`

```python
@app.websocket("/stream")
async def stream(websocket: WebSocket):
    queue = await service.hub.register()
    
    # Background task for posture updates
    async def send_posture_updates():
        while True:
            await asyncio.sleep(1.0)
            posture = posture_service.get_current_posture()
            await websocket.send_text(json.dumps({
                "type": "posture",
                "payload": posture
            }))
    
    posture_task = asyncio.create_task(send_posture_updates())
    
    try:
        while True:
            event = await queue.get()
            if event["type"] == "data":
                payload = event["payload"].to_dict()
                await websocket.send_text(json.dumps({
                    "type": "data",
                    "payload": payload
                }))
    finally:
        posture_task.cancel()
        await service.hub.unregister(queue)
```

**Message Types**:
- `{"type": "data", "payload": {...}}` - Sleep monitoring data (every 1 second)
- `{"type": "posture", "payload": {...}}` - Posture updates (every 1 second)
- `{"type": "status", "message": "calibrating"}` - System status

#### REST API Endpoints

**Sleep Monitoring**:
- `GET /api/status` - Backend status
- `GET /api/history?limit=300` - Recent samples
- `GET /api/latest` - Most recent sample
- `POST /api/reset` - Reset calibration

**Posture Detection**:
- `GET /api/posture/current` - Current posture
- `GET /api/posture/history?limit=200` - Posture history
- `GET /api/posture/status` - Service status
- `POST /api/posture/start` - Start service
- `POST /api/posture/stop` - Stop service

**Cognitive Assessment**:
- `GET /api/assessments?limit=100` - Recent assessments
- `GET /api/interactions?limit=200` - Recent interactions
- `POST /api/cognitive-assessment` - Receive assessment (BLE bridge)
- `POST /api/pet-interaction` - Receive interaction (BLE bridge)

**Camera Stream**:
- `GET /api/camera/stream` - MJPEG stream
- `GET /camera` - Camera preview page

---

## Frontend Dashboard

**Files**: `frontend/index.html`, `frontend/js/*.js`

### Architecture

- **Vanilla JavaScript** (no frameworks)
- **Chart.js** for data visualization
- **WebSocket** for real-time updates
- **Modular components** (OverviewPanel, SleepPanel, CognitivePanel)

### WebSocket Client

```javascript
const ws = new WebSocket('ws://localhost:8000/stream');

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'data') {
        // Update sleep monitoring charts
        updateSleepCharts(message.payload);
    } else if (message.type === 'posture') {
        // Update posture display
        updatePostureDisplay(message.payload);
    }
};
```

### Real-Time Updates

1. **Sleep Data** (every 1 second):
   - Updates RMS charts (head, body, leg)
   - Updates sleep score
   - Updates activity levels
   - Updates environmental sensors

2. **Posture Data** (every 1 second):
   - Updates posture status badge
   - Updates confidence percentage

3. **Cognitive Data** (on-demand):
   - Fetched via REST API
   - Updated when new assessments arrive

### Chart Rendering

**Chart.js Configuration**:
- **Line Charts**: RMS values over time
- **Bar Charts**: Event counts
- **Gauge Charts**: Sleep score
- **Real-time updates**: Data points added every second

---

## Database & Persistence

**File**: `backend/database.py`

### SQLite Database Schema

**Table**: `processed_samples`
- Stores sleep monitoring data (every 1 second)
- Fields: RMS values, events, sleep score, posture, etc.
- Indexed on `recorded_at` for time-based queries

**Table**: `cognitive_assessments`
- Stores cognitive assessment results
- Fields: Scores, timestamps, alert levels
- Indexed on `recorded_at`

**Table**: `pet_interactions`
- Stores pet interaction logs
- Fields: Interaction type, response time, success, mood
- Indexed on `recorded_at`

**Table**: `posture_detections`
- Stores posture detection results
- Fields: Posture type, confidence, timestamp
- Indexed on `recorded_at`

### Data Persistence Flow

```python
# Sleep data
processed_sample = pipeline._build_processed_sample()
database.save_processed_sample(processed_sample)
    ↓
SQLAlchemy ORM
    ↓
SQLite INSERT INTO processed_samples

# Cognitive data
database.save_cognitive_assessment(
    device_timestamp_ms=...,
    orientation_score=...,
    ...
)
    ↓
SQLite INSERT INTO cognitive_assessments

# Posture data
database.save_posture_detection(
    posture="Good-Style",
    confidence=0.85,
    ...
)
    ↓
SQLite INSERT INTO posture_detections
```

### Query Patterns

**Recent Data**:
```python
# Last N samples
samples = database.get_recent_samples(limit=300)

# Since timestamp
samples = database.get_samples_since(minutes=180)
```

**Aggregations**:
```python
# System statistics
stats = database.get_system_stats()
# Returns: total samples, latest timestamps, etc.
```

---

## System Startup Sequence

### 1. Backend Server Startup

```python
@app.on_event("startup")
async def startup_event():
    # 1. Initialize database
    database.init_db()
    
    # 2. Start backend service
    await service.start()
    # Opens serial port
    # Starts async task to read serial data
    
    # 3. Start posture detection (if available)
    await posture_service.start()
    # Opens camera
    # Loads YOLO model
    # Starts detection loop
```

### 2. BLE Bridge Startup

```bash
python backend/ble_bridge.py
```

1. Scans for "CogniPet" device
2. Connects via BLE
3. Subscribes to characteristics
4. Starts notification handlers
5. Forwards data to backend API

### 3. Frontend Connection

1. Browser loads `index.html`
2. JavaScript connects to WebSocket
3. Fetches initial data via REST API
4. Starts real-time updates via WebSocket

---

## Error Handling & Resilience

### Serial Communication

- **Connection Loss**: Automatic reconnection attempts
- **Parse Errors**: Logged and skipped, system continues
- **Timeout Handling**: Graceful degradation

### BLE Communication

- **Device Not Found**: Continuous scanning
- **Connection Loss**: Automatic reconnection
- **Data Corruption**: Validation and error logging

### Posture Detection

- **Camera Unavailable**: Service continues without posture
- **Model Missing**: Service continues without posture
- **Detection Failures**: Logged, doesn't crash system

### Database

- **Write Failures**: Logged, doesn't block processing
- **Connection Issues**: Automatic retry
- **Migration Errors**: Handled gracefully

---

## Performance Characteristics

### Latency

- **Sensor → Dashboard**: ~1-2 seconds
  - Serial read: ~100ms
  - Processing: ~10-50ms
  - WebSocket: ~10-100ms
  - Frontend render: ~16ms (60 FPS)

### Throughput

- **Sleep Data**: 1 sample/second (1 Hz output, 10 Hz input)
- **Posture Data**: 1 detection/second
- **Cognitive Data**: On-demand (when assessment completes)

### Resource Usage

- **CPU**: Low (~5-10% on modern hardware)
- **Memory**: ~100-200 MB (Python backend)
- **Storage**: ~1 MB per hour of data (SQLite)

---

## Configuration & Customization

### Environment Variables

```bash
# Serial port
export SLEEP_SERIAL_PORT=/dev/cu.usbmodem101

# Posture detection
export POSTURE_VIDEO_SOURCE="0"  # Camera index or IP webcam URL
export POSTURE_CONFIDENCE="0.5"  # Detection confidence threshold
export POSTURE_INTERVAL="1.0"    # Detection interval (seconds)

# Backend
export BACKEND_HOST="0.0.0.0"
export BACKEND_PORT="8000"
```

### Algorithm Parameters

Edit `backend/pipeline.py`:

```python
# Calibration
self.calibration_sample_target = 30

# Filtering
self.filter_alpha = 0.25  # EMA smoothing
self.noise_alpha = 0.05   # Noise adaptation

# Thresholds
self.vib_margin_add = 10.0
self.hyst_add = 2.0
self.spike_factor = 3.0

# Channel-specific
self.config = {
    "head": ChannelConfig(0.25, 1.00, 2.0),
    "body": ChannelConfig(0.70, 1.00, 8.0),
    "leg": ChannelConfig(1.00, 1.00, 6.0),
}
```

---

## Summary

DeliriGuard is a **sophisticated multi-component IoT system** that:

1. **Acquires** sensor data from Arduino (sleep) and ESP32 (cognitive)
2. **Processes** raw signals through advanced algorithms (calibration, normalization, filtering)
3. **Detects** events and classifies activity levels
4. **Integrates** multiple data sources (sensors, posture, cognitive)
5. **Stores** all data in SQLite database
6. **Streams** real-time updates via WebSocket
7. **Visualizes** data in web dashboard

The system is designed for **reliability**, **scalability**, and **clinical accuracy**, with comprehensive error handling and graceful degradation.

---

**For more details on specific components, see:**
- Signal Processing: `README.md` (Signal Processing & Algorithms section)
- Setup: `docs/SETUP_GUIDE.md`
- Testing: `docs/TEST_POSTURE_DETECTION.md`
- Camera: `docs/CAMERA_SETUP.md`

