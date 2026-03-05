# 🚀 Quick Start Guide - WiFi CSI Presence Detection

Get up and running in 5 minutes!

## Step 1: Setup (2 minutes)

### macOS/Linux:
```bash
./setup.sh
```

### Windows:
```cmd
setup.bat
```

## Step 2: Configure WiFi (1 minute)

Edit [firmware/csi_receiver/main/csi_receiver.c](firmware/csi_receiver/main/csi_receiver.c):

```c
#define WIFI_SSID "YourWiFiName"      // ← Change this
#define WIFI_PASS "YourWiFiPassword"  // ← Change this
```

## Step 3: Flash ESP32 (2 minutes)

```bash
cd firmware/csi_receiver
idf.py build flash monitor
```

**Note your serial port:**
- macOS: `/dev/cu.usbserial-*`
- Linux: `/dev/ttyUSB0`
- Windows: `COM3`

## Step 4: Run Detection! 🎉

```bash
cd python
source env/bin/activate          # Windows: env\Scripts\activate.bat
python3 run_presence_detection.py
```

## What You'll See:

1. **Auto-detection** of ESP32 port
2. **Calibration** phase (10 seconds - stay still!)
3. **Real-time graphs** showing CSI data
4. **Color-coded status**:
   - 🏠 **EMPTY** (Green) - No one detected
   - 🧍 **PERSON_STILL** (Yellow) - Person present, not moving
   - 🚶 **PERSON_MOVING** (Purple) - Person walking
   - 👥 **HIGH_ACTIVITY** (Red) - Multiple people or high activity

## Tips for Best Results:

1. **During calibration**: Leave room empty or stay completely still
2. **Placement**: Put ESP32 in central location of room
3. **Environment**: Close doors/windows for better detection
4. **WiFi**: Ensure strong WiFi signal in the area

## Troubleshooting:

### No CSI data?
- Check ESP32 serial monitor: `idf.py monitor`
- Verify WiFi credentials
- Ensure ESP32 shows "WiFi Connected"

### Can't find ESP32?
- Install USB drivers (CP210x or CH340)
- Run with manual port: `python3 run_presence_detection.py /dev/ttyUSB0`

### Detection not accurate?
- Increase calibration time in the script
- Try different ESP32 placement
- Reduce environmental interference

## Need More Help?

See full [README.md](README.md) for detailed documentation!

---

**Happy detecting! 🎯**
