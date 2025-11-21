#!/bin/bash
# Start posture monitoring with camera

echo "Starting Posture Monitoring..."
echo "================================"

# Check if server is running
if ! curl -s http://localhost:8000/status > /dev/null 2>&1; then
    echo "✗ Backend server is not running"
    echo "  Start it with: ./restart_all.sh"
    exit 1
fi

# Get current camera setting
echo "1. Checking camera status..."
CURRENT_SOURCE=$(curl -s http://localhost:8000/api/posture/status 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('video_source', '0'))" 2>/dev/null || echo "0")

echo ""
echo "2. Current posture detection status:"
curl -s http://localhost:8000/api/posture/status | python3 -m json.tool

echo ""
echo "3. Starting posture detection..."
# Start the service if not running
curl -s -X POST http://localhost:8000/api/posture/start > /dev/null

sleep 2

echo ""
echo "4. Updated status:"
curl -s http://localhost:8000/api/posture/status | python3 -m json.tool

echo ""
echo "================================"
echo "Posture monitoring is now active!"
echo ""
echo "To monitor in real-time:"
echo "  watch -n 2 'curl -s http://localhost:8000/api/posture/current | python3 -m json.tool'"
echo ""
echo "Or check the dashboard:"
echo "  http://localhost:8000/ -> Sleep Monitoring tab"
echo ""
echo "To stop:"
echo "  curl -X POST http://localhost:8000/api/posture/stop"

