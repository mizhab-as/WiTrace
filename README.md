# WiFi CSI Human Presence Detection System

Real-time human presence detection using WiFi Channel State Information (CSI) from ESP32.

![System Overview](docs/system-overview.png)

## 🎯 Overview

This project uses **WiFi CSI** (Channel State Information) to detect human presence in a room without cameras or wearable devices. The system consists of:

- **ESP32 Module**: Captures WiFi CSI data from the environment
- **Python Detector**: Analyzes CSI patterns to detect human presence in real-time

The system can detect:
- ✅ Empty room
- 👤 Person present (stationary)
- 🚶 Person moving/walking
- 👥 Multiple people or high activity

## 📋 Requirements

### Hardware
- **ESP32 Development Board** (any variant with WiFi)
- USB cable for ESP32 connection
- WiFi Access Point (router)

### Software
- **Python 3.7+** (with pip)
- **ESP-IDF** (for compiling firmware) - v4.4 or later
- Libraries: NumPy, SciPy, Matplotlib, PySerial (auto-installed)

### Operating Systems
- ✅ macOS
- ✅ Linux
- ✅ Windows

## 🚀 Quick Start

### 1️⃣ Setup Environment

**On macOS/Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**On Windows:**
```cmd
setup.bat
```

This will:
- Create Python virtual environment
- Install all dependencies
- Configure the project

### 2️⃣ Configure WiFi Credentials

Edit the ESP32 firmware with your WiFi credentials:

```c
// File: firmware/csi_receiver/main/csi_receiver.c
#define WIFI_SSID "YourWiFiName"
#define WIFI_PASS "YourWiFiPassword"
```

### 3️⃣ Flash ESP32 Firmware

```bash
cd firmware/csi_receiver
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Replace `/dev/ttyUSB0` with your ESP32's serial port:
- macOS: `/dev/cu.usbserial-*` or `/dev/cu.SLAB_USBtoUART`
- Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
- Windows: `COM3` or similar

### 4️⃣ Run Presence Detection

```bash
cd python
source env/bin/activate  # On Windows: env\Scripts\activate.bat
python3 run_presence_detection.py
```

The system will:
1. Auto-detect your ESP32
2. Connect and receive CSI data
3. Calibrate (stay still for 10 seconds)
4. Start real-time presence detection

## 📊 Usage Modes

### Advanced Detector Mode (Recommended)
```bash
python3 run_presence_detection.py detector
```

Features:
- 🎯 Automatic calibration
- 📈 Multi-graph visualization
- 🎨 Color-coded status display
- 📊 Real-time statistics

### Simple Live Plot Mode
```bash
python3 run_presence_detection.py simple
```

Features:
- 📉 Basic live plotting
- ⚡ Lightweight and fast
- 📊 Simple variance-based detection

## 🏗️ Project Structure

```
wifi_csi_imaging/
│
├── firmware/
│   └── csi_receiver/          # ESP32 firmware
│       └── main/
│           └── csi_receiver.c # CSI data capture code
│
├── python/
│   ├── run_presence_detection.py  # Main runner script ⭐
│   ├── csi_detector.py            # Advanced detection system
│   ├── live_plot.py               # Simple live plotter
│   ├── presence_det.py            # Offline analysis
│   └── env/                       # Python virtual environment
│
├── data/                      # Sample CSI datasets
│   ├── empty.txt
│   ├── occupied.txt
│   ├── walking.txt
│   └── multi_occ.txt
│
├── requirements.txt           # Python dependencies
├── setup.sh                   # Setup script (Unix)
├── setup.bat                  # Setup script (Windows)
└── README.md                  # This file
```

## 🔬 How It Works

### WiFi CSI (Channel State Information)

CSI measures how WiFi signals propagate through the environment. When a person moves or is present in a room, they affect the wireless signal patterns, which can be detected and analyzed.

### Detection Pipeline

1. **ESP32** captures CSI data from WiFi packets
2. **Serial** transfers data to Python in real-time
3. **Preprocessing** removes noise and spikes
4. **Feature Extraction** computes statistical features:
   - Variance (motion indicator)
   - Rate of change (activity level)
   - Frequency domain features
5. **Classification** determines presence status:
   - Empty room (low variance)
   - Person present (medium variance)
   - Person moving (high variance + high rate of change)
   - Multiple people (very high variance)

### Calibration

The system automatically calibrates to your environment during the first 10 seconds. This establishes a baseline for "empty room" conditions.

## 🛠️ Customization

### Adjust Detection Sensitivity

Edit `python/csi_detector.py`:

```python
class AdaptiveClassifier:
    def __init__(self, calibration_time=30, adaptation_rate=0.95):
        self.calibration_time = 50  # Increase for more stable baseline
```

### Change CSI Data Rate

Edit `firmware/csi_receiver/main/csi_receiver.c`:

```c
#define CSI_SEND_RATE_MS 100  // Milliseconds (100ms = 10 Hz)
```

Lower values = more data, but may overload serial connection.

### Customize Visualization

Edit plot settings in `python/csi_detector.py`:

```python
def setup_visualization(self):
    # Modify figure size, colors, layout, etc.
    self.fig, axes = plt.subplots(2, 2, figsize=(14, 8))
```

## 📈 Testing with Recorded Data

Test the detector without ESP32 using recorded datasets:

```bash
cd python
python3 test_with_data.py
```

Or analyze specific scenarios:

```bash
python3 presence_det.py
```

## 🐛 Troubleshooting

### No CSI data appearing

1. **Check WiFi connection**: Ensure ESP32 connects to your WiFi
   - Monitor serial output for "WiFi Connected" message
   - Verify SSID and password in firmware

2. **Check power saving**: Ensure power saving is disabled
   - Already configured in the provided firmware

3. **Check promiscuous mode**: Must be enabled
   - Already enabled in the provided firmware

### ESP32 not detected

1. **Install USB drivers**:
   - **CP210x**: [Silicon Labs drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   - **CH340**: [CH340 drivers](https://sparks.gogo.co.nz/ch340.html)

2. **Check permissions** (Linux/macOS):
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   ```

3. **Manual port selection**:
   ```bash
   python3 run_presence_detection.py /dev/ttyUSB0
   ```

### Poor detection accuracy

1. **Increase calibration time**: Edit `csi_detector.py`:
   ```python
   detector.classifier.calibration_time = 100
   ```

2. **Reduce environmental noise**:
   - Close doors/windows
   - Minimize WiFi interference
   - Keep ESP32 in central location

3. **Collect training data**:
   - Record empty room for 30 seconds
   - Adjust thresholds based on your environment

## 📚 Technical Details

### CSI Configuration

```c
wifi_csi_config_t csi_config = {
    .lltf_en = true,           // Legacy LTF
    .htltf_en = true,          // HT LTF
    .stbc_htltf2_en = true,    // STBC HT-LTF2
    .ltf_merge_en = true,      // Merge LTF data
    .channel_filter_en = false, // No channel filter
    .manu_scale = false,       // Auto scaling
    .shift = false             // No bit shifting
};
```

### Feature Engineering

The system extracts multiple features from CSI amplitude:
- **Statistical**: mean, variance, standard deviation, min, max
- **Temporal**: rate of change, moving averages
- **Frequency**: FFT peaks, frequency domain energy

### Adaptive Classification

The classifier adapts to environmental changes over time using:
- Dynamic threshold adjustment
- Moving average baseline updates
- Outlier removal and spike filtering

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Machine learning models (SVM, Random Forest, Neural Networks)
- Multi-room detection
- Person counting accuracy
- Mobile app integration
- Web dashboard

## 📄 License

MIT License - see LICENSE file for details

## 🔗 References

- [ESP32 CSI Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi.html#wi-fi-channel-state-information)
- [WiFi Sensing Research Papers](https://www.google.com/search?q=wifi+sensing+csi+human+detection)

## 📧 Support

For issues and questions:
1. Check the Troubleshooting section
2. Review ESP32 serial monitor output
3. Open an issue on GitHub

---

**Made with ❤️ using ESP32 and Python**

*Last updated: February 2026*
