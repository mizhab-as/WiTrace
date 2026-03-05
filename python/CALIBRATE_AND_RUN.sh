#!/bin/bash
# Complete workflow: Calibrate from stored data, then run real-time detection

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  🎯 WiFi CSI Detection - CALIBRATE & RUN                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will:"
echo "  1️⃣  Calibrate using stored data files (empty, occupied, multi_occ)"
echo "  2️⃣  Save calibration thresholds to calibration.json"
echo "  3️⃣  Start real-time web server with calibrated thresholds"
echo ""

cd /Users/mizhabas/wifi_csi_imaging/python
source env/bin/activate

# Step 1: Calibrate
echo "════════════════════════════════════════════════════════════════"
echo "STEP 1: Running Calibration from Stored Data"
echo "════════════════════════════════════════════════════════════════"
echo ""

python3 auto_calibrate.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Calibration failed! Please check your data files."
    exit 1
fi

echo ""
echo "✅ Calibration completed successfully!"
echo ""

# Step 2: Start web server
echo "════════════════════════════════════════════════════════════════"
echo "STEP 2: Starting Real-Time Web Server"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "The web server will now start with the calibrated thresholds."
echo "Open your browser to: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

read -p "Press ENTER to start the web server..."
echo ""

# Find ESP32 port
ESP32_PORT="/dev/cu.usbserial-0001"
if [ ! -e "$ESP32_PORT" ]; then
    echo "⚠️  Default port $ESP32_PORT not found. Searching..."
    ESP32_PORT=$(ls /dev/cu.usb* 2>/dev/null | head -1)
    if [ -z "$ESP32_PORT" ]; then
        echo "❌ No ESP32 found! Please connect your ESP32."
        exit 1
    fi
    echo "✅ Found ESP32 at: $ESP32_PORT"
fi

echo "📡 Using ESP32 port: $ESP32_PORT"
echo ""

python3 web_monitor_server.py --port "$ESP32_PORT"
