#!/bin/bash

# ESP32 Firmware Build and Flash Script
# Simplifies the firmware compilation and flashing process

set -e

echo "================================================"
echo "  ESP32 CSI Firmware - Build & Flash"
echo "================================================"
echo ""

# Navigate to firmware directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FIRMWARE_DIR="$SCRIPT_DIR/firmware/csi_receiver"

if [ ! -d "$FIRMWARE_DIR" ]; then
    echo "❌ Firmware directory not found: $FIRMWARE_DIR"
    exit 1
fi

cd "$FIRMWARE_DIR"

# Check ESP-IDF
if ! command -v idf.py &> /dev/null; then
    echo "❌ ESP-IDF not found. Please install ESP-IDF first."
    echo "   See: https://docs.espressif.com/projects/esp-idf/en/latest/get-started/"
    exit 1
fi

echo "ESP-IDF found: $(idf.py --version 2>&1 | head -n1)"
echo ""

# Check WiFi configuration
echo "🔍 Checking WiFi configuration..."
if grep -q 'WIFI_SSID "Connecting..."' main/csi_receiver.c; then
    echo "⚠️  WARNING: Default WiFi SSID detected!"
    echo "   Edit main/csi_receiver.c to set your WiFi credentials"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Menu
echo ""
echo "Select action:"
echo "  1. Build only"
echo "  2. Build and flash"
echo "  3. Build, flash, and monitor"
echo "  4. Monitor only (view serial output)"
echo "  5. Clean build"
echo ""
read -p "Enter choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🔨 Building firmware..."
        idf.py build
        echo ""
        echo "✅ Build complete!"
        ;;
    2)
        echo ""
        read -p "Enter ESP32 port (e.g., /dev/ttyUSB0): " port
        echo "🔨 Building firmware..."
        idf.py build
        echo "📤 Flashing to $port..."
        idf.py -p "$port" flash
        echo ""
        echo "✅ Flash complete!"
        ;;
    3)
        echo ""
        read -p "Enter ESP32 port (e.g., /dev/ttyUSB0): " port
        echo "🔨 Building firmware..."
        idf.py build
        echo "📤 Flashing to $port..."
        idf.py -p "$port" flash
        echo "📊 Starting monitor (Press Ctrl+] to exit)..."
        echo ""
        idf.py -p "$port" monitor
        ;;
    4)
        echo ""
        read -p "Enter ESP32 port (e.g., /dev/ttyUSB0): " port
        echo "📊 Starting monitor (Press Ctrl+] to exit)..."
        echo ""
        idf.py -p "$port" monitor
        ;;
    5)
        echo ""
        echo "🧹 Cleaning build..."
        idf.py fullclean
        echo "✅ Clean complete!"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "================================================"
