#!/usr/bin/env python3
"""
Quick test to verify BLE bridge connection status
"""
import asyncio
from bleak import BleakScanner

# CogniPet service UUID
COGNIPET_SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"

async def test_connection():
    print("Scanning for BLE devices (timeout: 10 seconds)...")
    print("Looking for CogniPet by name or service UUID...")
    print("="*60)
    devices = await BleakScanner.discover(timeout=10.0)
    
    print(f"\nFound {len(devices)} BLE device(s):\n")
    
    found_cognipet = False
    cognipet_address = None
    
    for d in devices:
        name = d.name if d.name else "(No name)"
        is_cognipet = False
        
        # Check by name
        if d.name and ("CogniPet" in d.name or "cognipet" in d.name.lower()):
            is_cognipet = True
            found_cognipet = True
            cognipet_address = d.address
        
        # Check by service UUID (in metadata)
        if not is_cognipet:
            try:
                metadata = d.metadata if hasattr(d, 'metadata') else {}
                uuids = metadata.get('uuids', [])
                if COGNIPET_SERVICE_UUID.lower() in [u.lower() for u in uuids]:
                    is_cognipet = True
                    found_cognipet = True
                    cognipet_address = d.address
            except:
                pass
        
        # Only print if it's CogniPet or if verbose mode
        if is_cognipet:
            print(f"  - {name} ⭐ COGNIPET FOUND!")
            print(f"    Address: {d.address}")
            try:
                rssi = getattr(d, 'rssi', None)
                if rssi is not None:
                    print(f"    RSSI: {rssi} dBm")
            except:
                pass
            print()
    
    # If not found, show summary
    if not found_cognipet:
        print("  (Scanning all devices - CogniPet not found by name or UUID)")
        print(f"  Found {len(devices)} total devices")
        print("  CogniPet might be one of the '(No name)' devices")
        print()
    
    print("="*60)
    if found_cognipet:
        print("✓ CogniPet device found and is advertising!")
    else:
        print("✗ CogniPet device not found")
        print("\nTroubleshooting:")
        print("  1. Make sure ESP32 is powered on")
        print("  2. Check Serial Monitor - should see 'BLE advertising started'")
        print("  3. Try restarting the ESP32 (unplug/replug USB)")
        print("  4. Check if deviceConnected is YES in Serial Monitor")
        print("     (if YES, something else is connected - restart ESP32)")
        print("  5. Make sure ESP32-S3 board is selected in Arduino IDE")
    
    return found_cognipet

if __name__ == "__main__":
    asyncio.run(test_connection())

