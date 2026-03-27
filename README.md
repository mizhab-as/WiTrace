<div align="center">

# 📡 WiTrace

### WiFi CSI‑Based Human Presence and Occupancy Detection

[![License](https://img.shields.io/github/license/jeevanjoseph03/WiTrace)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v5.x-red?logo=espressif)](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
[![Platform](https://img.shields.io/badge/Hardware-ESP32-informational)](https://www.espressif.com/en/products/socs/esp32)

> A non-invasive, privacy-preserving indoor presence and occupancy detection system leveraging **WiFi Channel State Information (CSI)** — no cameras, no sensors, just WiFi signals.

</div>

---

## 🧠 Overview

**WiTrace** exploits minute disturbances in WiFi Channel State Information (CSI) caused by human movement to detect and classify room occupancy states. By analyzing how the wireless multipath signal changes over time, the system can differentiate between:

- 🟢 **Empty Room** — No person present
- 🔵 **Person Detected** — Occupant present
- 🔴 **Multiple People** — High activity / multiple occupants


The system combines **ESP32 firmware** for raw CSI capture with a **Python live dashboard + detector** for feature extraction, classification, and visualization — all without any visual or acoustic surveillance.

---

## ✨ Features (Updated)

- 📶 **Raw WiFi CSI collection** via ESP32 (ESP-IDF firmware)
- 🧹 **Signal preprocessing** (static removal, smoothing) + **energy extraction**
- 🧠 **Presence classifier** with a more stable **ensemble** over multiple recent windows
- 🧾 **CSI_META + CSI_DATA pairing** supported (better logging + consistent analysis)
- 🧬 **Baseline template matching (5s)**: live window matched against saved room baselines
- 📈 Live dashboard improvements:
  - Larger real-time CSI capture view
  - **Detection diagnostics**: binary state, agreement, margin, windows, method
  - **Link/Data health**: RSSI/SNR stats, RX error ratio, MCS/rate, frame accept/reject counts
- 🔒 **Privacy-first** — passive RF sensing; no cameras/mics

---

## 🗂️ Repository Structure (Updated)

```text
WiTrace/
├── firmware/
│   └── csi_receiver/              # ESP-IDF project for ESP32 CSI capture
│
├── python/
│   ├── app.py                     # Live dashboard backend + serial ingestion + detection
│   ├── pattern_detector.py         # Pattern detection + baseline template matching
│   ├── collect_raw_csi.py          # Serial logger (pairs CSI_META + CSI_DATA when possible)
│   └── templates/
│       └── monitor.html            # Dashboard UI
│
├── data/                          # Example CSI datasets (.txt)
│   ├── empty.txt
│   ├── occupied.txt
│   └── multi_occ.txt
│
└── RUN_ONE_TERMINAL.sh             # One-command runner for venv + dashboard (optional)
```

> Note: `firmware/csi_receiver/build/*` contains local build outputs and is not required to understand the project.

---

## 🛠️ Tech Stack

| Layer | Technology |
|------|------------|
| Hardware | ESP32 (Wi-Fi CSI capable) |
| Firmware | ESP-IDF (C), CMake |
| Processing / Backend | Python 3.8+ (NumPy) |
| Dashboard | Web UI served from `python/app.py` + HTML template |
| Detection | Weighted similarity + multi-window ensemble + baseline template matching |

---

## 🚀 Getting Started

### Prerequisites

#### Firmware
- [ESP-IDF v5.x](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- ESP32 development board with CSI support

#### Python
- Python 3.8+
- Recommended: use a virtual environment (`.venv`) at repo root

Example:
```bash
python -m venv .venv
source .venv/bin/activate
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

The firmware prints CSI in two-line pairs when available:

```text
CSI_META: ts=... rssi=... noise_floor=... mcs=... rate=... len=... rx_state=... tx_mac=...
CSI_DATA: <int> <int> <int> ... <int>
```

---

### 2️⃣ Run the Live Dashboard / Detector

#### Option A — Run with the one-terminal script (recommended)
This will:
- free the serial port (kills any process holding it),
- activate `./.venv`,
- start the dashboard backend (`python/app.py`).

```bash
./RUN_ONE_TERMINAL.sh
```

If you want it to flash firmware first:

```bash
./RUN_ONE_TERMINAL.sh --flash
```

You can override the serial port using:

```bash
ESP_PORT=/dev/ttyUSB0 ./RUN_ONE_TERMINAL.sh
```

#### Option B — Manual run
```bash
source .venv/bin/activate
cd python
python app.py
```

Then open the dashboard in your browser (the URL/port is printed in the terminal by `app.py`).

---

### 3️⃣ Collect Raw CSI to a File (paired META+DATA)

```bash
cd python
python collect_raw_csi.py
```

This collector attempts to write CSI as ordered pairs (`CSI_META` then `CSI_DATA`) when both arrive within a short pairing window; otherwise it still logs what it receives.

---

## 🧪 Detection Notes (New Behavior)

- The detector now uses an **ensemble of recent windows** to improve stability.
- The dashboard reports:
  - `binary_state` (empty vs not_empty)
  - `agreement` across ensemble windows
  - `margin` (separation between top classes)
  - method name (e.g., `weighted_mahalanobis_ensemble`)
- A separate **5-second baseline matching** compares the last live window against saved templates (empty/occupied/multi) and can drive the final displayed room state.

---

## 🤝 Contributing

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

<div align="center">
  <sub>Built with 📡 WiFi signals and 🐍 Python</sub>
</div>
