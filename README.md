 <div align="center">

# 📡 WiTrace

### WiFi CSI‑Based Human Presence and Occupancy Detection

[![License](https://img.shields.io/github/license/jeevanjoseph03/WiTrace)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v5.x-red?logo=espressif)](https://docs.espressif.com/projects/esp-idf/en/latest/)
[![Platform](https://img.shields.io/badge/Hardware-ESP32-informational)](https://www.espressif.com/en/products/socs/esp32)

> A non-invasive, privacy-preserving indoor presence and occupancy detection system leveraging **WiFi Channel State Information (CSI)** — no cameras, no sensors, just WiFi signals.

</div>

---

## 🧠 Overview

**WiTrace** exploits minute disturbances in WiFi Channel State Information (CSI) caused by human movement to detect and classify room occupancy states. By analyzing how the wireless multipath signal changes over time, the system can differentiate between:

- 🟢 **Empty Room** — No person present
- 🟡 **Person Present (Still)** — Stationary occupant
- 🟠 **Person Walking** — Active movement detected
- 🔴 **Multiple People / High Activity** — Dense occupancy or high motion

The system combines **ESP32 firmware** for raw CSI capture with **Python-based signal processing** for feature extraction, classification, and visualization — all without any visual or acoustic surveillance.

---

## ✨ Features

- 📶 **Raw WiFi CSI Collection** via ESP32 (ESP-IDF firmware)
- 🧹 **Signal Preprocessing** — Static component removal, Gaussian smoothing
- 📊 **Energy Analysis** — Per-frame mean CSI energy across scenarios
- 🎯 **Motion Path Estimation** — Centroid-based subcarrier tracking
- 🧮 **Statistical Presence Classifier** — Z-score normalized decision logic
- 🌡️ **CSI Heatmaps** — Normalized amplitude visualization across subcarriers
- 📉 **Scatter & Line Plots** — Multi-scenario comparison dashboards
- 🔒 **Privacy-First** — Entirely passive, RF-based, no cameras or microphones

---

## 🗂️ Repository Structure

```
WiTrace/
├── firmware/
│   └── csi_receiver/          # ESP-IDF project for ESP32 CSI capture
│       ├── main/              # Main application source (C)
│       ├── CMakeLists.txt     # ESP-IDF build configuration
│       └── sdkconfig          # ESP-IDF SDK configuration
│
├── python/
│   ├── process_csi.py         # CSI energy analysis & motion path visualization
│   ├── presence_det.py        # Feature extraction & statistical presence classifier
│   └── backup_wall.py        # Extended analysis with through-wall scenario
│
├── data/                      # Raw CSI dataset files (.txt)
│   ├── empty.txt              # Baseline — empty room
│   ├── occupied.txt           # Stationary person
│   ├── walking.txt            # Walking person
│   ├── multi_occ.txt          # Multiple occupants
│   └── wall.txt               # Person behind wall
│
└── docs/                      # Documentation assets
```

---

## 🛠️ Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Hardware    | ESP32 (Wi-Fi CSI capable)           |
| Firmware    | ESP-IDF (C), CMake                  |
| Processing  | Python 3, NumPy, SciPy              |
| Visualization | Matplotlib                        |
| Classification | Statistical Z-score thresholding |

---

## 🚀 Getting Started

### Prerequisites

#### Firmware
- [ESP-IDF v5.x](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- ESP32 development board with CSI support

#### Python
- Python 3.8+
- Install dependencies:

```bash
pip install numpy scipy matplotlib
```

---

### 1️⃣ Flash the Firmware (ESP32)

```bash
cd firmware/csi_receiver
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

> The firmware captures CSI frames and prints them to serial in the format:
> ```
> CSI_DATA: <subcarrier values...>
> ```

Redirect the serial output to a `.txt` file to create your dataset:

```bash
idf.py -p /dev/ttyUSB0 monitor > ../data/empty.txt
```

---

### 2️⃣ Run CSI Processing & Visualization

```bash
cd python
python process_csi.py
```

This script will:
- Load the CSI datasets (`empty`, `occupied`, `walking`, `multi_occ`)
- Generate **energy comparison** line plots
- Plot **individual energy graphs** per scenario
- Render **motion path comparison** across all datasets
- Display **energy scatter plots** for all scenarios

---

### 3️⃣ Run Presence Detection

```bash
cd python
python presence_det.py
```

This script will:
- Extract features: **mean energy**, **temporal variance**, **motion centroid variance**
- Classify each dataset using a **Z-score normalized statistical classifier**
- Print a results card for each scenario:

```
==================================================
        CSI PRESENCE DETECTION RESULTS
==================================================

--------------------------------------------------
 SCENARIO: Walking
--------------------------------------------------
 Mean CSI Energy      : 42.87
 Temporal Variance    : 198.34
 Motion Variance      : 56.21
 Person Detection     : PERSON WALKING
 Confidence Level     : High
--------------------------------------------------
```

---

## 📐 How It Works

```
┌─────────────┐     WiFi CSI Frames     ┌────────────────────┐
│  ESP32 Node │ ───────────────────────▶│  Serial / Log File │
│  (Transmit  │                         │  (Raw CSI Data)    │
│   + Receive)│                         └────────┬───────────┘
└─────────────┘                                  │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  Preprocessing         │
                                    │  • Remove static mean  │
                                    │  • Compute magnitude   │
                                    │  • Gaussian smoothing  │
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  Feature Extraction    │
                                    │  • Mean CSI energy     │
                                    │  • Temporal variance   │
                                    │  • Motion centroid     │
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  Z-Score Classifier    │
                                    │  vs. Empty Baseline    │
                                    └────────────┬───────────┘
                                                 │
                                                 ▼
                                    ┌────────────────────────┐
                                    │  Presence Decision     │
                                    │  + Confidence Level    │
                                    └────────────────────────┘
```

### Detection Thresholds

| Z-Score (Motion Variance) | Classification                   | Confidence   |
|---------------------------|----------------------------------|--------------|
| `< 0.5`                   | No Person Detected               | High         |
| `0.5 – 3.0`               | Person Present (Still)           | Medium-High  |
| `3.0 – 8.0`               | Person Walking                   | High         |
| `> 8.0`                   | Multiple People / High Activity  | Very High    |

---

## 📁 Data Format

CSI data files are plain-text logs captured from the ESP32 serial output. Each line follows this format:

```
CSI_DATA: <int> <int> <int> ... <int>
```

Each integer represents the amplitude of one WiFi subcarrier at a given time frame. Multiple lines = multiple time frames.

---

## 🤝 Contributing

Contributions are welcome! To contribute:

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is open-source. Please refer to the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Authors

**WiTrace** was collaboratively developed by:

- [Mizhab](https://github.com/mizhab-as)
- [Jeevan Joseph](https://github.com/jeevanjoseph03)
- [Irfan](https://github.com/Irfan-34)
- [Muzammil](https://github.com/muzml)

---

## 🙏 Acknowledgements

- [Espressif ESP-IDF](https://github.com/espressif/esp-idf) for the WiFi CSI API  
- Research inspiration from WiFi-based passive sensing literature

---
---

<div align="center">
  <sub>Built with 📡 WiFi signals and 🐍 Python</sub>
</div>

