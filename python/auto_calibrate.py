#!/usr/bin/env python3
"""
Enhanced Auto-Calibration Tool for WiFi CSI Imaging
Addresses variance, fluctuation, and randomization issues by:
1. Loading and analyzing all available training data
2. Applying noise filtering and smoothing
3. Computing robust statistics
4. Generating adjusted calibration thresholds
5. Providing detailed analysis and recommendations
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from scipy import signal
from scipy.stats import variation

class CSICalibrator:
    def __init__(self, data_folders=None):
        """Initialize calibrator with data folders"""
        if data_folders is None:
            data_folders = [
                '/Users/mizhabas/wifi_csi_imaging/data',
                '/Users/mizhabas/wifi_csi_imaging/data2'
            ]
        self.data_folders = data_folders
        self.calibration_output = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
        
        # Calibration parameters
        self.target_bins = 64
        self.window_frames = 120
        self.window_step = 20
        self.min_frames = 80
        
        # Noise filtering parameters (OPTIMIZED FOR INVERTED VARIANCE)
        self.savgol_window = 19            # Larger smoothing window for high variance states
        self.savgol_polyorder = 3          # Balanced polynomial
        self.outlier_std_threshold = 1.0   # Aggressive outlier removal
        self.percentile_cutoff = (10, 90)  # Remove extreme 10% each side
        
        # Analysis results
        self.raw_data = {}
        self.filtered_data = {}
        self.statistics = {}
    
    def load_all_data(self):
        """Load all available CSI data from configured folders"""
        print("\n" + "="*70)
        print("STEP 1: Loading All Available Data")
        print("="*70)
        
        state_mapping = {
            'empty.txt': 'empty',
            'occupied.txt': 'occupied',
            'multiple_people.txt': 'multi',
            'multi_occ.txt': 'multi',
            'walking.txt': 'movement',
        }
        
        for folder in self.data_folders:
            if not os.path.exists(folder):
                print(f"⚠️  Folder not found: {folder}")
                continue
            
            # Search for data files recursively
            for root, dirs, files in os.walk(folder):
                for filename, state in state_mapping.items():
                    if filename in files:
                        filepath = os.path.join(root, filename)
                        print(f"\n📂 Analyzing: {filepath}")
                        data = self._extract_csi_data(filepath, state)
                        if data is not None:
                            key = f"{state}_{os.path.relpath(root, folder)}"
                            self.raw_data[key] = data
                            print(f"   ✅ Loaded: {len(data['energies'])} frames")
                            print(f"   📊 Energy range: {np.min(data['energies']):.2f} - {np.max(data['energies']):.2f}")
                            print(f"   📈 Variance: {np.var(data['energies']):.4f}")
                            print(f"   🔢 Mean: {np.mean(data['energies']):.2f}")
    
    def _extract_csi_data(self, filepath, state):
        """Extract variance values from data file (decimal format or CSI_DATA format)"""
        frame_energies = []
        frame_signatures = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Format 1: CSI_DATA format (raw CSI values)
                    if line.startswith('CSI_DATA:'):
                        try:
                            values_str = line.split(':', 1)[1].strip()
                            values = [int(v) for v in values_str.split()]
                            if values:
                                energy = np.mean(np.abs(values))
                                frame_energies.append(energy)
                                sig = self._frame_signature(values)
                                if sig is not None:
                                    frame_signatures.append(sig)
                        except ValueError:
                            continue
                    
                    # Format 2: Direct variance values (decimal numbers)
                    else:
                        try:
                            value = float(line)
                            frame_energies.append(value)
                        except ValueError:
                            continue
            
            if len(frame_energies) < self.min_frames:
                print(f"   ❌ Insufficient frames ({len(frame_energies)} < {self.min_frames})")
                return None
            
            return {
                'state': state,
                'energies': np.array(frame_energies),
                'signatures': frame_signatures,
                'count': len(frame_energies)
            }
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            return None
    
    def _frame_signature(self, values):
        """Compute frame signature using FFT"""
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
    
    def filter_and_smooth(self):
        """Apply filtering and smoothing to reduce noise"""
        print("\n" + "="*70)
        print("STEP 2: Filtering and Smoothing Data")
        print("="*70)
        
        for key, data in self.raw_data.items():
            print(f"\n🔧 Processing: {key}")
            energies = data['energies'].copy()
            
            # 1. Remove outliers using IQR method
            Q1, Q3 = np.percentile(energies, [25, 75])
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outlier_mask = (energies < lower_bound) | (energies > upper_bound)
            outlier_count = np.sum(outlier_mask)
            energies_no_outliers = energies[~outlier_mask]
            
            if outlier_count > 0:
                print(f"   🚫 Removed {outlier_count} outliers ({100*outlier_count/len(energies):.1f}%)")
            
            # 2. Apply Savitzky-Golay filter
            if len(energies_no_outliers) > self.savgol_window:
                filtered = signal.savgol_filter(energies_no_outliers, self.savgol_window, self.savgol_polyorder)
                print(f"   ✅ Applied Savitzky-Golay filter")
            else:
                filtered = energies_no_outliers
            
            # 3. Clip to percentile range for extreme value handling
            p_low, p_high = np.percentile(filtered, self.percentile_cutoff)
            filtered_clipped = np.clip(filtered, p_low, p_high)
            
            self.filtered_data[key] = {
                'raw_count': len(energies),
                'filtered_count': len(filtered),
                'outliers_removed': outlier_count,
                'energies': filtered_clipped,
                'state': data['state']
            }
            
            print(f"   📊 Before: mean={np.mean(energies):.2f}, std={np.std(energies):.2f}")
            print(f"   📊 After:  mean={np.mean(filtered_clipped):.2f}, std={np.std(filtered_clipped):.2f}")
            print(f"   📉 Noise reduction: {(np.std(energies) - np.std(filtered_clipped))/np.std(energies)*100:.1f}%")
    
    def compute_statistics(self):
        """Compute robust statistics for each state"""
        print("\n" + "="*70)
        print("STEP 3: Computing Robust Statistics")
        print("="*70)
        
        state_stats = {}
        
        for key, data in self.filtered_data.items():
            state = data['state']
            energies = data['energies']
            
            if state not in state_stats:
                state_stats[state] = {
                    'all_energies': [],
                    'count': 0
                }
            
            state_stats[state]['all_energies'].extend(energies)
            state_stats[state]['count'] += len(energies)
        
        print()
        for state in sorted(state_stats.keys()):
            combined = np.array(state_stats[state]['all_energies'])
            
            mean = np.mean(combined)
            median = np.median(combined)
            std = np.std(combined)
            variance = np.var(combined)
            cv = std / (mean + 1e-9)  # Coefficient of variation
            
            q1, q2, q3 = np.percentile(combined, [25, 50, 75])
            p5, p95 = np.percentile(combined, [5, 95])
            
            self.statistics[state] = {
                'mean': float(mean),
                'median': float(median),
                'std': float(std),
                'variance': float(variance),
                'coeff_variation': float(cv),
                'min': float(np.min(combined)),
                'max': float(np.max(combined)),
                'q1': float(q1),
                'q2': float(q2),
                'q3': float(q3),
                'p5': float(p5),
                'p95': float(p95),
                'count': int(state_stats[state]['count']),
                'iqr': float(q3 - q1)
            }
            
            print(f"\n📊 Statistics for '{state}':")
            print(f"   Samples: {self.statistics[state]['count']}")
            print(f"   Mean: {mean:.4f}, Median: {median:.4f}")
            print(f"   Std Dev: {std:.4f}, Variance: {variance:.4f}")
            print(f"   Coeff. Variation: {cv:.4f} ({cv*100:.2f}%)")
            print(f"   Range: [{np.min(combined):.2f}, {np.max(combined):.2f}]")
            print(f"   Quartiles: Q1={q1:.2f}, Q2={q2:.2f}, Q3={q3:.2f}")
            print(f"   Percentiles: 5th={p5:.2f}, 95th={p95:.2f}")
    
    def compute_thresholds(self):
        """Compute optimal separation thresholds"""
        print("\n" + "="*70)
        print("STEP 4: Computing Optimal Thresholds")
        print("="*70 + "\n")
        
        thresholds = {}
        
        if 'empty' not in self.statistics:
            print("❌ No 'empty' state data found!")
            return thresholds
        
        empty_stats = self.statistics['empty']
        
        # Threshold 1: Empty vs. Occupied
        # Use upper boundary of empty + buffer for separation
        if 'occupied' in self.statistics:
            occupied_stats = self.statistics['occupied']
            
            # Method 1: Mean + std of empty state
            threshold1_method1 = empty_stats['mean'] + 2.0 * empty_stats['std']
            
            # Method 2: Mean - std of occupied state (conservative)
            threshold1_method2 = occupied_stats['mean'] - 1.0 * occupied_stats['std']
            
            # Method 3: Midpoint between distributions
            threshold1_method3 = (empty_stats['p95'] + occupied_stats['p5']) / 2
            
            # Take the most conservative (highest value that protects empty)
            threshold_person = max(threshold1_method1, threshold1_method3)
            
            print(f"👤 Threshold: Empty ↔ Occupied/Person")
            print(f"   Method 1 (empty mean + 2*std): {threshold1_method1:.4f}")
            print(f"   Method 2 (occupied mean - std): {threshold1_method2:.4f}")
            print(f"   Method 3 (percentile midpoint): {threshold1_method3:.4f}")
            print(f"   ✅ Selected: {threshold_person:.4f}")
            
            thresholds['person'] = float(threshold_person)
        else:
            print("⚠️  No 'occupied' data - using default threshold")
            thresholds['person'] = float(empty_stats['mean'] + 2.0 * empty_stats['std'])
        
        # Threshold 2: Occupied vs. Multiple People
        if 'multi' in self.statistics:
            multi_stats = self.statistics['multi']
            
            # Method 1: Mean + std of occupied state
            if 'occupied' in self.statistics:
                occupied_stats = self.statistics['occupied']
                threshold2_method1 = occupied_stats['mean'] + 2.0 * occupied_stats['std']
            else:
                threshold2_method1 = float('inf')
            
            # Method 2: Midpoint between occupied and multi
            if 'occupied' in self.statistics:
                threshold2_method2 = (occupied_stats['p95'] + multi_stats['p5']) / 2
            else:
                threshold2_method2 = float('inf')
            
            # Method 3: Mean - std of multi state (conservative)
            threshold2_method3 = multi_stats['mean'] - 1.0 * multi_stats['std']
            
            # Take the most conservative value
            threshold_multi = min(threshold2_method1, threshold2_method2, threshold2_method3)
            threshold_multi = max(thresholds.get('person', 0) + 0.5, threshold_multi)
            
            print(f"\n👥 Threshold: Occupied ↔ Multiple People")
            if 'occupied' in self.statistics:
                print(f"   Method 1 (occupied mean + 2*std): {threshold2_method1:.4f}")
                print(f"   Method 2 (percentile midpoint): {threshold2_method2:.4f}")
            print(f"   Method 3 (multi mean - std): {threshold2_method3:.4f}")
            print(f"   ✅ Selected: {threshold_multi:.4f}")
            
            thresholds['multi'] = float(threshold_multi)
        else:
            print("⚠️  No 'multi' data - using derived threshold")
            thresholds['multi'] = float(thresholds.get('person', 4.64) + 1.0)
        
        return thresholds
    
    def provide_recommendations(self):
        """Provide detailed calibration recommendations"""
        print("\n" + "="*70)
        print("STEP 5: Calibration Recommendations")
        print("="*70 + "\n")
        
        recommendations = []
        
        if not self.statistics:
            print("⚠️  No statistics available for recommendations")
            return recommendations
        
        # Check coefficient of variation (measure of noise/volatility)
        for state, stats in self.statistics.items():
            cv = stats['coeff_variation']
            
            if cv > 0.4:
                recommendations.append({
                    'state': state,
                    'issue': 'HIGH VARIANCE',
                    'cv': cv,
                    'suggestion': 'Signal shows high fluctuation. Consider: more stable room conditions, longer calibration window, or better antenna positioning.'
                })
            elif cv > 0.2:
                recommendations.append({
                    'state': state,
                    'issue': 'MODERATE VARIANCE',
                    'cv': cv,
                    'suggestion': 'Normal variance. System should work well with current configuration.'
                })
            else:
                recommendations.append({
                    'state': state,
                    'issue': 'LOW VARIANCE',
                    'cv': cv,
                    'suggestion': 'Excellent signal stability. System should have high accuracy.'
                })
        
        # Print recommendations
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['state'].upper()} - {rec['issue']}")
            print(f"   CV={rec['cv']:.4f}")
            print(f"   → {rec['suggestion']}")
            print()
        
        # Overall recommendations
        print("🎯 OVERALL RECOMMENDATIONS:")
        print()
        print("1. DATA COLLECTION:")
        print("   - Collect 10+ minutes of data for each state")
        print("   - Ensure stable environmental conditions during collection")
        print("   - Position router away from large moving objects")
        print()
        
        print("2. FILTERING:")
        print("   - System now applies Savitzky-Golay filtering")
        print("   - Outliers are removed using IQR method")
        print("   - This reduces effective variance by up to 30-40%")
        print()
        
        print("3. WINDOW SIZE:")
        print("   - Current: 120-frame window for feature extraction")
        print("   - Increase to 150-180 if variance persists")
        print("   - Decrease to 80-100 for faster response")
        print()
        
        print("4. ADAPTIVE CALIBRATION:")
        print("   - Use app.py's live calibration feature")
        print("   - Run calibration for 120-180 seconds per state")
        print("   - Set alpha=0.85 for stable blending")
        print()
        
        print("5. VALIDATION:")
        print("   - Test thresholds with new data")
        print("   - Adjust if false positive/negative rates > 10%")
        print("   - Re-calibrate monthly for environment changes")
        print()
    
    def save_calibration(self, thresholds):
        """Save calibration to JSON file"""
        print("\n" + "="*70)
        print("STEP 6: Saving Calibration")
        print("="*70 + "\n")
        
        calibration_data = {
            'empty': thresholds.get('person', 4.64),
            'multi': thresholds.get('multi', 5.37),
            'metadata': {
                'version': '2.0',
                'timestamp': str(np.datetime64('today')),
                'method': 'statistical-robust',
                'data_sources': list(self.raw_data.keys()),
                'statistics': self.statistics
            }
        }
        
        try:
            output_dir = os.path.dirname(self.calibration_output)
            os.makedirs(output_dir, exist_ok=True)
            
            with open(self.calibration_output, 'w') as f:
                json.dump(calibration_data, f, indent=2)
            
            print(f"✅ Calibration saved to: {self.calibration_output}")
            print()
            print("📋 Saved Thresholds:")
            print(f"   Empty ↔ Person: {thresholds.get('person', 4.64):.4f}")
            print(f"   Person ↔ Multiple: {thresholds.get('multi', 5.37):.4f}")
            print()
            
        except Exception as e:
            print(f"❌ Error saving calibration: {e}")
    
    def run(self):
        """Run complete calibration process"""
        print("\n")
        print("╔════════════════════════════════════════════════════════════════╗")
        print("║  🎯 WiFi CSI ENHANCED AUTO-CALIBRATION                        ║")
        print("║     Version 2.0 - Noise-Aware Calibration                     ║")
        print("╚════════════════════════════════════════════════════════════════╝")
        
        # Run calibration pipeline
        self.load_all_data()
        
        if not self.raw_data:
            print("\n❌ No data files found! Please ensure data files exist in:")
            for folder in self.data_folders:
                print(f"   - {folder}")
            return False
        
        self.filter_and_smooth()
        self.compute_statistics()
        thresholds = self.compute_thresholds()
        self.provide_recommendations()
        self.save_calibration(thresholds)
        
        print("╔════════════════════════════════════════════════════════════════╗")
        print("║ ✅ CALIBRATION COMPLETE                                       ║")
        print("║                                                                ║")
        print("║ Next steps:                                                    ║")
        print("║ 1. Run app.py to start the web server                          ║")
        print("║ 2. Perform live calibration if accuracy is still not optimal   ║")
        print("║ 3. Monitor detection logs for false positives/negatives        ║")
        print("╚════════════════════════════════════════════════════════════════╝")
        print()
        
        return True


def main():
    """Main entry point"""
    calibrator = CSICalibrator()
    success = calibrator.run()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
