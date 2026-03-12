#!/usr/bin/env python3

import numpy as np
import os

class PatternDetector:
    def __init__(self, data_folder="/Users/mizhabas/wifi_csi_imaging/data2/myroom"):
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
        # Feature weights: emphasize variance, entropy, and spectral characteristics
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
            else:
                print(f"⚠️ Reference file not found: {filename}")

        if not self.patterns:
            print(f"⚠️ No valid training patterns found in {self.data_folder}")
        else:
            print("🧠 Training mode: raw-window-feature")
    
    def _extract_pattern(self, filepath):
        frame_signatures = []
        frame_energies = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                sig = self._frame_signature(values)
                                if sig is not None:
                                    frame_signatures.append(sig)
                                    frame_energies.append(float(np.mean(np.abs(values))))
                        except ValueError:
                            continue
            
            if len(frame_signatures) < self.min_frames_for_training:
                return None

            window_features = self._window_features(frame_signatures, frame_energies)
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
        if frame_signatures is None or frame_energies is None:
            return None, "missing data"
        required = self.min_frames if min_frames is None else max(20, int(min_frames))
        if len(frame_signatures) < required or len(frame_energies) < required:
            return None, f"insufficient frames ({len(frame_signatures)}/{required})"
        features = self._window_features(frame_signatures, frame_energies)
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
    ):
        alpha = float(min(0.98, max(0.50, alpha)))
        empty_pattern, empty_msg = self.build_pattern_from_live(empty_signatures, empty_energies, min_frames=min_frames)
        occ_pattern, occ_msg = self.build_pattern_from_live(occupied_signatures, occupied_energies, min_frames=min_frames)

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
            multi_pattern, multi_msg = self.build_pattern_from_live(
                multiple_signatures,
                multiple_energies,
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

    def _frame_signature(self, values):
        arr = np.abs(np.array(values, dtype=float))
        if arr.size < 8:
            return None

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

    def frame_signature(self, values):
        return self._frame_signature(values)

    def _window_features(self, frame_signatures, frame_energies):
        n = min(len(frame_signatures), len(frame_energies))
        if n < self.min_frames:
            return []

        features = []
        for i in range(0, n - self.window_frames + 1, self.window_step):
            sig_win = frame_signatures[i:i + self.window_frames]
            ene_win = frame_energies[i:i + self.window_frames]
            vec = self._extract_feature_vector(sig_win, ene_win)
            if vec is not None:
                features.append(vec)

        if not features:
            sig_win = frame_signatures[-self.window_frames:]
            ene_win = frame_energies[-self.window_frames:]
            vec = self._extract_feature_vector(sig_win, ene_win)
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

    def _extract_feature_vector(self, sig_window, energy_window):
        if len(sig_window) < 16 or len(energy_window) < 16:
            return None

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
        ], dtype=float)

        return vec
    
    def detect(self, frame_signatures, frame_energies=None):
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

        n = min(len(frame_signatures), len(frame_energies))
        sig_win = frame_signatures[n - self.window_frames:n]
        ene_win = frame_energies[n - self.window_frames:n]
        query = self._extract_feature_vector(sig_win, ene_win)
        if query is None:
            return {
                'status': 'INITIALIZING',
                'confidence': 0.0,
                'scores': {}
            }
        
        scores = {}
        for state, pattern in self.patterns.items():
            score = self._calculate_similarity(query, pattern)
            scores[state] = score
        
        if not scores:
            return {
                'status': 'ERROR: No reference patterns',
                'confidence': 0.0,
                'scores': scores
            }
        
        # Always use the best match (no uncertain state)
        best_state = max(scores, key=scores.get)
        best_score = float(scores[best_state])

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        second_score = float(ranked[1][1]) if len(ranked) > 1 else 0.0
        margin = float(best_score - second_score)

        # Binary classification: Empty vs Not-Empty (occupied or multiple people)
        binary_scores = {
            'empty': scores.get('empty', 0.0),
            'not_empty': max(scores.get('occupied', 0.0), scores.get('multi', 0.0))
        }
        binary_margin = float(abs(binary_scores['empty'] - binary_scores['not_empty']))
        
        # IMPROVED LOGIC: Add stricter filtering to avoid false empty positives
        # If 'empty' is best but margin to occupied is small, be more conservative
        if best_state == 'empty':
            occupied_score = max(scores.get('occupied', 0.0), scores.get('multi', 0.0))
            margin_to_occupied = best_score - occupied_score
            
            # If margin is too small (<5), occupied might be a stronger candidate
            # Threshold: empty must be clearly better, or occupied must be weak
            if margin_to_occupied < 5.0 and occupied_score > 35.0:
                # Empty barely wins but occupied is moderately confident
                # Boost occupied confidence as alternative
                binary_state = 'not_empty'
                best_state = 'occupied' if scores.get('occupied', 0.0) > scores.get('multi', 0.0) else 'multi'
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
        
        return {
            'status': status_map.get(final_state, 'UNKNOWN'),
            'state': final_state,
            'confidence': float(best_score),
            'scores': {k: float(v) for k, v in scores.items()},
            'margin': margin,
            'binary_state': binary_state,
            'binary_scores': {k: float(v) for k, v in binary_scores.items()},
            'binary_margin': binary_margin,
            'raw_state': best_state,
            'is_uncertain': False,
            'method': 'weighted_mahalanobis_matching'
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
