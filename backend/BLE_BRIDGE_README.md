# BLE Bridge for CogniPet Device

This bridge connects your ESP32-S3 CogniPet device to the backend server via Bluetooth Low Energy (BLE).

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `bleak` (BLE library) and `requests` (HTTP client).

### 2. Start the Backend Server

Make sure your FastAPI backend is running:

```bash
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 3. Run the BLE Bridge

```bash
cd backend
python ble_bridge.py
```

The bridge will:
- Scan for the "CogniPet" BLE device
- Connect automatically when found
- Subscribe to assessment and interaction data
- Forward all data to the backend API

## Usage Options

### Default Settings
```bash
python ble_bridge.py
```
- Backend URL: `http://localhost:8000`
- Device name: `CogniPet`

### Custom Backend URL
```bash
python ble_bridge.py --backend-url http://192.168.1.100:8000
```

### Custom Device Name
```bash
python ble_bridge.py --device-name MyCogniPet
```

## How It Works

1. **Device Discovery**: The bridge scans for BLE devices matching the device name
2. **Connection**: Once found, it connects to the ESP32-S3
3. **Subscription**: Subscribes to two BLE characteristics:
   - **Assessment Characteristic**: Receives cognitive assessment results
   - **Interaction Characteristic**: Receives pet interaction logs
4. **Data Forwarding**: Parses binary data and sends it to backend API endpoints:
   - `/api/cognitive-assessment` - Assessment results
   - `/api/pet-interaction` - Interaction logs

## Data Flow

```
ESP32-S3 (CogniPet)
    ↓ BLE
BLE Bridge (ble_bridge.py)
    ↓ HTTP POST
Backend API (FastAPI)
    ↓ SQLite
Database (sleep_data.db)
```

## Viewing Data

Once data is received, you can view it via the API:

- **Recent Assessments**: `GET http://localhost:8000/api/assessments`
- **Recent Interactions**: `GET http://localhost:8000/api/interactions`

Or use the web dashboard at `http://localhost:8000/`

## Troubleshooting

### Device Not Found
- Make sure the ESP32-S3 is powered on and BLE is advertising
- Check that the device name matches (default: "CogniPet")
- Try running the bridge with `--device-name` to match your device exactly

### Connection Issues
- Ensure Bluetooth is enabled on your computer
- On macOS/Linux, you may need to grant Bluetooth permissions
- Try restarting the ESP32-S3 device

### Backend Connection Failed
- Verify the backend server is running: `curl http://localhost:8000/status`
- Check the backend URL is correct
- Ensure firewall allows connections to the backend port

### Data Not Appearing
- Check the bridge console output for error messages
- Verify the ESP32-S3 is sending data (check Serial Monitor)
- Check backend logs for API errors

## Platform Notes

### macOS
- Bluetooth permissions may be required (System Preferences > Security & Privacy)
- The bridge should work out of the box with `bleak`

### Linux
- May require `sudo` or Bluetooth permissions
- Install: `sudo apt-get install libbluetooth-dev` (Debian/Ubuntu)

### Windows
- Should work with `bleak` library
- Ensure Bluetooth is enabled in Windows settings

## Running in Background

You can run the bridge as a background service:

```bash
# Using nohup
nohup python ble_bridge.py > ble_bridge.log 2>&1 &

# Or using screen/tmux
screen -S ble_bridge
python ble_bridge.py
# Press Ctrl+A then D to detach
```

