#!/usr/bin/env python3
"""
BLE Bridge for CogniPet Device
Connects to ESP32-S3 via Bluetooth Low Energy and forwards data to the backend API.

Usage:
    python ble_bridge.py [--backend-url http://localhost:8000] [--device-name CogniPet]

Requirements:
    - bleak library: pip install bleak requests
    - Backend server running (default: http://localhost:8000)
"""

import argparse
import asyncio
import struct
import sys
from typing import Optional

import requests
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

# BLE Configuration (must match ESP32 code)
BLE_DEVICE_NAME = "CogniPet"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
ASSESSMENT_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
INTERACTION_CHAR_UUID = "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e"

# Backend API endpoints
BACKEND_URL = "http://localhost:8000"
ASSESSMENT_ENDPOINT = f"{BACKEND_URL}/api/cognitive-assessment"
INTERACTION_ENDPOINT = f"{BACKEND_URL}/api/pet-interaction"


def parse_assessment_data(data: bytearray) -> dict:
    """Parse AssessmentResult struct from ESP32 (32 bytes)"""
    # struct AssessmentResult {
    #   uint32_t timestamp;        // 4 bytes
    #   uint8_t orientation_score; // 1 byte
    #   uint8_t memory_score;      // 1 byte
    #   uint8_t attention_score;   // 1 byte
    #   uint8_t executive_score;   // 1 byte
    #   uint8_t total_score;       // 1 byte
    #   uint16_t avg_response_time_ms; // 2 bytes
    #   uint8_t alert_level;       // 1 byte
    #   // padding to 32 bytes
    # }
    # Total: 4 + 1 + 1 + 1 + 1 + 1 + 2 + 1 = 12 bytes minimum
    if len(data) < 12:
        print(f"Warning: Assessment data too short ({len(data)} bytes), expected at least 12")
        return None
    
    try:
        # Format: I (uint32) + 5B (5 uint8) + H (uint16) = 4 + 5 + 2 = 11 bytes
        # But we need 12 bytes total, so let's parse it correctly
        # Actually: I (4) + B (1) + B (1) + B (1) + B (1) + B (1) + H (2) + B (1) = 12 bytes
        unpacked = struct.unpack("<IBBBBBHB", data[:12])  # Little-endian
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
    except struct.error as e:
        print(f"Error parsing assessment data: {e}")
        print(f"Data length: {len(data)}, hex: {data.hex()[:32]}")
        return None


def parse_interaction_data(data: bytearray) -> dict:
    """Parse InteractionLog struct from ESP32"""
    # struct InteractionLog {
    #   uint32_t timestamp;        // 4 bytes
    #   uint8_t interaction_type;  // 1 byte
    #   uint16_t response_time_ms; // 2 bytes
    #   uint8_t success;           // 1 byte
    #   int8_t mood_selected;      // 1 byte (signed)
    # }
    if len(data) < 9:
        print(f"Warning: Interaction data too short ({len(data)} bytes)")
        return None
    
    # Format: I (uint32), B (uint8), H (uint16), B (uint8), b (int8)
    unpacked = struct.unpack("<IBHBb", data[:9])  # Little-endian
    mood = unpacked[4]  # Already signed from 'b' format
    
    interaction_names = ["feed", "play", "clean", "game"]
    interaction_name = interaction_names[unpacked[1]] if unpacked[1] < len(interaction_names) else "unknown"
    
    return {
        "device_timestamp_ms": unpacked[0],
        "interaction_type": unpacked[1],
        "response_time_ms": unpacked[2],
        "success": bool(unpacked[3]),
        "mood_selected": mood if mood >= 0 else None,
    }


def send_to_backend(endpoint: str, data: dict) -> bool:
    """Send data to backend API"""
    try:
        response = requests.post(endpoint, json=data, timeout=5)
        if response.status_code == 200:
            print(f"✓ Data sent to backend: {data}")
            return True
        else:
            print(f"✗ Backend error {response.status_code}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send to backend: {e}")
        return False


def assessment_handler(sender: BleakGATTCharacteristic, data: bytearray):
    """Handle assessment characteristic notifications"""
    print(f"\n[Assessment] Received {len(data)} bytes")
    assessment = parse_assessment_data(data)
    if assessment:
        print(f"  Score: {assessment['total_score']}/12 "
              f"(O:{assessment['orientation_score']} "
              f"M:{assessment['memory_score']} "
              f"A:{assessment['attention_score']} "
              f"E:{assessment['executive_score']})")
        print(f"  Alert Level: {assessment['alert_level']}")
        send_to_backend(ASSESSMENT_ENDPOINT, assessment)
    else:
        print("  Failed to parse assessment data")


def interaction_handler(sender: BleakGATTCharacteristic, data: bytearray):
    """Handle interaction characteristic notifications"""
    print(f"\n[Interaction] Received {len(data)} bytes")
    interaction = parse_interaction_data(data)
    if interaction:
        interaction_names = ["feed", "play", "clean", "game"]
        name = interaction_names[interaction['interaction_type']] if interaction['interaction_type'] < len(interaction_names) else "unknown"
        print(f"  Type: {name}, Success: {interaction['success']}, "
              f"Time: {interaction['response_time_ms']}ms")
        if interaction['mood_selected'] is not None:
            print(f"  Mood: {interaction['mood_selected']}")
        send_to_backend(INTERACTION_ENDPOINT, interaction)
    else:
        print("  Failed to parse interaction data")


async def connect_and_subscribe(device_name: str, backend_url: str):
    """Scan for device, connect, and subscribe to characteristics"""
    global BACKEND_URL, ASSESSMENT_ENDPOINT, INTERACTION_ENDPOINT
    BACKEND_URL = backend_url
    ASSESSMENT_ENDPOINT = f"{backend_url}/api/cognitive-assessment"
    INTERACTION_ENDPOINT = f"{backend_url}/api/pet-interaction"
    
    print(f"Scanning for BLE device: {device_name}")
    print(f"Backend URL: {backend_url}")
    print("Press Ctrl+C to stop\n")
    
    device = None
    while device is None:
        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if d.name and device_name.lower() in d.name.lower():
                device = d
                print(f"Found device: {device.name} ({device.address})")
                break
        
        if device is None:
            print(f"Device '{device_name}' not found. Retrying...")
            await asyncio.sleep(2)
    
    async with BleakClient(device.address) as client:
        print(f"Connected to {device.name}")
        print("Subscribing to characteristics...")
        
        # Subscribe to assessment characteristic
        try:
            await client.start_notify(ASSESSMENT_CHAR_UUID, assessment_handler)
            print(f"✓ Subscribed to assessment characteristic")
        except Exception as e:
            print(f"✗ Failed to subscribe to assessment: {e}")
        
        # Subscribe to interaction characteristic
        try:
            await client.start_notify(INTERACTION_CHAR_UUID, interaction_handler)
            print(f"✓ Subscribed to interaction characteristic")
        except Exception as e:
            print(f"✗ Failed to subscribe to interaction: {e}")
        
        print("\n" + "="*50)
        print("Bridge is running. Waiting for data...")
        print("="*50 + "\n")
        
        # Keep connection alive and reconnect if disconnected
        try:
            while True:
                if not client.is_connected:
                    print("\n⚠ Device disconnected. Attempting to reconnect...")
                    await asyncio.sleep(2)
                    # Try to reconnect
                    try:
                        await client.connect()
                        if client.is_connected:
                            print("✓ Reconnected!")
                            # Re-subscribe
                            await client.start_notify(ASSESSMENT_CHAR_UUID, assessment_handler)
                            await client.start_notify(INTERACTION_CHAR_UUID, interaction_handler)
                            print("✓ Re-subscribed to characteristics")
                        else:
                            print("✗ Reconnection failed, retrying...")
                    except Exception as e:
                        print(f"✗ Reconnection error: {e}, retrying...")
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nStopping bridge...")
            try:
                await client.stop_notify(ASSESSMENT_CHAR_UUID)
                await client.stop_notify(INTERACTION_CHAR_UUID)
            except:
                pass
            print("Bridge stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="BLE Bridge for CogniPet Device",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default settings (localhost:8000, device name "CogniPet")
  python ble_bridge.py
  
  # Specify custom backend URL
  python ble_bridge.py --backend-url http://192.168.1.100:8000
  
  # Specify custom device name
  python ble_bridge.py --device-name MyCogniPet
        """
    )
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000",
        help="Backend API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--device-name",
        default=BLE_DEVICE_NAME,
        help=f"BLE device name to connect to (default: {BLE_DEVICE_NAME})"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(connect_and_subscribe(args.device_name, args.backend_url))
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

