#!/usr/bin/env python3
"""
Test script to verify BLE data transmission from ESP32 to backend.

This script can:
1. Send test data directly to backend API (fast test)
2. Simulate BLE data transmission through the bridge
3. Generate realistic test assessment and interaction data

Usage:
    # Test backend API directly (fast)
    python test_ble_data.py --direct
    
    # Test through BLE bridge (requires bridge running)
    python test_ble_data.py --ble
    
    # Send multiple test assessments
    python test_ble_data.py --direct --count 5
"""

import argparse
import struct
import sys
import time
from typing import Optional

import requests


# Backend API endpoints
BACKEND_URL = "http://localhost:8000"
ASSESSMENT_ENDPOINT = f"{BACKEND_URL}/api/cognitive-assessment"
INTERACTION_ENDPOINT = f"{BACKEND_URL}/api/pet-interaction"


def create_test_assessment_data(
    orientation_score: int = 3,
    memory_score: int = 2,
    attention_score: int = 3,
    executive_score: int = 2,
    avg_response_time_ms: int = 2500,
    device_timestamp_ms: Optional[int] = None,
) -> dict:
    """Create test assessment data matching ESP32 format"""
    if device_timestamp_ms is None:
        device_timestamp_ms = int(time.time() * 1000) % (2**32)
    
    total_score = orientation_score + memory_score + attention_score + executive_score
    
    # Calculate alert level: 0=green, 1=yellow, 2=orange, 3=red
    if total_score >= 10:
        alert_level = 0  # Green
    elif total_score >= 7:
        alert_level = 1  # Yellow
    elif total_score >= 4:
        alert_level = 2  # Orange
    else:
        alert_level = 3  # Red
    
    return {
        "device_timestamp_ms": device_timestamp_ms,
        "orientation_score": orientation_score,
        "memory_score": memory_score,
        "attention_score": attention_score,
        "executive_score": executive_score,
        "total_score": total_score,
        "avg_response_time_ms": avg_response_time_ms,
        "alert_level": alert_level,
    }


def create_test_interaction_data(
    interaction_type: int = 0,  # 0=feed, 1=play, 2=clean, 3=game
    response_time_ms: int = 500,
    success: bool = True,
    mood_selected: Optional[int] = None,
    device_timestamp_ms: Optional[int] = None,
) -> dict:
    """Create test interaction data matching ESP32 format"""
    if device_timestamp_ms is None:
        device_timestamp_ms = int(time.time() * 1000) % (2**32)
    
    return {
        "device_timestamp_ms": device_timestamp_ms,
        "interaction_type": interaction_type,
        "response_time_ms": response_time_ms,
        "success": success,
        "mood_selected": mood_selected if mood_selected is not None and mood_selected >= 0 else None,
    }


def send_to_backend(endpoint: str, data: dict) -> bool:
    """Send data to backend API"""
    try:
        response = requests.post(endpoint, json=data, timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Data sent successfully: {result.get('message', 'OK')}")
            return True
        else:
            print(f"✗ Backend error {response.status_code}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send to backend: {e}")
        return False


def test_backend_direct(count: int = 1):
    """Test backend API directly (bypasses BLE)"""
    print(f"\n{'='*60}")
    print("Testing Backend API Directly")
    print(f"{'='*60}\n")
    
    success_count = 0
    
    # Test scenarios
    test_scenarios = [
        # Good assessment
        {"orientation": 3, "memory": 3, "attention": 3, "executive": 3, "response_time": 2000},
        # Moderate assessment
        {"orientation": 2, "memory": 2, "attention": 2, "executive": 2, "response_time": 3000},
        # Poor assessment
        {"orientation": 1, "memory": 1, "attention": 1, "executive": 1, "response_time": 5000},
        # Mixed assessment
        {"orientation": 3, "memory": 1, "attention": 2, "executive": 2, "response_time": 3500},
    ]
    
    for i in range(count):
        print(f"\n--- Test {i+1}/{count} ---")
        
        # Send assessment
        scenario = test_scenarios[i % len(test_scenarios)]
        assessment = create_test_assessment_data(
            orientation_score=scenario["orientation"],
            memory_score=scenario["memory"],
            attention_score=scenario["attention"],
            executive_score=scenario["executive"],
            avg_response_time_ms=scenario["response_time"],
        )
        
        print(f"Assessment: Score {assessment['total_score']}/12 "
              f"(O:{assessment['orientation_score']} "
              f"M:{assessment['memory_score']} "
              f"A:{assessment['attention_score']} "
              f"E:{assessment['executive_score']}) "
              f"Alert: {assessment['alert_level']}")
        
        if send_to_backend(ASSESSMENT_ENDPOINT, assessment):
            success_count += 1
        
        time.sleep(0.5)
        
        # Send some interactions
        interactions = [
            (0, 450, True, None),   # feed
            (1, 1200, True, None),  # play
            (2, 800, True, None),   # clean
            (0, 500, True, 1),      # feed with mood
        ]
        
        for interaction_type, response_time, success, mood in interactions[:2]:  # Send 2 interactions
            interaction = create_test_interaction_data(
                interaction_type=interaction_type,
                response_time_ms=response_time,
                success=success,
                mood_selected=mood,
            )
            
            interaction_names = ["feed", "play", "clean", "game"]
            name = interaction_names[interaction_type]
            print(f"  Interaction: {name}, Success: {success}, Time: {response_time}ms")
            
            send_to_backend(INTERACTION_ENDPOINT, interaction)
            time.sleep(0.3)
    
    print(f"\n{'='*60}")
    print(f"Results: {success_count}/{count} assessments sent successfully")
    print(f"{'='*60}\n")


def simulate_ble_packet(data: dict, data_type: str = "assessment") -> bytes:
    """Convert data dict to binary format matching ESP32 BLE transmission"""
    if data_type == "assessment":
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
        packet = struct.pack(
            "<I5BH",  # Little-endian: uint32, 5*uint8, uint16
            data["device_timestamp_ms"],
            data["orientation_score"],
            data["memory_score"],
            data["attention_score"],
            data["executive_score"],
            data["total_score"],
            data["avg_response_time_ms"],
            data["alert_level"],
        )
        # Pad to 32 bytes
        packet += b'\x00' * (32 - len(packet))
        return packet
    
    elif data_type == "interaction":
        # struct InteractionLog {
        #   uint32_t timestamp;        // 4 bytes
        #   uint8_t interaction_type;  // 1 byte
        #   uint16_t response_time_ms; // 2 bytes
        #   uint8_t success;           // 1 byte
        #   int8_t mood_selected;      // 1 byte (signed)
        # }
        mood = data.get("mood_selected")
        if mood is None:
            mood = -1
        elif mood > 127:
            mood = mood - 256
        
        packet = struct.pack(
            "<IBHBb",  # Little-endian: uint32, uint8, uint16, uint8, int8
            data["device_timestamp_ms"],
            data["interaction_type"],
            data["response_time_ms"],
            1 if data["success"] else 0,
            mood,
        )
        return packet
    
    else:
        raise ValueError(f"Unknown data type: {data_type}")


def test_ble_bridge(count: int = 1):
    """Test through BLE bridge (requires bridge to be running and connected)"""
    print(f"\n{'='*60}")
    print("Testing BLE Bridge (simulating ESP32 data)")
    print(f"{'='*60}\n")
    print("Note: This simulates the data format but sends directly to backend.")
    print("For full BLE testing, use the actual ESP32 device.\n")
    
    # For now, we'll send directly but in the correct format
    # In a real scenario, you'd inject this into the BLE bridge
    test_backend_direct(count)


def verify_backend_data():
    """Verify data was received by checking API endpoints"""
    print(f"\n{'='*60}")
    print("Verifying Backend Data")
    print(f"{'='*60}\n")
    
    try:
        # Check assessments
        response = requests.get(f"{BACKEND_URL}/api/assessments?limit=10", timeout=5)
        if response.status_code == 200:
            assessments = response.json()
            print(f"✓ Found {len(assessments)} assessments in backend")
            if assessments:
                latest = assessments[-1]
                print(f"  Latest: Score {latest['total_score']}/12, "
                      f"Alert Level {latest['alert_level']}, "
                      f"Time: {latest['recorded_at']}")
        else:
            print(f"✗ Failed to get assessments: {response.status_code}")
        
        # Check interactions
        response = requests.get(f"{BACKEND_URL}/api/interactions?limit=10", timeout=5)
        if response.status_code == 200:
            interactions = response.json()
            print(f"✓ Found {len(interactions)} interactions in backend")
            if interactions:
                latest = interactions[-1]
                print(f"  Latest: {latest['interaction_name']}, "
                      f"Success: {latest['success']}, "
                      f"Time: {latest['recorded_at']}")
        else:
            print(f"✗ Failed to get interactions: {response.status_code}")
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to verify data: {e}")


def main():
    global BACKEND_URL, ASSESSMENT_ENDPOINT, INTERACTION_ENDPOINT
    
    parser = argparse.ArgumentParser(
        description="Test BLE data transmission from ESP32 to backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test backend API directly (fast)
  python test_ble_data.py --direct
  
  # Send 5 test assessments
  python test_ble_data.py --direct --count 5
  
  # Test through BLE bridge
  python test_ble_data.py --ble
  
  # Verify data in backend
  python test_ble_data.py --verify
        """
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Test backend API directly (bypasses BLE)"
    )
    parser.add_argument(
        "--ble",
        action="store_true",
        help="Test through BLE bridge (simulated)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify data in backend"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of test assessments to send (default: 1)"
    )
    parser.add_argument(
        "--backend-url",
        default=BACKEND_URL,
        help=f"Backend API URL (default: {BACKEND_URL})"
    )
    
    args = parser.parse_args()
    
    # Update global endpoints if custom URL provided
    if args.backend_url != BACKEND_URL:
        BACKEND_URL = args.backend_url
        ASSESSMENT_ENDPOINT = f"{BACKEND_URL}/api/cognitive-assessment"
        INTERACTION_ENDPOINT = f"{BACKEND_URL}/api/pet-interaction"
    
    # Check backend is running
    try:
        response = requests.get(f"{BACKEND_URL}/status", timeout=2)
        if response.status_code != 200:
            print(f"✗ Backend not responding at {BACKEND_URL}")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print(f"✗ Cannot connect to backend at {BACKEND_URL}")
        print("  Make sure the backend server is running:")
        print("  python -m uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    print(f"✓ Backend is running at {BACKEND_URL}\n")
    
    if args.verify:
        verify_backend_data()
    elif args.ble:
        test_ble_bridge(args.count)
        verify_backend_data()
    elif args.direct:
        test_backend_direct(args.count)
        verify_backend_data()
    else:
        # Default: test directly
        test_backend_direct(args.count)
        verify_backend_data()


if __name__ == "__main__":
    main()

