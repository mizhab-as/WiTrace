#!/bin/bash

# Quick start script for the new revamped system

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   🚀 WiFi CSI Presence Detection - NEW CLEAN VERSION          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

cd /Users/mizhabas/wifi_csi_imaging/python

# Check if server is already running
if pgrep -f "python3 app.py" > /dev/null; then
    echo "⚠️  Server already running. Killing old process..."
    pkill -f "python3 app.py"
    sleep 2
fi

# Activate environment
source env/bin/activate

echo "✅ Environment activated"
echo ""
echo "🚀 Starting clean Flask server..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python3 app.py
