# Troubleshooting Guide

Common issues and solutions for WiFi CSI Presence Detection System.

## Table of Contents
1. [ESP32 Connection Issues](#esp32-connection-issues)
2. [No CSI Data](#no-csi-data)
3. [Poor Detection Accuracy](#poor-detection-accuracy)
4. [Python Environment Issues](#python-environment-issues)
5. [Compilation Errors](#compilation-errors)
6. [Serial Communication Problems](#serial-communication-problems)

---

## ESP32 Connection Issues

### Problem: ESP32 not detected by computer

**Symptoms**:
- Device not showing up in port list
- "No such file or directory" error

**Solutions**:

1. **Install USB Drivers**:
   - **CP210x**: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
   - **CH340**: https://sparks.gogo.co.nz/ch340.html
   - **FTDI**: https://ftdichip.com/drivers/vcp-drivers/

2. **Check USB Cable**:
   - Use a data cable (not charge-only)
   - Try different USB ports
   - Test with a different cable

3. **Check Device Manager** (Windows):
   ```
   Device Manager → Ports (COM & LPT)
   Look for: "Silicon Labs CP210x" or "USB-SERIAL CH340"
   ```

4. **Check Permissions** (Linux/macOS):
   ```bash
   # Linux
   sudo usermod -a -G dialout $USER
   sudo chmod 666 /dev/ttyUSB0
   
   # macOS
   sudo chmod 666 /dev/cu.usbserial-*
   ```

5. **Verify ESP32 is powered**:
   - Check LED on ESP32
   - Try pressing BOOT/EN button

---

## No CSI Data

### Problem: ESP32 connected but no CSI_DATA output

**Symptoms**:
- Serial monitor shows WiFi logs but no CSI_DATA lines
- Detection script waiting forever

**Diagnostic Steps**:

1. **Check Serial Monitor**:
   ```bash
   cd firmware/csi_receiver
   idf.py monitor
   ```
   
   Look for:
   - "WiFi Connected" message
   - "CSI system active" message
   - Any error messages

2. **Verify WiFi Connection**:
   
   **Check credentials** in `firmware/csi_receiver/main/csi_receiver.c`:
   ```c
   #define WIFI_SSID "YourActualSSID"  // Must match exactly
   #define WIFI_PASS "YourPassword"
   ```
   
   **Common mistakes**:
   - Typo in SSID or password
   - Extra spaces
   - Wrong WiFi band (ESP32 only supports 2.4 GHz, not 5 GHz)

3. **Check WiFi Router**:
   - Ensure 2.4 GHz band is enabled
   - Check MAC address filtering (if enabled)
   - Verify WPA2 security (not WPA3 only)
   - Try disabling router firewall temporarily

4. **Reflash Firmware**:
   ```bash
   cd firmware/csi_receiver
   idf.py fullclean
   idf.py build flash monitor
   ```

5. **Check Promiscuous Mode**:
   Verify in code:
   ```c
   esp_wifi_set_promiscuous(true);
   esp_wifi_set_promiscuous_rx_cb(promiscuous_rx_cb);
   ```

**Expected Output**:
```
CSI_DATA: 23 45 67 89 12 34 56 78 ...
CSI_DATA: 21 43 65 87 19 32 54 76 ...
```

---

## Poor Detection Accuracy

### Problem: System detects presence incorrectly

**Symptoms**:
- False positives (detects person when room is empty)
- False negatives (doesn't detect person)
- Unstable readings

**Solutions**:

### 1. Increase Calibration Time

Edit `python/csi_detector.py`:
```python
# In CSIDetectionSystem class
detector.classifier.calibration_time = 100  # Increase from 50

# Or in AdaptiveClassifier.__init__:
def __init__(self, calibration_time=100, ...):  # Changed from 30
```

### 2. Ensure Proper Calibration

**During calibration**:
- Leave room completely empty, OR
- Stay perfectly still (don't move at all)
- Close doors and windows
- Wait for full calibration period

### 3. Optimize ESP32 Placement

**Best practices**:
- Place in center of room
- Elevation: 1-2 meters high
- Away from metal objects
- Clear line of sight
- Not in corners

**Avoid**:
- Near microwave ovens
- Behind thick walls
- In metal enclosures
- Near other ESP32/WiFi devices

### 4. Adjust Thresholds Manually

Edit `python/csi_detector.py` in `AdaptiveClassifier.calibrate()`:

```python
# More sensitive (detects smaller movements)
self.empty_threshold = empty_stats[2] * 1.2  # Default: 1.5
self.presence_threshold = empty_stats[2] * 2.5  # Default: 3.0
self.activity_threshold = empty_stats[2] * 5.0  # Default: 6.0

# Less sensitive (reduces false positives)
self.empty_threshold = empty_stats[2] * 2.0
self.presence_threshold = empty_stats[2] * 4.0
self.activity_threshold = empty_stats[2] * 8.0
```

### 5. Environmental Factors

**Check for**:
- Strong WiFi interference (multiple networks)
- Moving objects (fans, curtains)
- Pets in the room
- Electromagnetic interference

**Solutions**:
- Change WiFi channel on router
- Close windows to reduce interference
- Use wired connections for other devices
- Minimize electronic devices in room

### 6. Increase Sample Window

Edit `python/csi_detector.py`:
```python
# Increase buffers for more stable readings
self.feature_extractor = FeatureExtractor(window_sizes=[30, 70, 150])
# Default: [20, 50, 100]
```

---

## Python Environment Issues

### Problem: "ModuleNotFoundError" or import errors

**Symptoms**:
```
ModuleNotFoundError: No module named 'numpy'
ModuleNotFoundError: No module named 'serial'
```

**Solutions**:

1. **Activate Virtual Environment**:
   ```bash
   # macOS/Linux
   cd python
   source env/bin/activate
   
   # Windows
   cd python
   env\Scripts\activate.bat
   ```

2. **Reinstall Dependencies**:
   ```bash
   pip install -r ../requirements.txt
   ```

3. **Manual Installation**:
   ```bash
   pip install numpy scipy matplotlib pyserial
   ```

4. **Check Python Version**:
   ```bash
   python3 --version  # Should be 3.7+
   ```

### Problem: Matplotlib display issues

**Symptoms**:
- No graphs showing
- "Backend" errors

**Solutions**:

1. **macOS**:
   ```bash
   # Install backend
   pip install pyqt5
   
   # Or use different backend
   export MPLBACKEND=TkAgg
   ```

2. **Linux** (headless):
   ```bash
   # Use non-GUI backend
   export MPLBACKEND=Agg
   ```

3. **Windows**:
   ```cmd
   pip install pyqt5
   ```

---

## Compilation Errors

### Problem: ESP-IDF build fails

**Common Errors**:

#### 1. "ESP-IDF not found"

**Solution**:
```bash
# Install ESP-IDF
cd ~
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh
source export.sh
```

#### 2. "Python 2 not found"

**Solution**:
ESP-IDF v4.4+ uses Python 3:
```bash
# Update ESP-IDF
cd ~/esp-idf
git pull
git checkout v4.4
./install.sh
```

#### 3. "CMake error"

**Solution**:
```bash
# Install CMake
# macOS
brew install cmake

# Linux
sudo apt-get install cmake

# Windows
# Download from https://cmake.org/download/
```

#### 4. Configuration mismatch

**Solution**:
```bash
cd firmware/csi_receiver
idf.py fullclean
rm -rf build sdkconfig
idf.py menuconfig  # Configure as needed
idf.py build
```

---

## Serial Communication Problems

### Problem: Data corrupted or not received

**Symptoms**:
- Garbled output
- Missing CSI_DATA lines
- "UnicodeDecodeError"

**Solutions**:

1. **Check Baud Rate**:
   ```python
   # In run_presence_detection.py
   ser = serial.Serial(port, 115200)  # Must match ESP32
   ```
   
   ESP32 default is 115200.

2. **Increase Serial Buffer**:
   ```python
   ser = serial.Serial(
       port, 
       115200,
       timeout=1,
       write_timeout=1
   )
   ```

3. **Reduce CSI Data Rate**:
   
   Edit `firmware/csi_receiver/main/csi_receiver.c`:
   ```c
   #define CSI_SEND_RATE_MS 200  // Slower (was 100)
   ```

4. **Check USB Hub**:
   - Avoid USB hubs if possible
   - Connect directly to computer
   - Try different USB port

5. **Monitor Buffer Overflow**:
   ```bash
   # Check for overflow errors
   idf.py monitor | grep -i "overflow\|buffer"
   ```

---

## Advanced Debugging

### Enable Debug Mode

**ESP32**:
```c
// In csi_receiver.c, change log level
static const char *TAG = "CSI_PRESENCE_DETECTOR";

// In app_main():
esp_log_level_set("*", ESP_LOG_DEBUG);
```

**Python**:
```python
# In csi_detector.py, uncomment debug line
except Exception as e:
    print(f"Debug - Error: {e}")  # Uncomment this
    pass
```

### Collect Diagnostic Data

```bash
# Save ESP32 logs
idf.py monitor > esp32_log.txt

# Save Python output
python3 run_presence_detection.py > detection_log.txt 2>&1

# Save CSI data for analysis
python3 run_presence_detection.py | tee csi_data_$(date +%Y%m%d_%H%M%S).txt
```

### Test with Known-Good Data

```bash
cd python
python3 presence_det.py  # Offline analysis with sample data
```

---

## Getting More Help

If issues persist:

1. **Check documentation**:
   - README.md
   - ARCHITECTURE.md
   - ESP-IDF documentation

2. **System check**:
   ```bash
   python3 check_system.py
   ```

3. **Monitor ESP32 output**:
   ```bash
   cd firmware/csi_receiver
   idf.py monitor
   ```

4. **Collect information**:
   - ESP32 board type
   - Computer OS and version
   - Python version
   - ESP-IDF version
   - Error messages (full text)
   - Steps to reproduce

---

**Need more help?** Check the GitHub issues or ESP32 forums.
