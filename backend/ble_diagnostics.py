#!/usr/bin/env python3
"""
BLE Diagnostics Tool
Helps debug BLE connection and data transmission issues.
"""

import asyncio
import sys
from bleak import BleakScanner, BleakClient

BLE_DEVICE_NAME = "CogniPet"
SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
ASSESSMENT_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"
INTERACTION_CHAR_UUID = "1c95d5e3-d8f7-413a-bf3d-7a2e5d7be87e"


async def scan_for_device():
    """Scan for CogniPet device"""
    print("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5.0)
    
    print(f"\nFound {len(devices)} devices:")
    cognipet = None
    for device in devices:
        name = device.name or "Unknown"
        print(f"  - {name} ({device.address})")
        if BLE_DEVICE_NAME.lower() in name.lower():
            cognipet = device
            print(f"    ✓ This is the CogniPet device!")
    
    return cognipet


async def inspect_device(device):
    """Connect and inspect device characteristics"""
    print(f"\n{'='*60}")
    print(f"Connecting to {device.name} ({device.address})...")
    print(f"{'='*60}\n")
    
    async with BleakClient(device.address) as client:
        print(f"✓ Connected!\n")
        
        # List all services
        print("Services:")
        for service in client.services:
            print(f"  Service: {service.uuid}")
            if str(service.uuid).lower() == SERVICE_UUID.lower():
                print(f"    ✓ This is the CogniPet service!")
            
            # List characteristics
            for char in service.characteristics:
                props = []
                if "read" in char.properties:
                    props.append("READ")
                if "write" in char.properties:
                    props.append("WRITE")
                if "notify" in char.properties:
                    props.append("NOTIFY")
                
                print(f"    Characteristic: {char.uuid} [{', '.join(props)}]")
                
                # Check if this is our target characteristic
                if str(char.uuid).lower() == ASSESSMENT_CHAR_UUID.lower():
                    print(f"      ✓ This is the ASSESSMENT characteristic!")
                if str(char.uuid).lower() == INTERACTION_CHAR_UUID.lower():
                    print(f"      ✓ This is the INTERACTION characteristic!")
        
        print(f"\n{'='*60}")
        print("Checking subscriptions...")
        print(f"{'='*60}\n")
        
        # Try to read current values
        try:
            assessment_char = client.services.get_characteristic(ASSESSMENT_CHAR_UUID)
            if assessment_char:
                print(f"✓ Assessment characteristic found")
                try:
                    value = await client.read_gatt_char(ASSESSMENT_CHAR_UUID)
                    print(f"  Current value: {value.hex() if value else 'None'}")
                except Exception as e:
                    print(f"  Cannot read: {e}")
        except Exception as e:
            print(f"✗ Assessment characteristic not found: {e}")
        
        try:
            interaction_char = client.services.get_characteristic(INTERACTION_CHAR_UUID)
            if interaction_char:
                print(f"✓ Interaction characteristic found")
                try:
                    value = await client.read_gatt_char(INTERACTION_CHAR_UUID)
                    print(f"  Current value: {value.hex() if value else 'None'}")
                except Exception as e:
                    print(f"  Cannot read: {e}")
        except Exception as e:
            print(f"✗ Interaction characteristic not found: {e}")
        
        print(f"\n{'='*60}")
        print("Waiting for notifications (10 seconds)...")
        print("Trigger an assessment or interaction on your device now!")
        print(f"{'='*60}\n")
        
        assessment_received = False
        interaction_received = False
        
        def assessment_handler(sender, data):
            nonlocal assessment_received
            assessment_received = True
            print(f"✓ [ASSESSMENT] Received {len(data)} bytes: {data.hex()}")
        
        def interaction_handler(sender, data):
            nonlocal interaction_received
            interaction_received = True
            print(f"✓ [INTERACTION] Received {len(data)} bytes: {data.hex()}")
        
        # Subscribe to notifications
        try:
            await client.start_notify(ASSESSMENT_CHAR_UUID, assessment_handler)
            print("✓ Subscribed to assessment notifications")
        except Exception as e:
            print(f"✗ Failed to subscribe to assessment: {e}")
        
        try:
            await client.start_notify(INTERACTION_CHAR_UUID, interaction_handler)
            print("✓ Subscribed to interaction notifications")
        except Exception as e:
            print(f"✗ Failed to subscribe to interaction: {e}")
        
        # Wait for data
        await asyncio.sleep(10)
        
        # Unsubscribe
        try:
            await client.stop_notify(ASSESSMENT_CHAR_UUID)
        except:
            pass
        try:
            await client.stop_notify(INTERACTION_CHAR_UUID)
        except:
            pass
        
        print(f"\n{'='*60}")
        print("Results:")
        print(f"{'='*60}")
        print(f"Assessment data received: {'✓ YES' if assessment_received else '✗ NO'}")
        print(f"Interaction data received: {'✓ YES' if interaction_received else '✗ NO'}")
        
        if not assessment_received:
            print("\n⚠ Assessment data was NOT received!")
            print("  Possible issues:")
            print("  1. Assessment not completed on device")
            print("  2. Device not sending assessment via BLE")
            print("  3. Assessment characteristic not properly configured")
            print("  4. Check ESP32 Serial Monitor for errors")


async def main():
    print("BLE Diagnostics Tool for CogniPet")
    print("="*60)
    
    # Scan for device
    device = await scan_for_device()
    
    if not device:
        print(f"\n✗ CogniPet device not found!")
        print("  Make sure:")
        print("  1. ESP32-S3 is powered on")
        print("  2. Device is within Bluetooth range")
        print("  3. Device name is 'CogniPet'")
        sys.exit(1)
    
    # Inspect device
    await inspect_device(device)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped.")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

