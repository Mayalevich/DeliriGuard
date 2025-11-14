#!/bin/bash
# Check status of all CogniPet services

echo "=== CogniPet System Status ==="
echo ""

# Check backend
if curl -s http://localhost:8000/status > /dev/null 2>&1; then
    echo "✓ Backend Server: Running on http://localhost:8000"
    BACKEND_PID=$(ps aux | grep "[u]vicorn.*server:app" | awk '{print $2}' | head -1)
    echo "  PID: $BACKEND_PID"
else
    echo "✗ Backend Server: Not running"
fi

# Check BLE bridge
BRIDGE_PID=$(ps aux | grep "[b]le_bridge" | awk '{print $2}' | head -1)
if [ -n "$BRIDGE_PID" ]; then
    echo "✓ BLE Bridge: Running (PID: $BRIDGE_PID)"
    echo "  Log: tail -f /tmp/ble_bridge.log"
else
    echo "✗ BLE Bridge: Not running"
fi

# Check database
if [ -f "backend/sleep_data.db" ]; then
    DB_SIZE=$(du -h backend/sleep_data.db | cut -f1)
    echo "✓ Database: Exists ($DB_SIZE)"
    
    # Count records
    ASSESSMENTS=$(cd backend && python3 -c "import sqlite3; conn = sqlite3.connect('sleep_data.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM cognitive_assessments'); print(cursor.fetchone()[0]); conn.close()" 2>/dev/null)
    INTERACTIONS=$(cd backend && python3 -c "import sqlite3; conn = sqlite3.connect('sleep_data.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM pet_interactions'); print(cursor.fetchone()[0]); conn.close()" 2>/dev/null)
    
    echo "  Assessments: $ASSESSMENTS"
    echo "  Interactions: $INTERACTIONS"
else
    echo "✗ Database: Not found"
fi

echo ""
echo "=== Quick Commands ==="
echo "Restart all: ./restart_all.sh"
echo "Stop all: ./stop_all.sh"
echo "View assessments: curl http://localhost:8000/api/assessments | python3 -m json.tool"
echo "View interactions: curl http://localhost:8000/api/interactions | python3 -m json.tool"

