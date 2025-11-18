#!/usr/bin/env python3
"""
Test camera access for posture detection
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import cv2
    print("✓ OpenCV is available")
except ImportError:
    print("✗ OpenCV not available. Install with: pip install opencv-python")
    sys.exit(1)

def test_camera(camera_index=0):
    """Test if camera is accessible"""
    print(f"\nTesting camera {camera_index}...")
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"✗ Camera {camera_index} is not accessible")
        print("  Possible reasons:")
        print("  - Camera is being used by another application")
        print("  - Camera permissions not granted")
        print("  - Camera index is wrong (try 0, 1, 2, etc.)")
        return False
    
    print(f"✓ Camera {camera_index} opened successfully")
    
    # Try to read a frame
    ret, frame = cap.read()
    if ret:
        print(f"✓ Successfully read frame (size: {frame.shape[1]}x{frame.shape[0]})")
        cap.release()
        return True
    else:
        print("✗ Could not read frame from camera")
        cap.release()
        return False

def list_cameras(max_test=5):
    """Test multiple camera indices"""
    print("Testing available cameras...")
    available = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
                print(f"  ✓ Camera {i} is available")
            cap.release()
        else:
            cap.release()
    
    if not available:
        print("  ✗ No cameras found")
    else:
        print(f"\nAvailable cameras: {available}")
        print(f"Recommended: Use camera {available[0]}")
    
    return available

if __name__ == "__main__":
    print("=" * 50)
    print("Camera Test for Posture Detection")
    print("=" * 50)
    
    # Test default camera (0)
    if test_camera(0):
        print("\n✓ Default camera (0) works! You can use it for posture detection.")
    else:
        print("\nTrying other camera indices...")
        available = list_cameras()
        if available:
            print(f"\nUse one of these cameras by setting:")
            print(f"  export POSTURE_VIDEO_SOURCE={available[0]}")
        else:
            print("\n✗ No cameras found. Please check:")
            print("  1. Camera is connected")
            print("  2. Camera permissions are granted")
            print("  3. No other app is using the camera")

