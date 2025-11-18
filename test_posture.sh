#!/bin/bash
# Quick test script for posture detection

echo "Testing Posture Detection..."
echo "================================"
echo ""

# Check if service is running
echo "1. Checking service status..."
STATUS=$(curl -s http://localhost:8000/api/posture/statistics 2>/dev/null)
if echo "$STATUS" | grep -q "runtime_seconds"; then
    RUNTIME=$(echo "$STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('runtime_seconds', 0))" 2>/dev/null)
    echo "   ✅ Service is running (runtime: ${RUNTIME}s)"
else
    echo "   ❌ Service not responding"
    echo "   Check: tail -20 /tmp/cognipet_backend.log"
    exit 1
fi

# Check current posture
echo ""
echo "2. Checking current posture..."
CURRENT=$(curl -s http://localhost:8000/api/posture/current 2>/dev/null)
if echo "$CURRENT" | grep -q "posture"; then
    echo "   ✅ Posture detected:"
    echo "$CURRENT" | python3 -m json.tool 2>/dev/null | head -10
else
    echo "   ⚠️  No posture detected yet"
    echo "   (This is normal if no one is in front of camera)"
    echo "$CURRENT" | python3 -m json.tool 2>/dev/null 2>/dev/null || echo "$CURRENT"
fi

# Check statistics
echo ""
echo "3. Checking statistics..."
STATS=$(curl -s http://localhost:8000/api/posture/statistics 2>/dev/null)
if echo "$STATS" | grep -q "total_detections"; then
    TOTAL=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_detections', 0))" 2>/dev/null)
    echo "   Total detections: $TOTAL"
    echo "$STATS" | python3 -m json.tool 2>/dev/null | grep -A 10 "posture_distribution" || echo "   No posture distribution data yet"
else
    echo "   ⚠️  Could not get statistics"
fi

# Check sleep score integration
echo ""
echo "4. Checking sleep score integration..."
LATEST=$(curl -s http://localhost:8000/api/latest 2>/dev/null)
if echo "$LATEST" | grep -q "Posture"; then
    echo "   ✅ Posture data in sleep samples:"
    echo "$LATEST" | python3 -m json.tool 2>/dev/null | grep -E "(SleepScore|Posture|PostureConfidence)" | head -5
else
    echo "   ⚠️  No posture data in sleep samples yet"
    echo "   (Wait for sleep data to be processed)"
fi

# Check model file
echo ""
echo "5. Checking model file..."
if [ -f "best_model.pt" ]; then
    SIZE=$(du -h best_model.pt | cut -f1)
    echo "   ✅ Model file found: best_model.pt ($SIZE)"
elif [ -f "backend/best_model.pt" ]; then
    SIZE=$(du -h backend/best_model.pt | cut -f1)
    echo "   ✅ Model file found: backend/best_model.pt ($SIZE)"
else
    echo "   ❌ Model file not found!"
    echo "   Expected: best_model.pt or backend/best_model.pt"
fi

echo ""
echo "================================"
echo "Test complete!"
echo ""
echo "Next steps:"
echo "- Position yourself in front of camera"
echo "- Wait a few seconds for detection"
echo "- Run this script again to see results"
echo "- Check dashboard at http://localhost:8000/"

