#!/usr/bin/env python3

import numpy as np
import os

class PatternDetector:
    def __init__(self, data_folder="/Users/mizhabas/wifi_csi_imaging/data"):
        self.data_folder = data_folder
        self.patterns = {}
        self.min_samples = 50
        self.load_reference_patterns()
    
    def load_reference_patterns(self):
        print("🔍 Loading reference patterns...")
        
        state_files = {
            'empty': 'empty.txt',
            'occupied': 'occupied.txt',
            'multi': 'multi_occ.txt'
        }
        
        for state, filename in state_files.items():
            filepath = os.path.join(self.data_folder, filename)
            if os.path.exists(filepath):
                pattern_data = self._extract_pattern(filepath)
                if pattern_data:
                    self.patterns[state] = pattern_data
                    print(f"✅ Loaded {state}: {len(pattern_data['variances'])} samples")
            else:
                print(f"⚠️ Reference file not found: {filename}")
    
    def _extract_pattern(self, filepath):
        csi_data = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                csi_data.append(values)
                        except (ValueError, IndexError):
                            continue
            
            if not csi_data:
                return None
            
            variances = []
            for values in csi_data:
                if len(values) > 0:
                    variance = np.std(np.abs(values))
                    variances.append(variance)
            
            if len(variances) < self.min_samples:
                return None
            
            variances = np.array(variances)
            pattern = {
                'variances': variances,
                'mean': np.mean(variances),
                'std': np.std(variances),
                'min': np.min(variances),
                'max': np.max(variances),
                'median': np.median(variances),
                'quantile_25': np.percentile(variances, 25),
                'quantile_75': np.percentile(variances, 75),
            }
            
            return pattern
        except Exception as e:
            print(f"❌ Error reading {filepath}: {e}")
            return None
    
    def detect(self, variance_window):
        if len(variance_window) < self.min_samples // 2:
            return {
                'status': 'INITIALIZING',
                'confidence': 0.0,
                'scores': {}
            }
        
        window = np.array(variance_window[-100:] if len(variance_window) >= 100 else variance_window)
        
        window_stats = {
            'mean': np.mean(window),
            'std': np.std(window),
            'min': np.min(window),
            'max': np.max(window),
            'median': np.median(window),
            'quantile_25': np.percentile(window, 25),
            'quantile_75': np.percentile(window, 75),
        }
        
        scores = {}
        for state, pattern in self.patterns.items():
            score = self._calculate_similarity(window_stats, pattern)
            scores[state] = score
        
        if not scores:
            return {
                'status': 'ERROR: No reference patterns',
                'confidence': 0.0,
                'scores': scores
            }
        
        best_state = max(scores, key=scores.get)
        best_score = scores[best_state]
        
        status_map = {
            'empty': '🟢 EMPTY ROOM',
            'occupied': '🔵 PERSON DETECTED',
            'multi': '🔴 MULTIPLE PEOPLE'
        }
        
        return {
            'status': status_map.get(best_state, 'UNKNOWN'),
            'state': best_state,
            'confidence': best_score,
            'scores': scores,
            'window_stats': window_stats
        }
    
    def _calculate_similarity(self, window_stats, pattern):
        weights = {
            'mean': 1.0,
            'std': 0.8,
            'median': 0.6,
            'quantile_25': 0.4,
            'quantile_75': 0.4,
        }
        
        total_distance = 0
        total_weight = 0
        
        for stat_name, weight in weights.items():
            if stat_name in pattern and stat_name in window_stats:
                pattern_range = pattern['max'] - pattern['min'] + 1e-6
                diff = abs(window_stats[stat_name] - pattern[stat_name]) / pattern_range
                distance = min(diff, 1.0)
                
                total_distance += distance * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0
        
        normalized_distance = total_distance / total_weight
        similarity = (1 - normalized_distance) * 100
        
        return max(0, min(100, similarity))
