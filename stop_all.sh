#!/bin/bash
# Stop all CogniPet services

echo "=== Stopping CogniPet Services ==="
echo ""

echo "Stopping backend server..."
pkill -f "uvicorn.*server:app" 2>/dev/null
lsof -ti:8000 | xargs kill -9 2>/dev/null

echo "Stopping BLE bridge..."
pkill -f "ble_bridge" 2>/dev/null

sleep 2

echo ""
echo "✓ All services stopped"

