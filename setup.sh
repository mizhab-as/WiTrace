#!/bin/bash

# WiFi CSI Presence Detection - Setup Script
# This script helps set up the Python environment and dependencies

set -e  # Exit on error

echo "================================================"
echo "  WiFi CSI Presence Detection - Setup"
echo "================================================"
echo ""

# Check Python installation
echo "🐍 Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "   ✓ Found: $PYTHON_VERSION"
else
    echo "   ❌ Python 3 not found. Please install Python 3.7 or later."
    exit 1
fi

# Navigate to python directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_DIR="$SCRIPT_DIR/python"

if [ ! -d "$PYTHON_DIR" ]; then
    echo "❌ Python directory not found: $PYTHON_DIR"
    exit 1
fi

cd "$PYTHON_DIR"

# Check if virtual environment exists
if [ ! -d "env" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv env
    echo "   ✓ Virtual environment created"
else
    echo ""
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔄 Activating virtual environment..."
source env/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "   ✓ pip upgraded"

# Install requirements
echo ""
echo "📥 Installing Python dependencies..."
if [ -f "../requirements.txt" ]; then
    pip install -r ../requirements.txt
    echo "   ✓ Dependencies installed"
else
    echo "   ⚠️  requirements.txt not found, installing manually..."
    pip install numpy scipy matplotlib pyserial
    echo "   ✓ Dependencies installed"
fi

# Make scripts executable
echo ""
echo "🔧 Setting up scripts..."
chmod +x run_presence_detection.py 2>/dev/null || true
echo "   ✓ Scripts configured"

# Check ESP-IDF for firmware (optional)
echo ""
echo "🔍 Checking for ESP-IDF (for firmware compilation)..."
if command -v idf.py &> /dev/null; then
    IDF_VERSION=$(idf.py --version 2>/dev/null | head -n1 || echo "unknown")
    echo "   ✓ ESP-IDF found: $IDF_VERSION"
    echo "   ℹ️  You can compile firmware with: cd firmware/csi_receiver && idf.py build"
else
    echo "   ⚠️  ESP-IDF not found (only needed for firmware compilation)"
    echo "   ℹ️  If you need to compile ESP32 firmware, install ESP-IDF:"
    echo "      https://docs.espressif.com/projects/esp-idf/en/latest/get-started/"
fi

echo ""
echo "================================================"
echo "  ✅ Setup Complete!"
echo "================================================"
echo ""
echo "📋 Next Steps:"
echo ""
echo "  1. Configure WiFi credentials in firmware/csi_receiver/main/csi_receiver.c"
echo "     (Change WIFI_SSID and WIFI_PASS)"
echo ""
echo "  2. Flash ESP32 firmware (if not already done):"
echo "     cd firmware/csi_receiver"
echo "     idf.py flash monitor"
echo ""
echo "  3. Run presence detection:"
echo "     cd python"
echo "     source env/bin/activate"
echo "     python3 run_presence_detection.py"
echo ""
echo "================================================"
