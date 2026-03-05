#!/bin/bash

# ============================================================================
# ESP32 FIRMWARE BUILD & FLASH SCRIPT
# ============================================================================

set -e

PROJECT_ROOT="/Users/mizhabas/wifi_csi_imaging"
FIRMWARE_DIR="$PROJECT_ROOT/firmware/csi_receiver"
IDF_PATH="/Users/mizhabas/esp/esp-idf"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🔧 ESP32 CSI RECEIVER - FIRMWARE BUILDER & FLASHER        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# Step 1: Setup ESP-IDF
# ============================================================================
echo "📍 Checking ESP-IDF..."
if [ ! -d "$IDF_PATH" ]; then
    echo "❌ ESP-IDF not found at: $IDF_PATH"
    echo "   Please install ESP-IDF first"
    exit 1
fi

echo "✅ ESP-IDF found at: $IDF_PATH"
echo ""

# Source ESP-IDF
source "$IDF_PATH/export.sh"

# ============================================================================
# Step 2: Verify WiFi Credentials
# ============================================================================
echo "🔐 Verifying WiFi Configuration..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SSID=$(grep '#define WIFI_SSID' "$FIRMWARE_DIR/main/csi_receiver.c" | awk -F'"' '{print $2}')
PASS=$(grep '#define WIFI_PASS' "$FIRMWARE_DIR/main/csi_receiver.c" | awk -F'"' '{print $2}')

echo "   SSID: $SSID"
echo "   Password: $(echo $PASS | sed 's/./*/g')"
echo ""

echo "⚠️  ESP32 only works with 2.4GHz WiFi (not 5GHz)"
read -p "Press ENTER to continue with flashing..."
echo ""

# ============================================================================
# Step 3: Auto-detect ESP32 Port
# ============================================================================
echo "🔍 Finding ESP32 Serial Port..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PORTS=$(ls /dev/cu.usb* 2>/dev/null || echo "")

if [ -z "$PORTS" ]; then
    echo "❌ No ESP32 found on USB ports"
    echo ""
    echo "Please:"
    echo "  1. Connect ESP32 to USB"
    echo "  2. Wait 2 seconds for driver to load"
    echo "  3. Run this script again"
    exit 1
fi

echo "Found ports:"
IFS=$'\n'
i=1
for port in $PORTS; do
    echo "   $i. $port"
    ((i++))
done

# Use first port if only one
PORT_COUNT=$(echo "$PORTS" | wc -l)
if [ $PORT_COUNT -eq 1 ]; then
    ESP32_PORT="$PORTS"
    echo ""
    echo "✅ Using: $ESP32_PORT"
else
    echo ""
    read -p "Select port number [1]: " CHOICE
    CHOICE=${CHOICE:-1}
    ESP32_PORT=$(echo "$PORTS" | sed -n "${CHOICE}p")
fi

echo ""

# ============================================================================
# Step 4: Build Firmware
# ============================================================================
echo "🔨 Building Firmware..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$FIRMWARE_DIR"

# Clean previous build
idf.py fullclean > /dev/null 2>&1 || true

# Build
if idf.py build; then
    echo ""
    echo "✅ Build successful!"
else
    echo ""
    echo "❌ Build failed. Check errors above."
    exit 1
fi

echo ""

# ============================================================================
# Step 5: Flash Firmware
# ============================================================================
echo "📥 Flashing Firmware to ESP32..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Port: $ESP32_PORT"
echo ""

if idf.py -p "$ESP32_PORT" flash; then
    echo ""
    echo "✅ Flash successful!"
else
    echo ""
    echo "❌ Flash failed. Check:"
    echo "   • USB cable is properly connected"
    echo "   • ESP32 is powered on"
    echo "   • You have permission to access $ESP32_PORT"
    exit 1
fi

echo ""

# ============================================================================
# Step 6: Monitor Output (Optional)
# ============================================================================
echo "🔍 Starting Serial Monitor (Press Ctrl+C to exit)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Monitor ESP32 output? [y/N]: " MONITOR
if [[ "$MONITOR" == "y" || "$MONITOR" == "Y" ]]; then
    idf.py -p "$ESP32_PORT" monitor
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ FIRMWARE FLASHING COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1️⃣  The ESP32 is now running the CSI receiver firmware"
echo ""
echo "2️⃣  Start the web server:"
echo "   cd $PROJECT_ROOT/python"
echo "   source env/bin/activate"
echo "   python3 web_monitor_server.py"
echo ""
echo "3️⃣  Open browser: http://localhost:8080"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""
