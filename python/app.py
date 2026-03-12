#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request
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
    'baudrate': 115200,
    'detection_window_seconds': 5.0,     # Analyze this many seconds of CSI data
    'detection_update_interval': 5.0,     # Update detection every N seconds
    'min_frames_for_detection': 50,       # Minimum frames needed in window
    'esp_live_timeout_seconds': 2.5,      # Treat ESP as disconnected if no CSI arrives recently
    'data_timeout_seconds': 15.0,         # Reconnect if no data for 15 seconds (was 5)
    'serial_read_timeout': 3,              # Serial port read timeout in seconds
}

DEFAULT_THRESHOLDS = {
    'person': 9.0,    # INVERTED VARIANCE: Lower threshold for occupied state
    'multi': 11.0     # Higher threshold for multiple people
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
        self.signature_window = deque(maxlen=150)
        self.frame_energy_window = deque(maxlen=300)
        self.score_history = deque(maxlen=CONFIG['max_buffer_size'])
        self.raw_csi_lines = deque(maxlen=40)
        self.last_csi_line = ''
        self.last_csi_values_count = 0
        self.last_csi_at = 0.0
        self.stable_state = "⏳ INITIALIZING"
        self.pending_state = None
        self.pending_count = 0
        self.hysteresis_needed = {
            '🟢 EMPTY ROOM': 2,
            '🔵 PERSON DETECTED': 2,
            '🔴 MULTIPLE PEOPLE': 2,
            '🟡 UNCERTAIN': 2,
        }
        
        # Window-based periodic detection (5-second intervals)
        self.last_detection_time = 0.0
        self.detection_in_progress = False
        self.frames_since_last_detection = 0
        self.detection_history = deque(maxlen=60)  # Store up to 60 detection windows (5 min)
        self.detection_window_start_time = 0.0
        
        self.is_connected = False
        self.is_calibrated = True
        self.thresholds = DEFAULT_THRESHOLDS.copy()
        self.current_status = "INITIALIZING"
        self.status_color = "#808080"
        
        self.pattern_detector = pattern_detector
        self.detection_confidence = 0.0
        self.detection_scores = {}
        self.detection_margin = 0.0
        self.is_uncertain = False
        self.binary_margin = 0.0
        self.binary_scores = {'empty': 0.0, 'not_empty': 0.0}
        self.error_message = ""

        self.calibration_active = False
        self.calibration_stage = 'idle'
        self.calibration_duration = 60
        self.calibration_empty_duration = 60
        self.calibration_occupied_duration = 60
        self.calibration_multiple_duration = 60
        self.calibration_min_frames = 80
        self.calibration_alpha = 0.9
        self.calibration_started_at = 0.0
        self.calibration_remaining = 0.0
        self.calibration_message = 'Not started'
        self.calibration_empty_signatures = []
        self.calibration_empty_energies = []
        self.calibration_occupied_signatures = []
        self.calibration_occupied_energies = []
        self.calibration_multiple_signatures = []
        self.calibration_multiple_energies = []
        self.live_calibration_applied = False
        
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

    def add_csi_frame(self, values):
        if not values:
            return

        with self.lock:
            energy = np.mean(np.abs(values))
            self.energy_buffer.append(energy)

            if len(self.energy_buffer) >= CONFIG['energy_window']:
                variance = np.var(list(self.energy_buffer))
                sample = EnergySample(time.time(), energy, variance)
                self.samples.append(sample)
                self.variance_window.append(variance)

            if self.pattern_detector:
                signature = self.pattern_detector.frame_signature(values)
                if signature is not None:
                    self.signature_window.append(signature)
                    self.frame_energy_window.append(float(energy))
                    self._update_live_calibration(signature, float(energy))
                    self.frames_since_last_detection += 1

            # Only run detection periodically on accumulated window
            self._periodic_detection_update()

    def add_raw_csi_line(self, line, values_count):
        with self.lock:
            self.last_csi_line = line
            self.last_csi_values_count = int(values_count)
            self.last_csi_at = time.time()
            self.raw_csi_lines.append({
                'ts': self.last_csi_at,
                'line': line,
                'values_count': int(values_count),
            })
    
    def _periodic_detection_update(self):
        """Run pattern detection periodically on accumulated CSI window (every 5 seconds)."""
        current_time = time.time()
        
        # Check if it's time to run detection (5-second interval)
        time_since_last = current_time - self.last_detection_time
        if time_since_last < CONFIG['detection_update_interval']:
            return
        
        # Check if we have enough data
        if len(self.samples) < CONFIG['min_frames_for_detection']:
            self.current_status = "⏳ INITIALIZING"
            self.stable_state = self.current_status
            self.status_color = "#808080"
            self.detection_confidence = 0.0
            self.last_detection_time = current_time  # Update timer even during init
            return
        
        if not self.pattern_detector:
            self._fallback_status()
            return
        
        # Get window of CSI data (last N seconds)
        window_seconds = CONFIG['detection_window_seconds']
        cutoff_time = current_time - window_seconds
        
        # Filter signatures and energies to only include recent window
        windowed_sigs = []
        windowed_energies = []
        
        # Get timestamps for signature window (approximate based on frame rate)
        if len(self.signature_window) > 0 and len(self.frame_energy_window) > 0:
            # Assume roughly constant frame rate, work backwards from current time
            frames_in_window = min(len(self.signature_window), self.frames_since_last_detection)
            windowed_sigs = list(self.signature_window)[-frames_in_window:] if frames_in_window > 0 else list(self.signature_window)
            windowed_energies = list(self.frame_energy_window)[-frames_in_window:] if frames_in_window > 0 else list(self.frame_energy_window)
        
        if len(windowed_sigs) < CONFIG['min_frames_for_detection']:
            # Not enough frames in window yet
            self.last_detection_time = current_time  # Update timer anyway
            return
        
        try:
            # Run detection on the accumulated window (matching raw CSI data with reference patterns)
            result = self.pattern_detector.detect(
                windowed_sigs,
                windowed_energies
            )
            
            self.detection_confidence = result['confidence']
            self.detection_scores = result['scores']
            self.detection_margin = result.get('margin', 0.0)
            self.is_uncertain = result.get('is_uncertain', False)
            self.binary_margin = result.get('binary_margin', 0.0)
            self.binary_scores = result.get('binary_scores', {'empty': 0.0, 'not_empty': 0.0})
            
            state_name = result.get('state')
            if state_name == 'empty':
                new_state = '🟢 EMPTY ROOM'
            elif state_name == 'occupied':
                new_state = '🔵 PERSON DETECTED'
            elif state_name == 'multi':
                new_state = '🔴 MULTIPLE PEOPLE'
            else:
                new_state = '🟢 EMPTY ROOM'  # Default to empty if unknown
            
            # Update state based on window analysis
            self.stable_state = new_state
            self.current_status = new_state
            
            # Update color
            color_map = {
                '🟢 EMPTY ROOM': '#4CAF50',
                '🔵 PERSON DETECTED': '#2196F3',
                '🔴 MULTIPLE PEOPLE': '#F44336',
                '⏳ INITIALIZING': '#808080'
            }
            self.status_color = color_map.get(self.current_status, '#808080')
            
            # Log detection result with 5-second window timestamp
            detection_window_entry = {
                'timestamp': current_time,
                'window_index': len(self.detection_history),
                'seconds_ago': 0,
                'empty': self.detection_scores.get('empty', 0.0),
                'occupied': self.detection_scores.get('occupied', 0.0),
                'multi': self.detection_scores.get('multi', 0.0),
                'not_empty': max(self.detection_scores.get('occupied', 0.0), self.detection_scores.get('multi', 0.0)),
                'confidence': self.detection_confidence,
                'margin': self.detection_margin,
                'state': state_name,
                'frames_analyzed': len(windowed_sigs),
            }
            
            # Store in both score_history (for backward compatibility) and detection_history (for new time-based display)
            self.score_history.append(detection_window_entry)
            self.detection_history.append(detection_window_entry)
            
            # Update detection window tracking
            self.last_detection_time = current_time
            self.detection_window_start_time = current_time
            self.frames_since_last_detection = 0
            
        except Exception as e:
            self.error_message = str(e)
            print(f"❌ Detection error: {e}")
            self.last_detection_time = current_time  # Still update timer on error

    def _apply_hysteresis(self, candidate_state):
        if self.stable_state == "⏳ INITIALIZING":
            self.stable_state = candidate_state
            self.pending_state = None
            self.pending_count = 0
            return

        if candidate_state == self.stable_state:
            self.pending_state = None
            self.pending_count = 0
            return

        if self.pending_state != candidate_state:
            self.pending_state = candidate_state
            self.pending_count = 1
        else:
            self.pending_count += 1

        needed = self.hysteresis_needed.get(candidate_state, 5)
        if self.pending_count >= needed:
            self.stable_state = candidate_state
            self.pending_state = None
            self.pending_count = 0
    
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

    def _has_recent_csi(self):
        if not self.is_connected or self.last_csi_at <= 0:
            return False
        return (time.time() - self.last_csi_at) <= CONFIG['esp_live_timeout_seconds']
    
    def get_data(self):
        with self.lock:
            base_time = self.samples[0].timestamp if self.samples else time.time()
            esp_streaming = self._has_recent_csi()
            
            return {
                'status': self.current_status,
                'status_color': self.status_color,
                'is_connected': bool(esp_streaming),
                'serial_connected': bool(self.is_connected),
                'is_calibrated': bool(self.is_calibrated),
                'thresholds': self.thresholds,
                'timestamps': [float(s.timestamp - base_time) for s in self.samples],
                'energy': [float(s.energy) for s in self.samples],
                'variance': [float(s.variance) for s in self.samples],
                'detection_confidence': float(round(self.detection_confidence, 2)),
                'detection_scores': {k: float(round(v, 2)) for k, v in self.detection_scores.items()},
                'detection_margin': float(round(self.detection_margin, 2)),
                'is_uncertain': bool(self.is_uncertain),
                'binary_margin': float(round(self.binary_margin, 2)),
                'binary_scores': {
                    'empty': float(round(self.binary_scores.get('empty', 0.0), 2)),
                    'not_empty': float(round(self.binary_scores.get('not_empty', 0.0), 2)),
                },
                'window_info': {
                    'window_seconds': float(CONFIG['detection_window_seconds']),
                    'update_interval': float(CONFIG['detection_update_interval']),
                    'frames_since_last': int(self.frames_since_last_detection),
                    'time_until_next': float(max(0, CONFIG['detection_update_interval'] - (time.time() - self.last_detection_time))),
                    'last_detection_ago': float(time.time() - self.last_detection_time) if self.last_detection_time > 0 else 0.0,
                },
                'score_history': [
                    {
                        'timestamp': float(p.get('timestamp', 0.0)),
                        'seconds_ago': float(time.time() - p.get('timestamp', 0.0)),
                        'window_index': int(p.get('window_index', 0)),
                        'empty': float(p.get('empty', 0.0)),
                        'occupied': float(p.get('occupied', 0.0)),
                        'multi': float(p.get('multi', 0.0)),
                        'not_empty': float(p.get('not_empty', 0.0)),
                        'confidence': float(p.get('confidence', 0.0)),
                        'margin': float(p.get('margin', 0.0)),
                        'state': p.get('state', 'unknown'),
                        'frames_analyzed': int(p.get('frames_analyzed', 0)),
                    }
                    for p in self.score_history
                ],
                'calibration': {
                    'active': bool(self.calibration_active),
                    'stage': self.calibration_stage,
                    'remaining': float(max(0.0, self.calibration_remaining)),
                    'duration': int(self.calibration_duration),
                    'empty_duration': int(self.calibration_empty_duration),
                    'occupied_duration': int(self.calibration_occupied_duration),
                    'multiple_duration': int(self.calibration_multiple_duration),
                    'min_frames': int(self.calibration_min_frames),
                    'alpha': float(self.calibration_alpha),
                    'empty_frames_collected': int(len(self.calibration_empty_signatures)),
                    'occupied_frames_collected': int(len(self.calibration_occupied_signatures)),
                    'multiple_frames_collected': int(len(self.calibration_multiple_signatures)),
                    'message': self.calibration_message,
                    'live_applied': bool(self.live_calibration_applied),
                },
                'esp_live': {
                    'last_csi_line': self.last_csi_line,
                    'last_csi_values_count': int(self.last_csi_values_count),
                    'last_csi_at': float(self.last_csi_at),
                    'recent_lines': [
                        {
                            'ts': float(item.get('ts', 0.0)),
                            'line': item.get('line', ''),
                            'values_count': int(item.get('values_count', 0)),
                        }
                        for item in self.raw_csi_lines
                    ],
                },
                'error': self.error_message
            }

    def start_live_calibration(self, empty_duration=60, occupied_duration=60, multiple_duration=60, min_frames=80, alpha=0.9):
        with self.lock:
            self.calibration_empty_duration = max(20, int(empty_duration))
            self.calibration_occupied_duration = max(20, int(occupied_duration))
            self.calibration_multiple_duration = max(20, int(multiple_duration))
            self.calibration_duration = self.calibration_empty_duration
            self.calibration_min_frames = max(20, int(min_frames))
            self.calibration_alpha = float(min(0.98, max(0.50, alpha)))
            self.calibration_stage = 'empty'
            self.calibration_active = True
            self.calibration_started_at = time.time()
            self.calibration_remaining = float(self.calibration_duration)
            self.calibration_message = f'Stage 1/3: Keep room EMPTY ({self.calibration_empty_duration}s)'
            self.calibration_empty_signatures = []
            self.calibration_empty_energies = []
            self.calibration_occupied_signatures = []
            self.calibration_occupied_energies = []
            self.calibration_multiple_signatures = []
            self.calibration_multiple_energies = []
            self.live_calibration_applied = False
            return True, 'Calibration started: empty stage'

    def stop_live_calibration(self):
        with self.lock:
            self.calibration_active = False
            self.calibration_stage = 'idle'
            self.calibration_remaining = 0.0
            self.calibration_message = 'Calibration stopped by user'
            return True, self.calibration_message

    def _update_live_calibration(self, signature, energy):
        if not self.calibration_active:
            return

        now = time.time()
        elapsed = now - self.calibration_started_at
        self.calibration_remaining = float(self.calibration_duration - elapsed)

        if self.calibration_stage == 'empty':
            self.calibration_empty_signatures.append(signature)
            self.calibration_empty_energies.append(float(energy))
            if elapsed >= self.calibration_duration:
                self.calibration_stage = 'occupied'
                self.calibration_duration = self.calibration_occupied_duration
                self.calibration_started_at = now
                self.calibration_remaining = float(self.calibration_duration)
                self.calibration_message = f'Stage 2/3: One person in room ({self.calibration_occupied_duration}s)'
            return

        if self.calibration_stage == 'occupied':
            self.calibration_occupied_signatures.append(signature)
            self.calibration_occupied_energies.append(float(energy))
            if elapsed >= self.calibration_duration:
                self.calibration_stage = 'multiple'
                self.calibration_duration = self.calibration_multiple_duration
                self.calibration_started_at = now
                self.calibration_remaining = float(self.calibration_duration)
                self.calibration_message = f'Stage 3/3: Multiple people in room ({self.calibration_multiple_duration}s)'
            return

        if self.calibration_stage == 'multiple':
            self.calibration_multiple_signatures.append(signature)
            self.calibration_multiple_energies.append(float(energy))
            if elapsed >= self.calibration_duration:
                if not self.pattern_detector:
                    self.calibration_active = False
                    self.calibration_stage = 'failed'
                    self.calibration_remaining = 0.0
                    self.calibration_message = 'Calibration failed: pattern detector unavailable'
                    self.live_calibration_applied = False
                    return

                ok, msg = self.pattern_detector.apply_live_calibration(
                    self.calibration_empty_signatures,
                    self.calibration_empty_energies,
                    self.calibration_occupied_signatures,
                    self.calibration_occupied_energies,
                    self.calibration_multiple_signatures,
                    self.calibration_multiple_energies,
                    alpha=self.calibration_alpha,
                    min_frames=self.calibration_min_frames
                )
                self.calibration_active = False
                self.calibration_stage = 'done' if ok else 'failed'
                self.calibration_remaining = 0.0
                self.calibration_message = msg
                self.live_calibration_applied = bool(ok)

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
    reconnect_delay = 1
    last_data_time = time.time()
    connection_established = False
    
    try:
        while True:
            try:
                if ser is None or not ser.is_open:
                    if serial_port:
                        try:
                            print(f"🔄 Connecting to {serial_port}...")
                            ser = serial.Serial(serial_port, CONFIG['baudrate'], timeout=CONFIG['serial_read_timeout'])
                            state.is_connected = True
                            connection_established = True
                            last_data_time = time.time()
                            reconnect_delay = 1
                            print(f"✅ Connected to {serial_port}")
                        except serial.SerialException as e:
                            print(f"❌ Failed to open {serial_port}: {e}")
                            state.is_connected = False
                            ser = None
                            time.sleep(reconnect_delay)
                            reconnect_delay = min(reconnect_delay * 1.5, 10)
                            continue
                    else:
                        print("⚠️ No serial port found, retrying...")
                        state.is_connected = False
                        time.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, 10)  # Exponential backoff
                        continue
                
                if ser.is_open:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                state.add_raw_csi_line(line, len(values))
                                if detection_enabled.is_set():
                                    state.add_csi_frame(values)
                                coll_state.write_frame(line)
                                realtime_state.write_frame(line)
                                last_data_time = time.time()
                                # Reset connection status on successful data
                                if not state.is_connected:
                                    state.is_connected = True
                                    print(f"✅ Data streaming resumed")
                        except (ValueError, IndexError):
                            pass
                    
                    # Check for data timeout (increased from 5s to 15s for calibration stability)
                    if time.time() - last_data_time > CONFIG['data_timeout_seconds']:
                        print(f"⚠️ No CSI data received for {CONFIG['data_timeout_seconds']} seconds, reconnecting...")
                        state.is_connected = False
                        if ser:
                            ser.close()
                            ser = None
                        time.sleep(2)
                        
            except (serial.SerialException, OSError, Exception) as e:
                state.is_connected = False
                if ser:
                    try:
                        ser.close()
                    except:
                        pass
                    ser = None
                print(f"⚠️ Serial error: {e}, reconnecting in {reconnect_delay}s...")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 1.5, 10)
    except KeyboardInterrupt:
        print("Shutting down...")
        if ser and ser.is_open:
            ser.close()

app = Flask(__name__, template_folder='templates')

CALIBRATED_BASELINE_DIR = '/Users/mizhabas/wifi_csi_imaging/data2/myroom'
COLLECTED_BASELINE_DIR = '/Users/mizhabas/wifi_csi_imaging/data2/realtime'

# ─── Data collection state ────────────────────────────────────────────────────
class CollectionState:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.label = None          # 'empty' | 'occupied' | 'multiple'
        self.duration = 60
        self.started_at = 0.0
        self.frames_collected = 0
        self.output_file = None
        self._file_handle = None

    def start(self, label, duration, data2_folder='/Users/mizhabas/wifi_csi_imaging/data2/myroom'):
        label_map = {'empty': 'empty.txt', 'occupied': 'occupied.txt', 'multiple': 'multiple_people.txt'}
        if label not in label_map:
            return False, f'Unknown label: {label}'
        with self.lock:
            if self.active:
                return False, 'Collection already running'
            os.makedirs(data2_folder, exist_ok=True)
            self.output_file = os.path.join(data2_folder, label_map[label])
            try:
                self._file_handle = open(self.output_file, 'a')
            except OSError as e:
                return False, str(e)
            self.label = label
            self.duration = max(10, int(duration))
            self.started_at = time.time()
            self.frames_collected = 0
            self.active = True
            return True, f'Collecting {label} data for {self.duration}s → {self.output_file}'

    def write_frame(self, raw_line):
        with self.lock:
            if not self.active or self._file_handle is None:
                return
            elapsed = time.time() - self.started_at
            if elapsed >= self.duration:
                self._finish()
                return
            try:
                self._file_handle.write(raw_line + '\n')
                self._file_handle.flush()
                self.frames_collected += 1
            except OSError:
                pass

    def _finish(self):
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass
            self._file_handle = None
        self.active = False

    def stop(self):
        with self.lock:
            self._finish()
            return True, f'Stopped. Frames collected: {self.frames_collected}'

    def status(self):
        with self.lock:
            elapsed = time.time() - self.started_at if self.active else 0.0
            remaining = max(0.0, self.duration - elapsed) if self.active else 0.0
            progress = min(100.0, (elapsed / self.duration * 100)) if self.active and self.duration > 0 else 0.0
            return {
                'active': self.active,
                'label': self.label,
                'duration': self.duration,
                'elapsed': round(elapsed, 1),
                'remaining': round(remaining, 1),
                'progress': round(progress, 1),
                'frames': self.frames_collected,
                'output_file': self.output_file,
            }

# ─── Realtime Collection State (for individual calibration) ──────────────────
class RealtimeCollectionState:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.label = None          # 'empty' | 'occupied' | 'multiple'
        self.duration = 60
        self.started_at = 0.0
        self.frames_collected = 0
        self.output_file = None
        self._file_handle = None

    def start(self, label, duration, realtime_folder='/Users/mizhabas/wifi_csi_imaging/data2/realtime'):
        label_map = {'empty': 'empty.txt', 'occupied': 'occupied.txt', 'multiple': 'multiple_people.txt'}
        if label not in label_map:
            return False, f'Unknown label: {label}'
        with self.lock:
            if self.active:
                return False, 'Collection already running'
            os.makedirs(realtime_folder, exist_ok=True)
            self.output_file = os.path.join(realtime_folder, label_map[label])
            try:
                self._file_handle = open(self.output_file, 'w')  # Write mode (overwrites previous realtime session)
            except OSError as e:
                return False, str(e)
            self.label = label
            self.duration = max(10, int(duration))
            self.started_at = time.time()
            self.frames_collected = 0
            self.active = True
            return True, f'Realtime: {label} for {self.duration}s → {self.output_file}'

    def write_frame(self, raw_line):
        with self.lock:
            if not self.active or self._file_handle is None:
                return
            elapsed = time.time() - self.started_at
            if elapsed >= self.duration:
                self._finish()
                return
            try:
                self._file_handle.write(raw_line + '\n')
                self._file_handle.flush()
                self.frames_collected += 1
            except OSError:
                pass

    def _finish(self):
        if self._file_handle:
            try:
                self._file_handle.close()
            except OSError:
                pass
            self._file_handle = None
        self.active = False

    def stop(self):
        with self.lock:
            self._finish()
            return True, f'Stopped. Frames: {self.frames_collected}'

    def status(self):
        with self.lock:
            elapsed = time.time() - self.started_at if self.active else 0.0
            remaining = max(0.0, self.duration - elapsed) if self.active else 0.0
            progress = min(100.0, (elapsed / self.duration * 100)) if self.active and self.duration > 0 else 0.0
            return {
                'active': self.active,
                'label': self.label,
                'duration': self.duration,
                'elapsed': round(elapsed, 1),
                'remaining': round(remaining, 1),
                'progress': round(progress, 1),
                'frames': self.frames_collected,
                'output_file': self.output_file,
            }


def count_csi_frames(path):
    if not os.path.isfile(path):
        return 0
    lines = 0
    try:
        with open(path, 'r') as f:
            for line in f:
                if line.strip().startswith('CSI_DATA:'):
                    lines += 1
    except OSError:
        return 0
    return lines


def get_realtime_summary(folder=COLLECTED_BASELINE_DIR):
    return {
        'empty': count_csi_frames(os.path.join(folder, 'empty.txt')),
        'occupied': count_csi_frames(os.path.join(folder, 'occupied.txt')),
        'multiple': count_csi_frames(os.path.join(folder, 'multiple_people.txt')),
        'folder': folder,
    }


def switch_detection_baseline(mode):
    if pattern_detector is None:
        return False, 'Pattern detector unavailable'

    if mode == 'collected':
        target_folder = COLLECTED_BASELINE_DIR
    else:
        target_folder = CALIBRATED_BASELINE_DIR

    previous_folder = pattern_detector.data_folder
    previous_patterns = dict(pattern_detector.patterns)
    previous_min_frames = pattern_detector.min_frames
    previous_window_frames = pattern_detector.window_frames
    previous_window_step = pattern_detector.window_step
    previous_min_windows = getattr(pattern_detector, 'min_windows', 3)

    # Realtime session files are naturally smaller; use lighter extraction limits
    # so "collected" mode can start after practical short captures.
    if mode == 'collected':
        pattern_detector.min_frames = 20
        pattern_detector.window_frames = 40
        pattern_detector.window_step = 10
        pattern_detector.min_windows = 1
    else:
        pattern_detector.min_frames = 100
        pattern_detector.window_frames = 150
        pattern_detector.window_step = 30
        pattern_detector.min_windows = 3

    pattern_detector.data_folder = target_folder
    pattern_detector.patterns = {}
    pattern_detector.load_reference_patterns()

    pattern_detector.min_frames = previous_min_frames
    pattern_detector.window_frames = previous_window_frames
    pattern_detector.window_step = previous_window_step
    pattern_detector.min_windows = previous_min_windows

    if not pattern_detector.patterns:
        pattern_detector.data_folder = previous_folder
        pattern_detector.patterns = previous_patterns
        return False, f'No valid patterns found in {target_folder}'

    return True, f'Loaded {len(pattern_detector.patterns)} patterns from {target_folder}'

coll_state = CollectionState()
realtime_state = RealtimeCollectionState()

# ─── Live detection on/off ────────────────────────────────────────────────────
detection_enabled = threading.Event()
detection_enabled.set()  # on by default

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('monitor.html')

@app.route('/api/data')
def api_data():
    d = state.get_data()
    d['detection_enabled'] = detection_enabled.is_set()
    return jsonify(d)

@app.route('/api/status')
def api_status():
    data = state.get_data()
    return jsonify({
        'status': data['status'],
        'status_color': data['status_color'],
        'is_connected': data['is_connected'],
        'is_calibrated': data['is_calibrated'],
        'detection_enabled': detection_enabled.is_set(),
        'collection': coll_state.status(),
    })

# ── Calibration ───────────────────────────────────────────────────────────────
@app.route('/api/calibration/start', methods=['POST'])
def api_start_calibration():
    payload = request.get_json(silent=True) or {}
    empty_duration = int(payload.get('empty_duration', 60))
    occupied_duration = int(payload.get('occupied_duration', 60))
    multiple_duration = int(payload.get('multiple_duration', 60))
    min_frames = int(payload.get('min_frames', 80))
    alpha = float(payload.get('alpha', 0.9))
    ok, msg = state.start_live_calibration(
        empty_duration=empty_duration,
        occupied_duration=occupied_duration,
        multiple_duration=multiple_duration,
        min_frames=min_frames,
        alpha=alpha
    )
    return jsonify({'ok': bool(ok), 'message': msg})

@app.route('/api/calibration/stop', methods=['POST'])
def api_stop_calibration():
    ok, msg = state.stop_live_calibration()
    return jsonify({'ok': bool(ok), 'message': msg})

# ── Data collection ───────────────────────────────────────────────────────────
@app.route('/api/collect/start', methods=['POST'])
def api_collect_start():
    payload = request.get_json(silent=True) or {}
    label = payload.get('label', 'empty')
    duration = payload.get('duration', 60)
    ok, msg = coll_state.start(label, duration)
    return jsonify({'ok': ok, 'message': msg})

@app.route('/api/collect/stop', methods=['POST'])
def api_collect_stop():
    ok, msg = coll_state.stop()
    return jsonify({'ok': ok, 'message': msg})

@app.route('/api/collect/status')
def api_collect_status():
    return jsonify(coll_state.status())

# ── Realtime individual calibration data collection ───────────────────────────
@app.route('/api/realtime/start', methods=['POST'])
def api_realtime_start():
    payload = request.get_json(silent=True) or {}
    label = payload.get('label', 'empty')
    duration = payload.get('duration', 60)
    ok, msg = realtime_state.start(label, duration)
    return jsonify({'ok': ok, 'message': msg})

@app.route('/api/realtime/stop', methods=['POST'])
def api_realtime_stop():
    payload = request.get_json(silent=True) or {}
    ok, msg = realtime_state.stop()
    return jsonify({'ok': ok, 'message': msg})

@app.route('/api/realtime/status')
def api_realtime_status():
    return jsonify(realtime_state.status())


@app.route('/api/realtime/summary')
def api_realtime_summary():
    return jsonify(get_realtime_summary())

# ── Live detection control ─────────────────────────────────────────────────────
detection_baseline_mode = None  # 'collected' or 'calibrated'

@app.route('/api/detection/start', methods=['POST'])
def api_detection_start():
    detection_enabled.set()
    return jsonify({'ok': True, 'detection_enabled': True})

@app.route('/api/detection/stop', methods=['POST'])
def api_detection_stop():
    detection_enabled.clear()
    state.stable_state = '⏳ DETECTION PAUSED'
    state.current_status = '⏳ DETECTION PAUSED'
    state.status_color = '#808080'
    return jsonify({'ok': True, 'detection_enabled': False})

# ── Detection with different baselines ─────────────────────────────────────────
@app.route('/api/detection/mode/start', methods=['POST'])
def api_detection_mode_start():
    global detection_baseline_mode
    payload = request.get_json(silent=True) or {}
    mode = payload.get('mode', 'calibrated')  # 'collected' or 'calibrated'
    
    if mode not in ['collected', 'calibrated']:
        return jsonify({'ok': False, 'message': 'Invalid mode'})
    
    ok, load_msg = switch_detection_baseline(mode)
    if not ok:
        return jsonify({'ok': False, 'message': load_msg})

    detection_baseline_mode = mode
    detection_enabled.set()
    
    msg = f'Detection started with {mode} data baseline'
    print(f"🔍 {msg}")
    
    return jsonify({'ok': True, 'message': msg})

@app.route('/api/detection/mode/stop', methods=['POST'])
def api_detection_mode_stop():
    global detection_baseline_mode
    payload = request.get_json(silent=True) or {}
    mode = payload.get('mode', 'calibrated')
    
    detection_enabled.clear()
    detection_baseline_mode = None
    state.stable_state = '⏳ DETECTION PAUSED'
    state.current_status = '⏳ DETECTION PAUSED'
    state.status_color = '#808080'
    
    print(f"⏹ Detection stopped ({mode} mode)")
    
    return jsonify({'ok': True, 'message': f'Detection stopped'})


@app.route('/api/detection/mode/status')
def api_detection_mode_status():
    return jsonify({
        'ok': True,
        'mode': detection_baseline_mode,
        'detection_enabled': detection_enabled.is_set(),
        'pattern_source': pattern_detector.data_folder if pattern_detector else None,
        'patterns': sorted(list(pattern_detector.patterns.keys())) if pattern_detector else [],
    })

# ── Logs ──────────────────────────────────────────────────────────────────────
DATA2_ROOT = '/Users/mizhabas/wifi_csi_imaging/data2'

@app.route('/api/logs/list')
def api_logs_list():
    result = {}
    if os.path.isdir(DATA2_ROOT):
        for room in sorted(os.listdir(DATA2_ROOT)):
            room_path = os.path.join(DATA2_ROOT, room)
            if os.path.isdir(room_path):
                files = []
                for fname in sorted(os.listdir(room_path)):
                    fpath = os.path.join(room_path, fname)
                    if os.path.isfile(fpath):
                        stat = os.stat(fpath)
                        lines = 0
                        try:
                            with open(fpath, 'r') as f:
                                lines = sum(1 for l in f if l.strip().startswith('CSI_DATA:'))
                        except OSError:
                            pass
                        files.append({
                            'name': fname,
                            'path': f'{room}/{fname}',
                            'size_kb': round(stat.st_size / 1024, 1),
                            'frames': lines,
                            'modified': time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime)),
                        })
                result[room] = files
    return jsonify(result)

@app.route('/api/logs/read')
def api_logs_read():
    rel = request.args.get('path', '')
    # Sanitize: only allow files inside DATA2_ROOT
    safe = os.path.normpath(os.path.join(DATA2_ROOT, rel))
    if not safe.startswith(DATA2_ROOT + os.sep):
        return jsonify({'error': 'Invalid path'}), 400
    if not os.path.isfile(safe):
        return jsonify({'error': 'File not found'}), 404
    lines = []
    try:
        with open(safe, 'r') as f:
            for i, line in enumerate(f):
                if i >= 200:
                    lines.append('... (truncated, showing first 200 lines)')
                    break
                lines.append(line.rstrip())
    except OSError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'path': rel, 'lines': lines})

@app.route('/api/logs/delete', methods=['POST'])
def api_logs_delete():
    payload = request.get_json(silent=True) or {}
    rel = payload.get('path', '')
    safe = os.path.normpath(os.path.join(DATA2_ROOT, rel))
    if not safe.startswith(DATA2_ROOT + os.sep):
        return jsonify({'error': 'Invalid path'}), 400
    if not os.path.isfile(safe):
        return jsonify({'error': 'File not found'}), 404
    try:
        os.remove(safe)
    except OSError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'ok': True})

# ── Reload patterns after collection ──────────────────────────────────────────
@app.route('/api/patterns/reload', methods=['POST'])
def api_patterns_reload():
    try:
        pattern_detector.load_reference_patterns()
        state.is_calibrated = len(pattern_detector.patterns) > 0
        return jsonify({'ok': True, 'patterns': list(pattern_detector.patterns.keys())})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

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
