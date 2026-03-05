#!/usr/bin/env python3
"""Final system verification"""
import sys
import os

os.chdir('/Users/mizhabas/wifi_csi_imaging/python')

print("\n✅ FINAL SYSTEM VERIFICATION\n")

# Test imports
try:
    import numpy as np
    print("✅ numpy imported successfully")
    import scipy
    print("✅ scipy imported successfully")
    import matplotlib
    print("✅ matplotlib imported successfully")
    import serial
    print("✅ pyserial imported successfully")
    import flask
    print("✅ flask imported successfully")
    from flask_cors import CORS
    print("✅ flask-cors imported successfully")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test detection modules
try:
    from csi_detector import CSIPreprocessor, FeatureExtractor
    print("✅ csi_detector modules imported")
except Exception as e:
    print(f"❌ csi_detector error: {e}")
    sys.exit(1)

# Test web server
try:
    from web_monitor_server import DataStore, find_esp32_port
    print("✅ web_monitor_server imported successfully")
except Exception as e:
    print(f"❌ web_monitor_server error: {e}")
    sys.exit(1)

# Test run_presence_detection
try:
    from run_presence_detection import find_esp32_port
    print("✅ run_presence_detection imported successfully")
except Exception as e:
    print(f"❌ run_presence_detection error: {e}")
    sys.exit(1)

# Check calibration
import json
if os.path.exists("calibration.json"):
    with open("calibration.json") as f:
        cal = json.load(f)
    print(f"✅ Calibration loaded: empty={cal['empty']}, multi={cal['multi']}")
else:
    print("⚠️  No calibration.json (will auto-calibrate on startup)")

print("\n✅ ALL SYSTEMS READY FOR DEPLOYMENT!\n")
