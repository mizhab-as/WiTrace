#!/usr/bin/env python3

from flask import Flask, render_template, jsonify
import serial
import serial.tools.list_ports
import numpy as np
from collections import deque
import json
import time
import threading
import os
from pattern_detector import PatternDetector

CONFIG = {
    'max_buffer_size': 300,
    'energy_window': 50,
    'baudrate': 115200
}

DEFAULT_THRESHOLDS = {
    'person': 4.64,
    'multi': 5.37
}

class EnergySample:
    def __init__(self, timestamp, energy, variance):
        self.timestamp = timestamp
        self.energy = energy
        self.variance = variance

class SystemState:
    def __init__(self, pattern_detector=None):
        self.lock = threading.Lock()
        self.samples = deque(maxlen=CONFIG['max_buffer_size'])
        self.energy_buffer = deque(maxlen=CONFIG['energy_window'])
        self.variance_window = deque(maxlen=100)
        
        self.is_connected = False
        self.is_calibrated = True
        self.thresholds = DEFAULT_THRESHOLDS.copy()
        self.current_status = "INITIALIZING"
        self.status_color = "#808080"
        
        self.pattern_detector = pattern_detector
        self.detection_confidence = 0.0
        self.detection_scores = {}
        self.error_message = ""
        
        self.load_calibration()
    
    def load_calibration(self):
        try:
            cal_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
            if os.path.exists(cal_file):
                with open(cal_file, 'r') as f:
                    cal = json.load(f)
                    self.thresholds = {
                        'person': cal.get('empty', 4.64),
                        'multi': cal.get('multi', 5.37)
                    }
                    self.is_calibrated = True
                    print(f"✅ Calibration loaded: {self.thresholds}")
        except Exception as e:
            print(f"⚠️ Calibration error: {e}")
    
    def add_energy(self, energy_value):
        with self.lock:
            self.energy_buffer.append(energy_value)
            
            if len(self.energy_buffer) >= CONFIG['energy_window']:
                variance = np.var(list(self.energy_buffer))
                sample = EnergySample(time.time(), energy_value, variance)
                self.samples.append(sample)
                self.variance_window.append(variance)
                self._update_status()
    
    def _update_status(self):
        if len(self.variance_window) < 50:
            self.current_status = "⏳ INITIALIZING"
            self.status_color = "#808080"
            self.detection_confidence = 0.0
            return
        
        if self.pattern_detector:
            try:
                result = self.pattern_detector.detect(list(self.variance_window))
                self.current_status = result['status']
                self.detection_confidence = result['confidence']
                self.detection_scores = result['scores']
                
                color_map = {
                    '🟢 EMPTY ROOM': '#4CAF50',
                    '🔵 PERSON DETECTED': '#2196F3',
                    '🔴 MULTIPLE PEOPLE': '#F44336',
                    'INITIALIZING': '#808080'
                }
                self.status_color = color_map.get(self.current_status, '#808080')
            except Exception as e:
                self.error_message = str(e)
        else:
            self._fallback_status()
    
    def _fallback_status(self):
        if len(self.samples) > 0:
            latest_variance = self.samples[-1].variance
            if latest_variance < self.thresholds['person']:
                self.current_status = "🟢 EMPTY ROOM"
                self.status_color = "#4CAF50"
            elif latest_variance < self.thresholds['multi']:
                self.current_status = "🔵 PERSON DETECTED"
                self.status_color = "#2196F3"
            else:
                self.current_status = "🔴 MULTIPLE PEOPLE"
                self.status_color = "#F44336"
    
    def get_data(self):
        with self.lock:
            base_time = self.samples[0].timestamp if self.samples else time.time()
            
            return {
                'status': self.current_status,
                'status_color': self.status_color,
                'is_connected': self.is_connected,
                'is_calibrated': self.is_calibrated,
                'thresholds': self.thresholds,
                'timestamps': [s.timestamp - base_time for s in self.samples],
                'energy': [s.energy for s in self.samples],
                'variance': [s.variance for s in self.samples],
                'detection_confidence': round(self.detection_confidence, 2),
                'detection_scores': {k: round(v, 2) for k, v in self.detection_scores.items()},
                'error': self.error_message
            }

pattern_detector = PatternDetector()
print(f"✅ Pattern detector ready with {len(pattern_detector.patterns)} patterns")

state = SystemState(pattern_detector=pattern_detector)

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(x in port.description.lower() for x in ['cp210', 'ch340', 'usb serial', 'uart']):
            return port.device
    return ports[0].device if ports else None

serial_port = find_esp32_port()

def read_serial_worker():
    global serial_port
    ser = None
    
    try:
        while True:
            try:
                if ser is None or not ser.is_open:
                    if serial_port:
                        ser = serial.Serial(serial_port, CONFIG['baudrate'], timeout=1)
                        state.is_connected = True
                        print(f"✅ Connected to {serial_port}")
                    else:
                        time.sleep(1)
                        continue
                
                if ser.is_open:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                energy = np.mean(np.abs(values))
                                state.add_energy(energy)
                        except (ValueError, IndexError):
                            pass
            except (serial.SerialException, OSError) as e:
                state.is_connected = False
                if ser:
                    ser.close()
                    ser = None
                print(f"⚠️ Serial error: {e}")
                time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        if ser and ser.is_open:
            ser.close()

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('monitor.html')

@app.route('/api/data')
def api_data():
    return jsonify(state.get_data())

@app.route('/api/status')
def api_status():
    data = state.get_data()
    return jsonify({
        'status': data['status'],
        'status_color': data['status_color'],
        'is_connected': data['is_connected'],
        'is_calibrated': data['is_calibrated']
    })

if __name__ == '__main__':
    serial_thread = threading.Thread(target=read_serial_worker, daemon=True)
    serial_thread.start()
    
    print("\n" + "="*60)
    print("  WiFi CSI Presence Detection")
    print("="*60)
    print(f"📡 Port: {serial_port}")
    print("🌐 Server: http://localhost:8080")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8080, debug=False)
