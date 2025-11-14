# CogniPet: Hospital-Induced Delirium Detection & Prevention System

A comprehensive IoT system for monitoring cognitive function and detecting delirium risk in hospital patients using an ESP32-S3 device with cognitive assessment tests and a virtual pet interface.

## 🎯 Overview

CogniPet combines:
- **Hardware Device (ESP32-S3)**: Portable cognitive assessment device with LCD display and buttons
- **Cognitive Assessment Tests**: Orientation, memory, attention, and executive function tests
- **Virtual Pet Interface**: Engaging patient interaction to encourage regular cognitive engagement
- **BLE Data Transmission**: Automatic upload of assessment and interaction data via Bluetooth
- **Backend Server**: FastAPI server for data storage, analysis, and visualization
- **Web Dashboard**: Real-time monitoring and reporting interface

## 🏗️ System Architecture

```
ESP32-S3 (CogniPet Device)
    ↓ Bluetooth Low Energy (BLE)
BLE Bridge (Python)
    ↓ HTTP POST
Backend API (FastAPI)
    ↓ SQLite Database
Data Storage & Analysis
```

## 📁 Project Structure

```
sketch_nov2a/
├── cognipet_esp32/          # Arduino sketch for ESP32-S3
│   ├── cognipet_esp32.ino   # Main device firmware
│   └── README.md            # Hardware setup guide
├── backend/                 # Python backend server
│   ├── server.py            # FastAPI server
│   ├── database.py          # Database models and operations
│   ├── ble_bridge.py        # BLE to HTTP bridge
│   ├── pipeline.py          # Data processing pipeline
│   ├── test_ble_data.py     # Test script for data transmission
│   └── requirements.txt     # Python dependencies
├── restart_all.sh           # Restart all services
├── stop_all.sh              # Stop all services
├── status.sh                # Check system status
└── Documentation files
```

## 🚀 Quick Start

### 1. Hardware Setup

See `cognipet_esp32/README.md` for detailed hardware setup instructions.

**Required Hardware:**
- ESP32-S3 microcontroller
- Grove LCD RGB Backlight (16x2 character LCD)
- 3 buttons
- LED for feedback

### 2. Upload Firmware

1. Open `cognipet_esp32/cognipet_esp32.ino` in Arduino IDE
2. Install ESP32 board support (see `cognipet_esp32/README.md`)
3. Select board: **ESP32S3 Dev Module**
4. Upload to your ESP32-S3

### 3. Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

### 4. Start the System

```bash
# From project root
./restart_all.sh
```

This will:
- Start the backend server (http://localhost:8000)
- Start the BLE bridge
- Wait for ESP32 connection

### 5. Connect Your Device

1. Power on your ESP32-S3
2. Wait 5-10 seconds for boot
3. BLE bridge will automatically connect
4. Check status: `./status.sh`

## 🎮 Device Usage

### Button Combinations

- **Button 1 + Button 2** (hold 2 sec): Trigger cognitive assessment
- **Button 1 + Button 3** (hold 2 sec): Send test assessment data

### Pet Interactions

- **Button A (BTN1)**: Feed pet
- **Button B (BTN2)**: Play mini-game
- **Button C (BTN3)**: Clean pet
- **Button C (long press)**: Open menu

## 📊 Cognitive Assessment

The device performs four cognitive tests:

1. **Orientation Test** (3 questions)
   - Day of week
   - Time of day
   - Location awareness

2. **Memory Test** (Simon Says style)
   - Visual sequence memory
   - Button pattern repetition

3. **Attention Test** (Reaction time)
   - Press button when star appears
   - Measures response time

4. **Executive Function Test** (Sequencing)
   - Order daily activities correctly

**Scoring:**
- **10-12 points**: No impairment (Green alert)
- **7-9 points**: Mild concern (Yellow alert)
- **4-6 points**: Moderate impairment (Orange alert)
- **0-3 points**: Severe impairment (Red alert)

## 🔌 BLE Data Transmission

The ESP32 automatically sends data via Bluetooth Low Energy:

- **Device Name**: "CogniPet"
- **Service UUID**: `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **Assessment Characteristic**: `beb5483e-36e1-4688-b7f5-ea07361b26a8`
- **Interaction Characteristic**: `1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e`

The BLE bridge (`backend/ble_bridge.py`) automatically:
- Connects to the device
- Receives assessment and interaction data
- Forwards data to the backend API

## 🌐 Backend API

### Endpoints

- `GET /` - Web dashboard
- `GET /status` - System status
- `GET /api/assessments` - Get recent assessments
- `GET /api/interactions` - Get recent interactions
- `POST /api/cognitive-assessment` - Receive assessment data
- `POST /api/pet-interaction` - Receive interaction data

### View Data

```bash
# View assessments
curl http://localhost:8000/api/assessments | python3 -m json.tool

# View interactions
curl http://localhost:8000/api/interactions | python3 -m json.tool

# Web dashboard
open http://localhost:8000/
```

## 🧪 Testing

### Test BLE Data Transmission

```bash
cd backend
python3 test_ble_data.py --direct --count 5
```

This sends test assessment data directly to the backend (bypasses BLE).

### Test with Real Device

1. Make sure BLE bridge is running
2. On ESP32: Hold Button 1 + Button 3 for 2 seconds
3. Check backend: `curl http://localhost:8000/api/assessments`

## 📚 Documentation

- **Hardware Setup**: `cognipet_esp32/README.md`
- **BLE Bridge Guide**: `backend/BLE_BRIDGE_README.md`
- **Setup Guide**: `SETUP_GUIDE.md`
- **Restart Guide**: `RESTART_GUIDE.md`
- **Test Guide**: `backend/TEST_GUIDE.md`

## 🛠️ Management Scripts

### Restart Everything
```bash
./restart_all.sh
```

### Stop All Services
```bash
./stop_all.sh
```

### Check Status
```bash
./status.sh
```

## 🔧 Troubleshooting

### Device Not Found
- Ensure ESP32 is powered on
- Check Bluetooth is enabled on your computer
- Wait 10 seconds after powering on ESP32
- Check Serial Monitor: should show "BLE advertising started"

### Backend Won't Start
- Check if port 8000 is in use: `lsof -i:8000`
- Kill existing process: `lsof -ti:8000 | xargs kill -9`
- Check logs: `tail -f /tmp/cognipet_backend.log`

### Data Not Appearing
- Verify BLE bridge is connected: `tail -f /tmp/ble_bridge.log`
- Check backend is running: `curl http://localhost:8000/status`
- Try test script: `python3 backend/test_ble_data.py --direct`

## 📦 Dependencies

### Python Backend
- FastAPI
- Uvicorn
- SQLAlchemy
- Bleak (BLE library)
- Requests

See `backend/requirements.txt` for complete list.

### Arduino/ESP32
- ESP32 Board Support Package
- Built-in libraries: Wire, BLE, Preferences

## 🎯 Use Cases

- **Hospital Patient Monitoring**: Regular cognitive assessments for delirium detection
- **Long-term Care**: Track cognitive function over time
- **Research**: Collect cognitive assessment data
- **Rehabilitation**: Monitor cognitive recovery progress

## 📝 Data Privacy

All data is stored locally in SQLite database. No data is transmitted to external servers unless explicitly configured.

## 🤝 Contributing

This is a research/educational project. Contributions welcome!

## 📄 License

[Add your license here]

## 🔗 Links

- **Repository**: https://github.com/Mayalevich/NightWatch.git
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (when server is running)

## 📧 Contact

[Add contact information]

---

**Built for hospital-induced delirium detection and prevention** 🏥
