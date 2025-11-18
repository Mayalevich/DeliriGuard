# DeliriGuard: Hospital-Induced Delirium Detection & Prevention System

A comprehensive IoT healthcare monitoring system that combines **real-time sleep monitoring** and **cognitive assessment** to detect and prevent hospital-induced delirium in patients.

## 🎯 Overview

DeliriGuard is an integrated system with **two complementary components** that work together to detect delirium:

1. **Sleep Monitoring** (Arduino UNO R4): Tracks sleep patterns, movement, and environmental factors
2. **Cognitive Assessment** (ESP32-S3 CogniPet): Performs cognitive tests and tracks cognitive function over time (now supports real-world orientation prompts via Wi‑Fi/NTP)

**Together**, these components provide early warning signs of delirium by monitoring both:
- **Sleep disturbances** (disrupted sleep patterns are a key indicator)
- **Cognitive decline** (direct assessment of cognitive function)

## 🏥 How It Works

Hospital-induced delirium is often preceded by:
- **Sleep disruption** (frequent awakenings, restlessness)
- **Cognitive impairment** (confusion, disorientation, memory issues)

DeliriGuard monitors both indicators:
- **Sleep sensors** detect movement patterns and sleep quality
- **Cognitive device** performs regular assessments to track cognitive function
- **Combined data** provides comprehensive delirium risk assessment

---

## 📦 Project Structure

```
sketch_nov2a/
├── backend/                    # Python backend (shared by both components)
│   ├── server.py              # FastAPI server
│   ├── database.py            # Database models (sleep + cognitive data)
│   ├── pipeline.py            # Sleep data processing
│   ├── ble_bridge.py          # BLE bridge for CogniPet
│   └── requirements.txt
├── cognipet_esp32/            # CogniPet ESP32 firmware
│   ├── cognipet_esp32.ino     # Cognitive assessment device
│   └── README.md
├── sketch_nov2a.ino           # DeliriGuard Arduino UNO R4 sketch (sleep monitoring)
├── restart_all.sh             # Restart all services
├── stop_all.sh                # Stop all services
└── status.sh                  # Check system status
```

---

## 🌙 Component 1: Sleep Monitoring (Arduino UNO R4)

Monitors sleep patterns, movement, and environmental factors that may indicate delirium risk.

### Features

- **Real-time monitoring** via WebSocket streaming
- **Intelligent filtering** with adaptive thresholds and EMA smoothing
- **3-level activity classification** (Idle / Slight movement / Needs attention)
- **Environmental monitoring** (sound, light, temperature)
- **Posture Detection**: YOLO-based sleep posture monitoring (Good-Style/Bad-Style) with automatic camera startup
- **Posture Integration**: Bad posture reduces sleep score by 10-20 points
- **Camera Preview**: Live camera feed at `/camera` for debugging and monitoring
- **Dual interface**: Clinician-friendly overview + detailed technical dashboard
- **Data persistence** with SQLite database
- **Advanced analytics** with Plotly visualizations

### Hardware Requirements

- Arduino UNO R4 Minima
- 3× Piezo sensors (Head: A3, Body: A4, Leg: A5)
- Sound sensor (A0)
- Light sensor (A1)
- Temperature sensor (A2)
- Push button (D2 to GND)

### Installation

#### 1. Arduino Setup

Upload `sketch_nov2a.ino` to your Arduino UNO R4 Minima using the Arduino IDE.

#### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

**Note**: Posture detection requires OpenCV and Ultralytics. If these are not installed, the service will continue without posture detection (non-critical).

#### 3. Posture Detection Setup (Optional)

For posture detection, you need:
- **Model file**: `best_model.pt` (YOLO trained model) in project root or `backend/` directory
- **Camera**: Default camera (index 0) or IP webcam

**Configure camera source** (optional):
```bash
# Use default camera (0)
export POSTURE_VIDEO_SOURCE="0"

# Use IP webcam
export POSTURE_VIDEO_SOURCE="http://192.168.1.100:8080/video"

# Use specific camera index
export POSTURE_VIDEO_SOURCE="1"
```

**macOS Camera Permissions**:
1. System Settings → Privacy & Security → Camera
2. Enable camera access for Terminal/Python
3. Restart terminal after granting permissions

#### 4. Run the Server

```bash
# Set your Arduino's serial port
export SLEEP_SERIAL_PORT=/dev/cu.usbmodem101  # macOS
# or
export SLEEP_SERIAL_PORT=COM3  # Windows

# Start the server
python3 -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000/`

### Usage

- **Live Dashboard**: `http://localhost:8000/`
  - **Overview tab**: Clinician-friendly snapshot
  - **Sleep Monitoring tab**: Detailed metrics including posture status
  - **Detailed dashboard**: Charts, event log, CSV export, session reset

- **Camera Preview**: `http://localhost:8000/camera`
  - Live camera feed for posture detection debugging
  - Real-time status indicators (camera status, resolution, FPS, detections)
  - Visual verification that camera is working

- **Analytics Reports**: `http://localhost:8000/reports`
  - Plotly-based trends for movement, environment, and sleep scores
  - Auto-generated notes for quick interpretation

- **Patient Navigator (demo)**: `http://localhost:8000/patients`
  - Switch between example patients for trainings or demos while the physical device remains on one bed

### API Endpoints

- `GET /` - Live dashboard
- `GET /patients` - Patient navigator (demo)
- `GET /reports` - Analytics report
- `GET /camera` - Camera preview page (live feed for posture detection)
- `GET /api/camera/stream` - MJPEG camera stream
- `WebSocket /stream` - Real-time data stream
- `GET /api/status` - Backend status
- `GET /api/history?limit=300` - Recent samples
- `GET /api/latest` - Most recent sample
- `POST /api/reset` - Clear data and recalibrate

#### Posture Detection Endpoints

- `GET /api/posture/current` - Get current posture detection
- `GET /api/posture/history?limit=200` - Get posture detection history
- `GET /api/posture/latest` - Get latest posture from database
- `GET /api/posture/statistics` - Get detection statistics
- `GET /api/posture/status` - Get detailed camera and service status
- `POST /api/posture/start` - Start posture detection service
- `POST /api/posture/stop` - Stop posture detection service

### Posture Detection

The sleep monitoring system includes **YOLO-based posture detection** that automatically starts when the backend server starts:

- **Automatic Camera Startup**: Camera starts automatically on server startup
- **Real-time Detection**: Processes frames every 1 second (configurable)
- **Sleep Score Integration**: Bad posture reduces sleep score by 10-20 points
- **Visual Feedback**: Frontend displays posture status (✓ Good / ✗ Bad)
- **Camera Preview**: Debug camera feed at `http://localhost:8000/camera`

**Testing Posture Detection**:
```bash
# Quick test
./test_posture.sh

# Test camera access
python3 backend/test_camera.py

# Check status
curl http://localhost:8000/api/posture/status | python3 -m json.tool
```

See `TEST_POSTURE_DETECTION.md` and `CAMERA_SETUP.md` for detailed testing and setup instructions.

### Architecture

```
Arduino (Raw Sensors 10Hz)
    ↓ Serial @ 115200 baud
Python Backend (FastAPI + SQLAlchemy)
    ├─ Real-time filtering & event detection
    ├─ Posture detection (YOLO + camera)
    ├─ SQLite persistence
    └─ WebSocket broadcast
         ↓
Web Dashboard (Chart.js)
    ├─ Overview (clinician view)
    ├─ Sleep monitoring (with posture display)
    ├─ Camera preview page
    └─ CSV logging
```

---

## 🐾 Component 2: Cognitive Assessment (ESP32-S3 CogniPet)

Portable cognitive assessment device that performs regular cognitive tests to track cognitive function and detect delirium.

### Features

- **Cognitive Assessment Tests**: Orientation, memory, attention, executive function
- **Real-world Orientation Prompts**: When Wi‑Fi credentials are provided the device syncs its clock (Eastern/Waterloo timezone) so "What day/time is it?" questions use the actual current day and time-of-day; without Wi‑Fi it automatically falls back to the demo prompts
- **Assessment Scheduling & Reminders**: Configurable intervals (4/6/8 hours) with visual/LED reminders when assessments are due. Skip/postpone options available.
- **Adaptive Difficulty System**: Automatically adjusts test difficulty based on recent performance (easier patterns after low scores, harder when thriving)
- **Local Data Persistence & Recovery**: Stores last 50 assessments in memory, queues interactions when BLE is down, auto-retries on reconnect, and supports serial export for backup
- **Assessment History Viewer**: Scroll through last 10 assessments on LCD with score trends (improving/declining indicators) and a simple graph view using both LCD lines
- **On-device Diagnostics Mode**: Hidden bedside dashboard (Wi‑Fi/NTP status, BLE queue depth, button tester, pet vitals) activated via button combo for quick troubleshooting
- **Virtual Pet Interface**: Engaging patient interaction to encourage regular check-ins
- **BLE Data Transmission**: Automatic upload of assessment and interaction data with retry logic
- **Real-time Monitoring**: Track cognitive function over time
- **Alert System**: Color-coded risk levels (Green/Yellow/Orange/Red)

### Hardware Requirements

- ESP32-S3 microcontroller
- Grove LCD RGB Backlight (16x2 character LCD)
- 3 buttons (BTN1, BTN2, BTN3)
- LED for feedback

See `cognipet_esp32/README.md` for detailed hardware setup.

### Installation

#### 1. Upload Firmware

1. Open `cognipet_esp32/cognipet_esp32.ino` in Arduino IDE
2. Install ESP32 board support (see `cognipet_esp32/README.md`)
3. Select board: **ESP32S3 Dev Module**
4. Upload to your ESP32-S3

#### (Optional) Enable Wi‑Fi Time Sync

If you want the orientation questions to reference the real local date/time (Waterloo timezone), set the Wi‑Fi credentials near the top of `cognipet_esp32/cognipet_esp32.ino` before flashing:

```cpp
const char* WIFI_SSID = "YourHospitalWiFi";
const char* WIFI_PASSWORD = "super-secret";
```

On boot the device will briefly connect, synchronize against Canadian NTP servers, and then disconnect to save power. If the credentials remain as `YOUR_WIFI` / `YOUR_PASSWORD` (or Wi‑Fi is unavailable) the firmware automatically falls back to the original demo-oriented prompts.  
**Important:** the ESP32-S3 only supports **2.4 GHz** Wi‑Fi. Ensure your hotspot/router is broadcasting 2.4 GHz or mixed mode; pure 5 GHz SSIDs (e.g., “5G” hotspots) will always fail to connect.

#### 2. Start BLE Bridge

The backend server includes a BLE bridge that automatically connects to the device:

```bash
cd backend
python3 ble_bridge.py
```

Or use the restart script:
```bash
./restart_all.sh
```

### Usage

#### Button Combinations

- **Button 1 + Button 2** (hold 1.5 sec): Trigger cognitive assessment (easier to trigger, shows progress bar)
- **Button 1 + Button 3** (hold 1.5 sec): Send test assessment data (easier to trigger, shows progress bar)
- **Button 2 + Button 3** (hold 1.5 sec): Enter diagnostics mode (always accessible, even during games; View Wi‑Fi/BLE status, button tester, pet vitals; hold Button 3 for ~1.5 s to exit)

#### Pet Interactions

- **Button A (BTN1)**: Feed pet
- **Button B (BTN2)**: Play mini-game
- **Button C (BTN3)**: Clean pet
- **Button C (long press)**: Open menu

#### Assessment Reminders

When an assessment is due (default: every 6 hours):
- **Orange blinking LED** and LCD message appear
- **Button 1**: Start assessment immediately
- **Button 2**: Skip (adds 1 hour to schedule)
- **Button 3**: Postpone (adds 30 minutes to schedule)
- Reminders won't show again for 5 minutes after skip/postpone

#### Assessment History Viewer

Access from pet menu:
1. Long press **Button 3** → Opens menu
2. Navigate to **Stats menu** (Button 1/2)
3. Hold **Button 1** for 1 second → Opens history viewer

**Navigation:**
- **Button 1**: Scroll to older assessments
- **Button 2**: Scroll to newer assessments (or toggle graph at most recent)
- **Button 3**: Exit history viewer

**Features:**
- Shows assessment number, score, and breakdown
- Trend arrows: `^` (improving), `v` (declining), `=` (stable)
- Graph view: Visual trend using both LCD lines (up to 16 assessments)

#### Data Export

Export assessment history via Serial Monitor:
- Open Serial Monitor (115200 baud)
- Type: `EXPORT` and press Enter
- CSV format output with all assessment data

### Cognitive Assessment

The device performs four cognitive tests with **adaptive difficulty** that adjusts based on patient performance:

1. **Orientation Test** (3 questions)
   - Day of week, time of day, location awareness
   - Uses real-world time when Wi‑Fi/NTP is synced

2. **Memory Test** (Simon Says style)
   - Visual sequence memory, button pattern repetition
   - **Adaptive**: Sequence length (2-5 items) and display time (400-1200ms) adjust based on performance

3. **Attention Test** (Reaction time)
   - Press button when star appears, measures response time
   - **Adaptive**: Number of trials (3-7) and delay ranges adjust based on performance

4. **Executive Function Test** (Sequencing)
   - Order daily activities correctly
   - **Adaptive**: Sequence length (3-5 items) adjusts based on performance

**Scoring:**
- **10-12 points**: No impairment (Green alert)
- **7-9 points**: Mild concern (Yellow alert)
- **4-6 points**: Moderate impairment (Orange alert)
- **0-3 points**: Severe impairment (Red alert)

**Adaptive Difficulty:**
- Tracks last 5 assessment scores to calculate trends
- **High performance** (avg ≥ 9): Difficulty increases (longer sequences, shorter times, more trials)
- **Low performance** (avg ≤ 5): Difficulty decreases (shorter sequences, longer times, fewer trials)
- All tests still return normalized 0-3 scores regardless of difficulty level

### BLE Data Transmission

- **Device Name**: "CogniPet"
- **Service UUID**: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **Assessment Characteristic**: `beb5483e-36e1-4688-b7f5-ea07361b26a8`
- **Interaction Characteristic**: `1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e`

### API Endpoints (Cognitive Data)

- `GET /api/assessments` - Get recent cognitive assessments
- `GET /api/interactions` - Get recent pet interactions
- `POST /api/cognitive-assessment` - Receive assessment data
- `POST /api/pet-interaction` - Receive interaction data

### Architecture

```
ESP32-S3 (CogniPet Device)
    ↓ Bluetooth Low Energy (BLE)
BLE Bridge (Python)
    ↓ HTTP POST
Backend API (FastAPI)
    ↓ SQLite Database
Data Storage & Analysis
```

---

## 🚀 Quick Start (Complete System)

### Start Everything

```bash
./restart_all.sh
```

This starts:
- Backend server (http://localhost:8000)
- BLE bridge (for CogniPet)
- All services ready for both components

### Check Status

```bash
./status.sh
```

### Stop Everything

```bash
./stop_all.sh
```

---

## 📊 Data Viewing

### Sleep Monitoring Data

```bash
# View recent sleep samples
curl http://localhost:8000/api/history | python3 -m json.tool

# View latest sample
curl http://localhost:8000/api/latest | python3 -m json.tool

# Web dashboard
open http://localhost:8000/
```

### Cognitive Assessment Data

```bash
# View assessments
curl http://localhost:8000/api/assessments | python3 -m json.tool

# View interactions
curl http://localhost:8000/api/interactions | python3 -m json.tool
```

---

## 🧪 Testing

### Test Sleep Monitoring

Use the mock data generator:
```bash
cd backend
python3 mock_data_generator.py
```

### Test CogniPet Data Transmission

```bash
cd backend
python3 test_ble_data.py --direct --count 5
```

This sends test assessment data directly to the backend (bypasses BLE).

---

## 📚 Documentation

- **CogniPet Hardware Setup**: `cognipet_esp32/README.md`
- **BLE Bridge Guide**: `backend/BLE_BRIDGE_README.md`
- **Complete Setup Guide**: `SETUP_GUIDE.md`
- **Restart Guide**: `RESTART_GUIDE.md`
- **Test Guide**: `backend/TEST_GUIDE.md`
- **Posture Detection Testing**: `TEST_POSTURE_DETECTION.md`
- **Camera Setup**: `CAMERA_SETUP.md`

---

## 🔧 Configuration

### Sleep Monitoring Thresholds

Adjust filtering parameters in `backend/pipeline.py`:

```python
# Absolute minimum thresholds (normalized RMS units)
self.config = {
  "head": ChannelConfig(0.25, 1.20, 1.5),
  "body": ChannelConfig(1.00, 0.90, 6.0),
  "leg": ChannelConfig(1.00, 1.00, 5.5),
}

# Activity classification
value >= 1.0  → Needs attention
value >= 0.5  → Slight movement  
value < 0.5   → Idle
```

---

## 🛠️ Troubleshooting

### Sleep Monitoring Issues

- **No data received**: Check serial port connection
- **Data looks wrong**: Verify sensor connections
- **Dashboard not updating**: Check WebSocket connection

### Posture Detection Issues

- **Camera not accessible**: 
  - Grant camera permissions (System Settings → Privacy → Camera)
  - Ensure no other app is using the camera
  - Try different camera index: `export POSTURE_VIDEO_SOURCE="1"`
- **No posture detected**: 
  - Check camera preview at `http://localhost:8000/camera`
  - Verify model file exists: `ls -lh best_model.pt`
  - Check service status: `curl http://localhost:8000/api/posture/status`
- **Service not starting**: 
  - Check server logs: `tail -f /tmp/cognipet_backend.log`
  - Verify OpenCV is installed: `python3 -c "import cv2; print('OK')"`
  - Service will continue without posture detection if model is missing (non-critical)

### CogniPet Issues

- **Device not found**: Ensure ESP32 is powered on, Bluetooth enabled
- **Data not appearing**: Check BLE bridge is connected
- **Assessment not working**: Check Serial Monitor for errors

See individual component documentation for detailed troubleshooting.

---

## 📦 Dependencies

### Python Backend

See `backend/requirements.txt`:
- FastAPI
- Uvicorn
- SQLAlchemy
- Bleak (BLE library)
- Plotly
- Requests
- OpenCV (opencv-python) - For posture detection
- Ultralytics - For YOLO model inference
- NumPy - For image processing

### Arduino/ESP32

- ESP32 Board Support Package (for CogniPet)
- Standard Arduino libraries (for DeliriGuard)

---

## 🎯 Use Cases

- **Hospital Patient Monitoring**: Combined sleep and cognitive monitoring for delirium detection
- **Early Warning System**: Detect delirium risk before symptoms become severe
- **Long-term Care**: Track sleep patterns and cognitive function over time
- **Research**: Collect comprehensive patient data for delirium studies
- **Rehabilitation**: Monitor recovery progress and cognitive improvement

---

## 🔗 Links

- **Repository**: https://github.com/Mayalevich/NightWatch.git  <!-- repository URL unchanged; project branding is DeliriGuard -->
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (when server is running)

---

## 📄 License

MIT

---

## 🤝 Contributing

This is a research/educational project. Contributions welcome!

---

**Built for hospital-induced delirium detection and prevention** 🏥
