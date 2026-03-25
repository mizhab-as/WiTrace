#!/usr/bin/env python3

import numpy as np
import os

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))
DEFAULT_DATA_FOLDER = os.path.join(PROJECT_ROOT, 'data2', 'myroom')

class PatternDetector:
    def __init__(self, data_folder=DEFAULT_DATA_FOLDER):
        self.data_folder = data_folder
        self.patterns = {}
        self.target_bins = 64
        self.window_frames = 150        # Larger window for more stable patterns (was 120)
        self.window_step = 30           # Larger step for better separation (was 20)
        self.min_frames = 50            # Minimum frames for pattern MATCHING (was 100 for building)
        self.min_frames_for_training = 100  # Separate threshold for building new patterns
        self.min_windows = 3            # Minimum feature windows required to build a pattern
        self.min_confidence = 55.0      # Increased from 45.0 - stricter confidence threshold
        self.min_margin = 8.0           # Increased from 3.0 - require better separation between patterns
        self.min_binary_margin = 5.0    # Increased from 2.0 - stricter for empty/not_empty distinction
        self.template_points = 80
        self.template_window_frames = 60
        self.baseline_templates = {}

        # Optional meta gating (keeps training + live consistent)
        self.active_tx_mac = (os.environ.get('WITRACE_TX_MAC') or '').strip().lower() or None
        self.lock_tx_mac = True
        self.min_snr_db = 10
        # Feature weights: emphasize variance, entropy, spectral characteristics, and basic link quality
        self.feature_weights = np.array([
            1.5,   # emean (0) - energy level
            3.0,   # estd (1) - VARIANCE KEY FEATURE - higher weight
            2.5,   # mad (2) - median absolute deviation
            2.5,   # iqr (3) - interquartile range
            2.5,   # ptp (4) - peak-to-peak
            2.0,   # sent (5) - energy entropy
            3.5,   # mv_mean (6) - MOVING VARIANCE MEAN - highest weight for temporal dynamics
            3.0,   # mv_std (7) - moving variance std
            3.5,   # mv_max (8) - MOVING VARIANCE MAX - captures peak dynamics
            2.0,   # low/total (9)
            2.0,   # mid/total (10)
            2.0,   # high/total (11)
            2.5,   # spec_entropy (12) - spectral entropy
            1.5,   # centroid_norm (13)
            1.5,   # rms_norm (14)
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,  # sig_bands (15-22) - lower weight

            # Meta-derived features (23-28)
            0.35,  # rssi_mean
            0.65,  # rssi_std
            0.75,  # snr_mean
            0.85,  # snr_std
            0.25,  # mcs_mean
            0.25,  # rate_mean

            # Additional metadata quality/link features (29-37)
            0.30,  # channel_mean
            0.20,  # cwb_mean
            0.20,  # sgi_mean
            0.20,  # stbc_mean
            0.40,  # len_mean
            0.40,  # len_std
            0.70,  # rx_error_ratio
            0.40,  # snr_p10
            0.40,  # snr_p90
        ])
        self.load_reference_patterns()
    
    def load_reference_patterns(self):
        print("🔍 Loading reference patterns...")
        
        state_files = {
            'empty': 'empty.txt',
            'occupied': 'occupied.txt',
            'multi': 'multiple_people.txt'
        }
        
        for state, filename in state_files.items():
            filepath = os.path.join(self.data_folder, filename)
            if os.path.exists(filepath):
                pattern_data = self._extract_pattern(filepath)
                if pattern_data:
                    self.patterns[state] = pattern_data
                    print(f"✅ Loaded {state}: {pattern_data['samples']} windows")

                # Build a baseline energy template for live 5s matching graphs.
                energies = self._extract_energy_series(filepath)
                if len(energies) >= 20:
                    tmpl = self._build_energy_template(energies)
                    if tmpl is not None:
                        self.baseline_templates[state] = tmpl
            else:
                print(f"⚠️ Reference file not found: {filename}")

        if not self.patterns:
            print(f"⚠️ No valid training patterns found in {self.data_folder}")
        else:
            print("🧠 Training mode: raw-window-feature")

    @staticmethod
    def _resample_vector(values, target_len):
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            return None
        if arr.size == target_len:
            return arr
        x_old = np.linspace(0.0, 1.0, num=arr.size)
        x_new = np.linspace(0.0, 1.0, num=target_len)
        return np.interp(x_new, x_old, arr)

    @staticmethod
    def _normalize_trace(values):
        arr = np.asarray(values, dtype=float)
        if arr.size == 0:
            return arr
        m = float(np.mean(arr))
        s = float(np.std(arr))
        if s < 1e-8:
            return arr - m
        return (arr - m) / s

    def _build_energy_template(self, frame_energies):
        if frame_energies is None or len(frame_energies) < 20:
            return None
        x = np.asarray(frame_energies, dtype=float)
        win = min(max(20, self.template_window_frames), max(20, len(x)))
        step = max(8, win // 4)

        traces = []
        if len(x) >= win:
            for i in range(0, len(x) - win + 1, step):
                seg = x[i:i + win]
                r = self._resample_vector(seg, self.template_points)
                if r is not None:
                    traces.append(self._normalize_trace(r))
        else:
            r = self._resample_vector(x, self.template_points)
            if r is not None:
                traces.append(self._normalize_trace(r))

        if not traces:
            return None
        return np.mean(np.vstack(traces), axis=0)

    def _extract_energy_series(self, filepath):
        frame_energies = []
        pending_meta = None
        pending_values = None
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('CSI_META:'):
                        parsed = self._parse_csi_meta_line(line)
                        if parsed:
                            if pending_values is not None:
                                if self._accept_meta(parsed):
                                    frame_energies.append(float(self.values_to_energy(pending_values, meta=parsed)))
                                pending_values = None
                            else:
                                pending_meta = parsed
                        else:
                            pending_meta = None
                        continue
                    if line.startswith('tx_mac='):
                        pending_meta = {'tx_mac': line.split('=', 1)[1].strip()}
                        continue
                    if line.startswith('CSI_DATA:'):
                        try:
                            values = [int(v) for v in line.split(':', 1)[1].strip().split()]
                        except ValueError:
                            continue
                        if not values:
                            continue

                        if pending_meta is not None:
                            if self._accept_meta(pending_meta):
                                frame_energies.append(float(self.values_to_energy(values, meta=pending_meta)))
                            pending_meta = None
                        else:
                            if pending_values is not None:
                                frame_energies.append(float(self.values_to_energy(pending_values, meta=None)))
                            pending_values = values

            if pending_values is not None:
                frame_energies.append(float(self.values_to_energy(pending_values, meta=None)))
        except Exception:
            return []
        return frame_energies

    def match_live_window(self, frame_energies):
        if frame_energies is None or len(frame_energies) < 10:
            return {
                'scores': {},
                'best_state': None,
                'live_trace': [],
                'templates': {}
            }

        if not self.baseline_templates:
            return {
                'scores': {},
                'best_state': None,
                'live_trace': [],
                'templates': {}
            }

        win = min(max(20, self.template_window_frames), len(frame_energies))
        live_seg = np.asarray(frame_energies[-win:], dtype=float)
        live_r = self._resample_vector(live_seg, self.template_points)
        if live_r is None:
            return {
                'scores': {},
                'best_state': None,
                'live_trace': [],
                'templates': {}
            }
        live_z = self._normalize_trace(live_r)

        scores = {}
        for state, tmpl in self.baseline_templates.items():
            t = np.asarray(tmpl, dtype=float)
            if t.size != live_z.size:
                t = self._resample_vector(t, live_z.size)
            if t is None:
                continue

            # Correlation component
            corr = float(np.corrcoef(live_z, t)[0, 1]) if np.std(live_z) > 1e-9 and np.std(t) > 1e-9 else 0.0
            corr = max(-1.0, min(1.0, corr))
            corr_score = (corr + 1.0) * 50.0

            # Shape error component
            rmse = float(np.sqrt(np.mean((live_z - t) ** 2)))
            rmse_score = 100.0 / (1.0 + rmse)

            scores[state] = float(0.7 * corr_score + 0.3 * rmse_score)

        if scores:
            keys = [k for k in ['empty', 'occupied', 'multi'] if k in scores]
            raw = np.asarray([scores[k] for k in keys], dtype=float)
            z = raw - np.max(raw)
            p = np.exp(z / 10.0)
            p = p / (np.sum(p) + 1e-12)
            norm_scores = {k: float(v * 100.0) for k, v in zip(keys, p)}
            best_state = max(norm_scores, key=norm_scores.get)
        else:
            norm_scores = {}
            best_state = None

        return {
            'scores': norm_scores,
            'best_state': best_state,
            'live_trace': [float(v) for v in live_z.tolist()],
            'templates': {
                k: [float(v) for v in np.asarray(t, dtype=float).tolist()]
                for k, t in self.baseline_templates.items()
            }
        }
    
    def _extract_pattern(self, filepath):
        frame_signatures = []
        frame_energies = []
        frame_meta = []
        pending_meta = None
        pending_values = None
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('CSI_META:'):
                        parsed = self._parse_csi_meta_line(line)
                        if parsed:
                            # If CSI_DATA came first, pair retroactively.
                            if pending_values is not None:
                                if self._accept_meta(parsed):
                                    sig = self._frame_signature(pending_values, meta=parsed)
                                    if sig is not None:
                                        frame_signatures.append(sig)
                                        frame_energies.append(float(self.values_to_energy(pending_values, meta=parsed)))
                                        frame_meta.append(dict(parsed))
                                pending_values = None
                            else:
                                pending_meta = parsed
                        else:
                            pending_meta = None
                        continue
                    if line.startswith('tx_mac='):
                        # Some logs may contain loose meta lines.
                        pending_meta = {'tx_mac': line.split('=', 1)[1].strip()}
                        continue
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                if pending_meta is not None:
                                    if self._accept_meta(pending_meta):
                                        sig = self._frame_signature(values, meta=pending_meta)
                                        if sig is not None:
                                            frame_signatures.append(sig)
                                            frame_energies.append(float(self.values_to_energy(values, meta=pending_meta)))
                                            frame_meta.append(dict(pending_meta))
                                    pending_meta = None
                                else:
                                    # Buffer in case CSI_META arrives immediately after.
                                    # If no meta arrives, flush the buffered frame on the next CSI_DATA.
                                    if pending_values is not None:
                                        sig = self._frame_signature(pending_values, meta=None)
                                        if sig is not None:
                                            frame_signatures.append(sig)
                                            frame_energies.append(float(self.values_to_energy(pending_values, meta=None)))
                                            frame_meta.append({})
                                    pending_values = values
                        except ValueError:
                            continue

            # Flush last unpaired CSI_DATA
            if pending_values is not None:
                sig = self._frame_signature(pending_values, meta=None)
                if sig is not None:
                    frame_signatures.append(sig)
                    frame_energies.append(float(self.values_to_energy(pending_values, meta=None)))
                    frame_meta.append({})
                pending_values = None
            
            if len(frame_signatures) < self.min_frames_for_training:
                return None

            window_features = self._window_features(frame_signatures, frame_energies, frame_meta)
            if len(window_features) < self.min_windows:
                return None

            return self._build_pattern(window_features)
        except Exception as e:
            print(f"❌ Error reading {filepath}: {e}")
            return None

    def _build_pattern(self, feature_vectors):
        feature_stack = np.vstack(feature_vectors)
        centroid = np.mean(feature_stack, axis=0)
        scale = np.std(feature_stack, axis=0) + 1e-3
        distances = np.mean(np.abs((feature_stack - centroid) / scale), axis=1)

        return {
            'samples': len(feature_vectors),
            'centroid': centroid,
            'scale': scale,
            'spread': float(np.std(distances) + np.mean(distances) * 0.25 + 1e-6),
        }

    def _blend_patterns(self, old_pattern, new_pattern, alpha=0.8):
        # Weighted update keeps model stable while adapting to current environment.
        centroid = alpha * new_pattern['centroid'] + (1.0 - alpha) * old_pattern['centroid']
        scale = alpha * new_pattern['scale'] + (1.0 - alpha) * old_pattern['scale']
        spread = float(alpha * new_pattern['spread'] + (1.0 - alpha) * old_pattern['spread'])
        return {
            'samples': int(alpha * new_pattern['samples'] + (1.0 - alpha) * old_pattern['samples']),
            'centroid': centroid,
            'scale': scale,
            'spread': spread,
        }

    def build_pattern_from_live(self, frame_signatures, frame_energies, min_frames=None):
        return self.build_pattern_from_live_with_meta(frame_signatures, frame_energies, frame_meta=None, min_frames=min_frames)

    def build_pattern_from_live_with_meta(self, frame_signatures, frame_energies, frame_meta=None, min_frames=None):
        if frame_signatures is None or frame_energies is None:
            return None, "missing data"
        required = self.min_frames if min_frames is None else max(20, int(min_frames))
        if len(frame_signatures) < required or len(frame_energies) < required:
            return None, f"insufficient frames ({len(frame_signatures)}/{required})"
        features = self._window_features(frame_signatures, frame_energies, frame_meta)
        if len(features) < 1:
            return None, f"insufficient windows ({len(features)})"
        return self._build_pattern(features), f"frames={len(frame_signatures)}, windows={len(features)}"

    def apply_live_calibration(
        self,
        empty_signatures,
        empty_energies,
        occupied_signatures,
        occupied_energies,
        multiple_signatures=None,
        multiple_energies=None,
        alpha=0.85,
        min_frames=None,
        empty_meta=None,
        occupied_meta=None,
        multiple_meta=None,
    ):
        alpha = float(min(0.98, max(0.50, alpha)))
        empty_pattern, empty_msg = self.build_pattern_from_live_with_meta(
            empty_signatures,
            empty_energies,
            frame_meta=empty_meta,
            min_frames=min_frames,
        )
        occ_pattern, occ_msg = self.build_pattern_from_live_with_meta(
            occupied_signatures,
            occupied_energies,
            frame_meta=occupied_meta,
            min_frames=min_frames,
        )

        if empty_pattern is None:
            return False, f"Empty calibration failed: {empty_msg}"
        if occ_pattern is None:
            return False, f"Occupied calibration failed: {occ_msg}"

        if 'empty' in self.patterns:
            self.patterns['empty'] = self._blend_patterns(self.patterns['empty'], empty_pattern, alpha=alpha)
        else:
            self.patterns['empty'] = empty_pattern

        if 'occupied' in self.patterns:
            self.patterns['occupied'] = self._blend_patterns(self.patterns['occupied'], occ_pattern, alpha=alpha)
        else:
            self.patterns['occupied'] = occ_pattern

        has_multi_inputs = multiple_signatures is not None and multiple_energies is not None
        if has_multi_inputs:
            multi_pattern, multi_msg = self.build_pattern_from_live_with_meta(
                multiple_signatures,
                multiple_energies,
                frame_meta=multiple_meta,
                min_frames=min_frames,
            )
            if multi_pattern is None:
                return False, f"Multiple calibration failed: {multi_msg}"

            if 'multi' in self.patterns:
                self.patterns['multi'] = self._blend_patterns(self.patterns['multi'], multi_pattern, alpha=alpha)
            else:
                self.patterns['multi'] = multi_pattern

            return True, f"Live calibration applied (empty + occupied + multi) [{empty_msg}; {occ_msg}; {multi_msg}]"

        return True, f"Live calibration applied (empty + occupied) [{empty_msg}; {occ_msg}]"

    @staticmethod
    def _parse_csi_meta_line(line):
        if not line or not line.startswith('CSI_META:'):
            return None
        payload = line.split(':', 1)[1].strip()
        if not payload:
            return None
        meta = {}
        for token in payload.split():
            if '=' not in token:
                continue
            key, value = token.split('=', 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if key == 'tx_mac':
                meta[key] = value
                continue
            try:
                meta[key] = int(value)
            except ValueError:
                meta[key] = value
        return meta if meta else None

    def _accept_meta(self, meta):
        meta = dict(meta or {})
        tx_mac = meta.get('tx_mac')
        if isinstance(tx_mac, str):
            tx_mac = tx_mac.strip().lower()
        else:
            tx_mac = None

        if self.active_tx_mac:
            if tx_mac and tx_mac != self.active_tx_mac:
                return False
        elif self.lock_tx_mac and tx_mac:
            self.active_tx_mac = tx_mac

        try:
            rssi = meta.get('rssi')
            noise_floor = meta.get('noise_floor')
            if isinstance(rssi, int) and isinstance(noise_floor, int):
                snr = int(rssi - noise_floor)
                if snr < int(self.min_snr_db):
                    return False
        except Exception:
            pass
        return True

    @staticmethod
    def _values_to_amplitude(values, meta=None):
        if values is None:
            return None
        try:
            arr = np.asarray(values, dtype=float)
        except Exception:
            return None
        if arr.size < 8:
            return None

        # Backward-compatibility:
        # - Older datasets in this repo contain CSI_DATA-only and may already be in an "amplitude-ish" int format.
        # - Newer (CSI_META+CSI_DATA) streams are treated as interleaved int8 I/Q bytes.
        has_meta = isinstance(meta, dict) and len(meta) > 0

        if not has_meta:
            amp = np.abs(arr)
        else:
            if arr.size % 2 == 0:
                i = arr[0::2]
                q = arr[1::2]
                amp = np.sqrt(i * i + q * q)
            else:
                amp = np.abs(arr)

        if amp.size < 4:
            return None

        # Many logs include trailing zero padding; trim it so FFT features remain informative.
        nz = np.nonzero(amp)[0]
        if nz.size == 0:
            return None
        last = int(nz[-1])
        if last < (amp.size - 1):
            amp = amp[: last + 1]

        if amp.size < 8:
            return None
        return amp

    def values_to_energy(self, values, meta=None):
        amp = self._values_to_amplitude(values, meta=meta)
        if amp is None:
            return 0.0
        return float(np.mean(amp))

    def _frame_signature(self, values, meta=None):
        amp = self._values_to_amplitude(values, meta=meta)
        if amp is None:
            return None

        arr = amp.astype(float)

        arr = arr - np.mean(arr)
        if np.allclose(arr, 0):
            return None

        spectrum = np.abs(np.fft.rfft(arr))
        spectrum[0] = 0.0

        if spectrum.size < self.target_bins:
            x_old = np.linspace(0, 1, num=spectrum.size)
            x_new = np.linspace(0, 1, num=self.target_bins)
            spectrum = np.interp(x_new, x_old, spectrum)
        elif spectrum.size > self.target_bins:
            spectrum = spectrum[:self.target_bins]

        norm = np.linalg.norm(spectrum) + 1e-9
        return spectrum / norm

    def frame_signature(self, values, meta=None):
        return self._frame_signature(values, meta=meta)

    def _window_features(self, frame_signatures, frame_energies, frame_meta=None):
        if frame_meta is None:
            frame_meta = [{} for _ in range(min(len(frame_signatures), len(frame_energies)))]
        n = min(len(frame_signatures), len(frame_energies), len(frame_meta))
        if n < self.min_frames:
            return []

        features = []
        for i in range(0, n - self.window_frames + 1, self.window_step):
            sig_win = frame_signatures[i:i + self.window_frames]
            ene_win = frame_energies[i:i + self.window_frames]
            meta_win = frame_meta[i:i + self.window_frames]
            vec = self._extract_feature_vector(sig_win, ene_win, meta_win)
            if vec is not None:
                features.append(vec)

        if not features:
            sig_win = frame_signatures[-self.window_frames:]
            ene_win = frame_energies[-self.window_frames:]
            meta_win = frame_meta[-self.window_frames:]
            vec = self._extract_feature_vector(sig_win, ene_win, meta_win)
            if vec is not None:
                features.append(vec)

        return features

    def _moving_variance(self, x, k=12):
        """
        Calculate moving variance with improved sensitivity.
        Large k=12 window captures temporal dynamics crucial for occupancy.
        Empty rooms: low, steady variance
        Occupied rooms: high, dynamic variance due to body movements
        """
        if len(x) < k:
            return np.array([np.var(x)])
        vals = []
        for i in range(0, len(x) - k + 1):
            window = x[i:i + k]
            # Weight recent values more heavily in variance calculation
            weights = np.linspace(0.7, 1.0, len(window))
            weighted_var = np.sum(weights * (window - np.mean(window))**2) / np.sum(weights)
            vals.append(weighted_var)
        return np.array(vals, dtype=float) if vals else np.array([np.var(x)])

    def _extract_feature_vector(self, sig_window, energy_window, meta_window=None):
        if len(sig_window) < 16 or len(energy_window) < 16:
            return None

        if meta_window is None:
            meta_window = [{} for _ in range(len(energy_window))]

        e = np.array(energy_window, dtype=float)
        emean = np.mean(e)
        estd = np.std(e)
        if estd < 1e-8:
            estd = 1e-8

        median = np.median(e)
        mad = np.median(np.abs(e - median))
        iqr = np.percentile(e, 75) - np.percentile(e, 25)
        ptp = np.ptp(e)

        q = np.abs(e) / (np.sum(np.abs(e)) + 1e-9)
        sent = -np.sum(q * np.log(q + 1e-12)) / np.log(len(q) + 1e-12)

        mv = self._moving_variance(e, k=12)
        mv_mean = np.mean(mv)
        mv_std = np.std(mv)
        mv_max = np.max(mv)

        d = e - emean
        spec = np.abs(np.fft.rfft(d)) ** 2
        if len(spec) < 8:
            return None
        spec[0] = 0.0
        ps = spec / (np.sum(spec) + 1e-9)
        spec_entropy = -np.sum(ps * np.log(ps + 1e-12)) / np.log(len(ps) + 1e-12)

        n = len(spec)
        low = np.sum(spec[1:max(2, n // 6)])
        mid = np.sum(spec[max(2, n // 6):max(3, n // 3)])
        high = np.sum(spec[max(3, n // 3):])
        total = low + mid + high + 1e-9

        idx = np.arange(n, dtype=float)
        centroid = np.sum(idx * spec) / (np.sum(spec) + 1e-9)
        rms_freq = np.sqrt(np.sum((idx ** 2) * spec) / (np.sum(spec) + 1e-9))
        centroid_norm = centroid / max(1.0, n - 1)
        rms_norm = rms_freq / max(1.0, n - 1)

        sig_mean = np.mean(np.vstack(sig_window), axis=0)
        sig_mean = sig_mean / (np.linalg.norm(sig_mean) + 1e-9)
        split = np.array_split(sig_mean, 8)
        sig_bands = [float(np.sum(b)) for b in split]

        # Meta stats (robust to missing meta)
        rssi_vals = []
        snr_vals = []
        mcs_vals = []
        rate_vals = []
        channel_vals = []
        cwb_vals = []
        sgi_vals = []
        stbc_vals = []
        len_vals = []
        rx_error_count = 0
        rx_total_count = 0
        for m in meta_window:
            if not isinstance(m, dict):
                continue
            rssi = m.get('rssi')
            noise_floor = m.get('noise_floor')
            if isinstance(rssi, int):
                rssi_vals.append(rssi)
                if isinstance(noise_floor, int):
                    snr_vals.append(int(rssi - noise_floor))
            mcs = m.get('mcs')
            if isinstance(mcs, int):
                mcs_vals.append(mcs)
            rate = m.get('rate')
            if isinstance(rate, int):
                rate_vals.append(rate)

            ch = m.get('channel')
            if isinstance(ch, int):
                channel_vals.append(ch)

            cwb = m.get('cwb')
            if isinstance(cwb, int):
                cwb_vals.append(cwb)

            sgi = m.get('sgi')
            if isinstance(sgi, int):
                sgi_vals.append(sgi)

            stbc = m.get('stbc')
            if isinstance(stbc, int):
                stbc_vals.append(stbc)

            clen = m.get('len')
            if isinstance(clen, int):
                len_vals.append(clen)

            rx_state = m.get('rx_state')
            if isinstance(rx_state, int):
                rx_total_count += 1
                if rx_state != 0:
                    rx_error_count += 1

        def _mean_std(xs):
            if not xs:
                return 0.0, 0.0
            arr = np.asarray(xs, dtype=float)
            return float(np.mean(arr)), float(np.std(arr))

        rssi_mean, rssi_std = _mean_std(rssi_vals)
        snr_mean, snr_std = _mean_std(snr_vals)
        mcs_mean, _ = _mean_std(mcs_vals)
        rate_mean, _ = _mean_std(rate_vals)
        channel_mean, _ = _mean_std(channel_vals)
        cwb_mean, _ = _mean_std(cwb_vals)
        sgi_mean, _ = _mean_std(sgi_vals)
        stbc_mean, _ = _mean_std(stbc_vals)
        len_mean, len_std = _mean_std(len_vals)

        rx_error_ratio = float(rx_error_count / rx_total_count) if rx_total_count > 0 else 0.0
        if snr_vals:
            snr_arr = np.asarray(snr_vals, dtype=float)
            snr_p10 = float(np.percentile(snr_arr, 10))
            snr_p90 = float(np.percentile(snr_arr, 90))
        else:
            snr_p10 = 0.0
            snr_p90 = 0.0

        vec = np.array([
            emean,
            estd,
            mad,
            iqr,
            ptp,
            sent,
            mv_mean,
            mv_std,
            mv_max,
            low / total,
            mid / total,
            high / total,
            spec_entropy,
            centroid_norm,
            rms_norm,
            *sig_bands,

            rssi_mean,
            rssi_std,
            snr_mean,
            snr_std,
            mcs_mean,
            rate_mean,
            channel_mean,
            cwb_mean,
            sgi_mean,
            stbc_mean,
            len_mean,
            len_std,
            rx_error_ratio,
            snr_p10,
            snr_p90,
        ], dtype=float)

        return vec
    
    def detect(self, frame_signatures, frame_energies=None, frame_meta=None):
        if not self.patterns:
            return {
                'status': 'ERROR: No reference patterns',
                'confidence': 0.0,
                'scores': {}
            }

        if frame_energies is None or len(frame_signatures) < self.min_frames or len(frame_energies) < self.min_frames:
            return {
                'status': 'INITIALIZING',
                'confidence': 0.0,
                'scores': {}
            }

        if frame_meta is None:
            frame_meta = [{} for _ in range(min(len(frame_signatures), len(frame_energies)))]

        n = min(len(frame_signatures), len(frame_energies), len(frame_meta))
        if n < self.min_frames:
            return {
                'status': 'INITIALIZING',
                'confidence': 0.0,
                'scores': {}
            }

        # Ensemble over multiple recent windows for stability.
        queries = []
        if n >= self.window_frames:
            start = max(0, n - (self.window_frames * 3))
            step = max(8, self.window_step)
            for i in range(start, n - self.window_frames + 1, step):
                sig_win = frame_signatures[i:i + self.window_frames]
                ene_win = frame_energies[i:i + self.window_frames]
                meta_win = frame_meta[i:i + self.window_frames]
                q = self._extract_feature_vector(sig_win, ene_win, meta_win)
                if q is not None:
                    queries.append(q)

        if not queries:
            sig_win = frame_signatures[n - self.window_frames:n]
            ene_win = frame_energies[n - self.window_frames:n]
            meta_win = frame_meta[n - self.window_frames:n]
            q = self._extract_feature_vector(sig_win, ene_win, meta_win)
            if q is not None:
                queries.append(q)

        if not queries:
            return {
                'status': 'INITIALIZING',
                'confidence': 0.0,
                'scores': {}
            }

        score_runs = {state: [] for state in self.patterns.keys()}
        for query in queries:
            for state, pattern in self.patterns.items():
                score_runs[state].append(self._calculate_similarity(query, pattern))

        scores = {}
        for state, vals in score_runs.items():
            if vals:
                # Median is robust to transient windows.
                scores[state] = float(np.median(vals))
        
        if not scores:
            return {
                'status': 'ERROR: No reference patterns',
                'confidence': 0.0,
                'scores': scores
            }
        
        best_state = max(scores, key=scores.get)
        best_score = float(scores[best_state])

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        second_score = float(ranked[1][1]) if len(ranked) > 1 else 0.0
        margin = float(best_score - second_score)

        # Window stability boost: if recent windows agree, confidence improves.
        majority_ratio = 1.0
        if queries and len(queries) > 1:
            winners = []
            for query in queries:
                query_scores = {state: self._calculate_similarity(query, self.patterns[state]) for state in self.patterns.keys()}
                winners.append(max(query_scores, key=query_scores.get))
            majority_ratio = float(sum(1 for w in winners if w == best_state) / len(winners))

        # Convert raw matching scores into normalized class percentages.
        # This yields directly comparable "empty/occupied/multi" probabilities.
        cls_keys = [k for k in ['empty', 'occupied', 'multi'] if k in scores]
        raw = np.asarray([scores[k] for k in cls_keys], dtype=float)
        if raw.size > 0:
            # Stable softmax with mild temperature to keep separation meaningful.
            temp = 12.0
            z = (raw - np.max(raw)) / temp
            p = np.exp(z)
            p = p / (np.sum(p) + 1e-12)
            prob_scores = {k: float(v * 100.0) for k, v in zip(cls_keys, p)}
        else:
            prob_scores = {k: float(v) for k, v in scores.items()}

        best_prob = float(prob_scores.get(best_state, 0.0))
        adjusted_confidence = float(best_prob * (0.75 + 0.25 * majority_ratio))
        adjusted_confidence = float(max(0.0, min(100.0, adjusted_confidence)))

        ranked_probs = sorted(prob_scores.items(), key=lambda x: x[1], reverse=True)
        second_score = float(ranked_probs[1][1]) if len(ranked_probs) > 1 else 0.0
        margin = float(best_prob - second_score)

        # Binary classification: Empty vs Not-Empty (occupied or multiple people)
        binary_scores = {
            'empty': prob_scores.get('empty', 0.0),
            'not_empty': max(prob_scores.get('occupied', 0.0), prob_scores.get('multi', 0.0))
        }
        binary_margin = float(abs(binary_scores['empty'] - binary_scores['not_empty']))

        # Conservative correction against false-empty edge cases.
        if best_state == 'empty':
            occupied_score = max(prob_scores.get('occupied', 0.0), prob_scores.get('multi', 0.0))
            margin_to_occupied = best_prob - occupied_score
            if margin_to_occupied < 3.0 and occupied_score > 45.0:
                binary_state = 'not_empty'
                best_state = 'occupied' if prob_scores.get('occupied', 0.0) > prob_scores.get('multi', 0.0) else 'multi'
            else:
                binary_state = 'empty'
        else:
            binary_state = 'not_empty'

        final_state = best_state
        status_map = {
            'empty': '🟢 EMPTY ROOM',
            'occupied': '🔵 PERSON DETECTED',
            'multi': '🔴 MULTIPLE PEOPLE'
        }
        status_value = status_map.get(final_state, 'UNKNOWN')

        return {
            'status': status_value,
            'state': final_state,
            'confidence': adjusted_confidence,
            'scores': {k: float(v) for k, v in prob_scores.items()},
            'margin': margin,
            'binary_state': binary_state,
            'binary_scores': {k: float(v) for k, v in binary_scores.items()},
            'binary_margin': binary_margin,
            'raw_state': best_state,
            'is_uncertain': False,
            'ensemble_windows': int(len(queries)),
            'agreement': majority_ratio,
            'method': 'weighted_mahalanobis_ensemble'
        }
    
    def _calculate_similarity(self, query_features, pattern):
        """
        Calculate weighted Mahalanobis-like distance for robust occupancy detection.
        Key insight from CSI research: Variance features (estd, mv_mean, mv_max) are 
        most discriminative between empty and occupied rooms.
        """
        # Apply feature weighting (emphasizes key discriminative features)
        weighted_query = query_features * self.feature_weights
        weighted_centroid = pattern['centroid'] * self.feature_weights
        weighted_scale = pattern['scale'] * self.feature_weights
        
        # Prevent division by very small numbers
        weighted_scale = np.clip(weighted_scale, 1e-6, None)
        
        # Weighted Mahalanobis-like distance
        z = np.abs((weighted_query - weighted_centroid) / weighted_scale)
        
        # Apply non-linear clipping to emphasize deviations in key features
        # Softer clipping (was 6.0, now 5.0) to be more sensitive to differences
        z_clipped = np.clip(z, 0.0, 5.0)
        
        # Mean distance
        dist = float(np.mean(z_clipped))
        
        # Spread adjustment - penalizes patterns with high internal variance
        spread_adjust = dist / (pattern['spread'] + 1e-6)
        
        # Sigmoid-like transformation emphasizes low distances (empty) vs high distances (occupied)
        # Old: similarity = np.exp(-0.75 * spread_adjust)
        # New: More aggressive decay to be stricter about matches
        similarity = np.exp(-1.2 * spread_adjust)
        
        # Scale to 0-100 range with higher threshold for acceptance
        final_score = max(0.0, min(100.0, float(similarity * 100.0)))
        
        return final_score
