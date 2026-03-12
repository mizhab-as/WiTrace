#!/usr/bin/env python3
"""
WiFi CSI Variance Analysis & Advanced Calibration Adjustment Tool
Identifies and corrects variance inversion and randomization issues
"""

import json
import numpy as np
import os

def analyze_variance_issues():
    """Detailed analysis of variance problems"""
    
    print("\n" + "="*80)
    print("🔍 WIFI CSI VARIANCE ANALYSIS REPORT")
    print("="*80 + "\n")
    
    # Load current calibration
    cal_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
    with open(cal_file, 'r') as f:
        cal_data = json.load(f)
    
    stats = cal_data['metadata']['statistics']
    
    print("📊 CURRENT DATA STATISTICS:")
    print("-" * 80)
    for state in sorted(stats.keys()):
        s = stats[state]
        print(f"\n{state.upper()}:")
        print(f"  • Mean variance: {s['mean']:.4f}")
        print(f"  • Std deviation: {s['std']:.4f}")
        print(f"  • Coefficient of Variation (CV): {s['coeff_variation']:.4f} ({s['coeff_variation']*100:.2f}%)")
        print(f"  • Range: {s['min']:.2f} - {s['max']:.2f}")
        print(f"  • Sample count: {s['count']}")
        print(f"  • IQR: {s['iqr']:.4f}")
    
    print("\n" + "="*80)
    print("⚠️  ISSUE IDENTIFICATION")
    print("="*80 + "\n")
    
    # Identify issues
    empty_mean = stats['empty']['mean']
    occupied_mean = stats.get('occupied', {}).get('mean', empty_mean)
    multi_mean = stats.get('multi', {}).get('mean', empty_mean)
    
    if empty_mean > occupied_mean or empty_mean > multi_mean:
        print("🔴 CRITICAL ISSUE: Inverted State Relationship")
        print("   Empty room shows HIGHER variance than occupied states!")
        print(f"   • Empty: {empty_mean:.4f}")
        print(f"   • Occupied: {occupied_mean:.4f}")
        print(f"   • Multi: {multi_mean:.4f}")
        print("\n   ROOT CAUSES:")
        print("   1. Possible mislabeling of training data (empty/occupied reversed)")
        print("   2. Movement/activity during 'empty' data collection")
        print("   3. CSI processing error (wrong variance calculation)")
        print("   4. WiFi reflection patterns (multipath effects)")
        print()
    
    # Check for high overall variance
    print("🔴 VARIANCE LEVELS:")
    for state in sorted(stats.keys()):
        cv = stats[state]['coeff_variation']
        if cv > 0.15:
            print(f"   • {state}: CV={cv:.4f} - HIGH variability (>15%)")
        elif cv > 0.10:
            print(f"   • {state}: CV={cv:.4f} - MODERATE variability (10-15%)")
        else:
            print(f"   • {state}: CV={cv:.4f} - GOOD stability (<10%)")
    
    print("\n" + "="*80)
    print("✅ RECOMMENDED SOLUTIONS")
    print("="*80 + "\n")
    
    print("SOLUTION 1: DATA RECALIBRATION")
    print("-" * 80)
    print("""
1. VERIFY DATA LABELS:
   □ Check data/myroom/empty.txt - Should be collected with room COMPLETELY empty
   □ Check data/myroom/occupied.txt - Should be person standing still
   □ Check data/myroom/multiple_people.txt - Should be 2+ people present
   
2. RECOLLECT IF NEEDED:
   python collect_raw_csi.py ../data2/myroom/empty_v2.txt 600
   - Keep room completely silent and still
   - No WiFi devices moving
   - 10+ minutes collection
   """)
    
    print("\nSOLUTION 2: ADVANCED FILTERING")
    print("-" * 80)
    print("""
The current calibration applies:
  • IQR-based outlier removal (removes 1.5*IQR outliers)
  • Savitzky-Golay smoothing (window=11, polyorder=3)
  • Percentile clipping (5th-95th percentile)

This reduces noise by ~20-30%, but if you still have high variance:

A) INCREASE FILTERING AGGRESSION:
   Edit auto_calibrate.py:
   - self.savgol_window = 15  (was 11)
   - self.percentile_cutoff = (10, 90)  (was 5, 95)
   - self.outlier_std_threshold = 2.5  (was 3.5)
    
B) ADD ADDITIONAL PROCESSING:
   - Apply power spectral density (PSD) filtering
   - Use median filtering instead of Savgol
   """)
    
    print("\nSOLUTION 3: ALGORITHMIC ADJUSTMENTS")
    print("-" * 80)
    print("""
Given the inverted relationship, consider these approaches:

A) REVERSE THRESHOLDS (if data is mislabeled):
   • Swap empty/occupied labels in training data
   • Or: Use max_energy instead of mean_energy
   
B) USE RATE-OF-CHANGE:
   • Instead of absolute variance: track variance CHANGE
   • Empty room: stable variance (low change)
   • Occupied: changing variance (high change)
   • This is more robust to baseline differences
   
C) USE SPECTRAL FEATURES:
   • Analyze frequency domain patterns
   • Empty: broadband spectrum
   • Occupied: peaks at breathing frequency (~0.2-0.4 Hz)
   """)
    
    print("\nSOLUTION 4: ADAPTIVE THRESHOLDING")
    print("-" * 80)
    print("""
Instead of fixed thresholds, adapt based on conditions:

1. BASELINE CALIBRATION (3 min per state):
   python calibrate_baseline.py
   
2. RUN DYNAMIC CALIBRATION (app.py):
   • Open http://localhost:8080
   • Use "Live Calibration" feature
   • Collect 2-3 min empty room data
   • Collect 2-3 min occupied room data
   • Algorithm adapts thresholds automatically
   
Alpha = 0.9 (high) for stable environments
Alpha = 0.7 (low) for changing conditions
   """)
    
    print("\nSOLUTION 5: MULTI-FEATURE FUSION")
    print("-" * 80)
    print("""
Instead of relying on single variance metric:

Features to combine:
1. Energy variance (current)
2. Spectral entropy (randomness of frequency)
3. Kurtosis (peakedness - breathing has high peaks)
4. 1st derivative (rate of change)
5. Zero-crossing rate (randomness)

The pattern_detector.py already extracts some of these!
Recent data extraction: 24 features per window
- These should give better discrimination
    """)


def generate_quick_fix():
    """Generate immediate calibration adjustments"""
    
    print("\n" + "="*80)
    print("⚡ QUICK FIX: ADJUSTED THRESHOLDS")
    print("="*80 + "\n")
    
    cal_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
    with open(cal_file, 'r') as f:
        cal_data = json.load(f)
    
    stats = cal_data['metadata']['statistics']
    
    # Given the inverted relationship, we need different logic
    print("Current issue: empty > occupied > multi (inverted)")
    print()
    print("OPTION 1: Use MINIMUM energy (inverse logic)")
    print("-" * 80)
    
    # If we invert the logic
    multi_min = stats.get('multi', {}).get('p5', 0)
    occupied_min = stats.get('occupied', {}).get('p5', 0)
    empty_min = stats.get('empty', {}).get('p5', 0)
    
    print(f"5th percentile values:")
    print(f"  Multi: {multi_min:.4f}")
    print(f"  Occupied: {occupied_min:.4f}")
    print(f"  Empty: {empty_min:.4f}")
    print()
    print("If MINIMUM values increase with occupancy:")
    threshold1 = (empty_min + occupied_min) / 2
    threshold2 = (occupied_min + multi_min) / 2
    print(f"  Threshold Empty→Occ: {threshold1:.4f}")
    print(f"  Threshold Occ→Multi: {threshold2:.4f}")
    print()
    
    print("OPTION 2: Use MEAN-based with inverted comparison")
    print("-" * 80)
    
    empty_mean = stats['empty']['mean']
    occupied_mean = stats.get('occupied', {}).get('mean', empty_mean)
    multi_mean = stats.get('multi', {}).get('mean', empty_mean)
    
    threshold1_mean = (empty_mean + occupied_mean) / 2
    threshold2_mean = (occupied_mean + multi_mean) / 2
    
    print(f"Mean values:")
    print(f"  Empty: {empty_mean:.4f}")
    print(f"  Occupied: {occupied_mean:.4f}")
    print(f"  Multi: {multi_mean:.4f}")
    print()
    print(f"  Threshold Empty→Occ: {threshold1_mean:.4f}")
    print(f"  Threshold Occ→Multi: {threshold2_mean:.4f}")
    print()
    
    print("OPTION 3: Use Variance ratio (most robust)")
    print("-" * 80)
    
    empty_var = stats['empty']['variance']
    occupied_var = stats.get('occupied', {}).get('variance', empty_var)
    multi_var = stats.get('multi', {}).get('variance', empty_var)
    
    ratio_occ = occupied_var / empty_var if empty_var > 0 else 1
    ratio_multi = multi_var / empty_var if empty_var > 0 else 1
    
    print(f"Variance ratios (relative to empty):")
    print(f"  Occupied/Empty: {ratio_occ:.4f}")
    print(f"  Multi/Empty: {ratio_multi:.4f}")
    print()
    print("This removes absolute scale - only relative changes matter!")
    print()


def provide_detailed_recommendations():
    """Provide specific next steps"""
    
    print("="*80)
    print("📋 RECOMMENDED NEXT STEPS")
    print("="*80 + "\n")
    
    print("IMMEDIATE (TODAY):")
    print("""
1. Run live calibration in app.py:
   - Keep room empty for 2 minutes
   - Move around for 2 minutes
   - System learns actual thresholds
   
2. Test detection accuracy:
   - Go in/out of room
   - Check if detection matches reality
   - Note false positives/negatives
""")
    
    print("\nSHORT TERM (THIS WEEK):")
    print("""
1. Recollect reference data if live calibration doesn't help:
   python collect_raw_csi.py ../data2/myroom/empty_clean.txt 600 &
   python collect_raw_csi.py ../data2/myroom/occupied_v2.txt 600 &
   
2. Verify data quality:
   - Check for WiFi interference
   - Check for movement during empty collection
   - Ensure router positioning is stable
   
3. Use enhanced multi-feature detection:
   - pattern_detector.py already uses 24 features
   - These should be more stable than single variance
""")
    
    print("\nMEDIUM TERM (2-4 WEEKS):")
    print("""
1. Implement adaptive baseline:
   - System learns environment baseline
   - Continuously updates thresholds
   - Compensates for WiFi changes
   
2. Implement detection smoothing:
   - Use hysteresis (already done in app.py)
   - Increase detection window
   - Reduce false positives
   
3. Add confidence scoring:
   - Low confidence detection → hold previous state
   - High confidence detection → change state
""")


if __name__ == '__main__':
    analyze_variance_issues()
    generate_quick_fix()
    provide_detailed_recommendations()
    
    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80 + "\n")
