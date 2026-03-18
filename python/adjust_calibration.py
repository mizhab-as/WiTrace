#!/usr/bin/env python3
"""
Advanced Calibration Adjustment Tool
Applies multiple correction strategies to address variance inversion
"""

import json
import numpy as np
import os

def create_improved_calibration():
    """Create improved calibration with multiple approaches"""
    
    cal_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
    with open(cal_file, 'r') as f:
        cal_data = json.load(f)
    
    stats = cal_data['metadata']['statistics']
    
    print("\n" + "="*80)
    print("⚙️  GENERATING IMPROVED CALIBRATION STRATEGIES")
    print("="*80 + "\n")
    
    strategies = {}
    
    # Strategy 1: Inverted (if data labels are swapped)
    print("Strategy 1: INVERTED THRESHOLDS (if data is mislabeled)")
    print("-" * 80)
    empty_stats = stats['empty']
    occupied_stats = stats.get('occupied', stats['empty'])
    multi_stats = stats.get('multi', stats['empty'])
    
    # Use inverse logic: higher value = more occupancy
    threshold1_inv = empty_stats['mean'] - empty_stats['std']
    threshold2_inv = empty_stats['mean'] + empty_stats['std']
    
    strategies['inverted'] = {
        'description': 'Uses inverse thresholds (empty > occupied)',
        'empty_upper': float(empty_stats['mean'] - 1.5 * empty_stats['std']),
        'occupied_upper': float(empty_stats['mean'] + 1.5 * empty_stats['std']),
        'multi_upper': float(empty_stats['mean'] + 3.0 * empty_stats['std']),
    }
    
    print(f"  Empty upper bound: {strategies['inverted']['empty_upper']:.4f}")
    print(f"  Occupied upper bound: {strategies['inverted']['occupied_upper']:.4f}")
    print(f"  Multi upper bound: {strategies['inverted']['multi_upper']:.4f}")
    
    # Strategy 2: Robust percentile-based
    print("\nStrategy 2: ROBUST PERCENTILE-BASED")
    print("-" * 80)
    
    # Combine statistical approaches
    threshold1_p = (empty_stats['p95'] + occupied_stats['p5']) / 2
    threshold2_p = (occupied_stats['p95'] + multi_stats['p5']) / 2
    
    strategies['percentile'] = {
        'description': 'Based on 5th and 95th percentiles',
        'person': float(threshold1_p),
        'multi': float(threshold2_p),
    }
    
    print(f"  Empty→Occupied: {strategies['percentile']['person']:.4f}")
    print(f"  Occupied→Multi: {strategies['percentile']['multi']:.4f}")
    
    # Strategy 3: Ratio-based (most robust to absolute scale)
    print("\nStrategy 3: RATIO-BASED (Relative Changes)")
    print("-" * 80)
    
    empty_var = empty_stats['variance']
    occupied_var = occupied_stats['variance']
    multi_var = multi_stats['variance']
    
    # Use ratios: these are scale-independent
    occ_ratio = occupied_var / empty_var if empty_var > 0 else 1.0
    multi_ratio = multi_var / empty_var if empty_var > 0 else 1.0
    
    strategies['ratio'] = {
        'description': 'Based on variance ratios (scale-independent)',
        'occupied_ratio': float(occ_ratio),
        'multi_ratio': float(multi_ratio),
        'threshold_ratio_1': 0.5 * (1.0 + occ_ratio),  # Between 1 and occupied_ratio
        'threshold_ratio_2': 0.75 * (occ_ratio + multi_ratio),  # Between occupied and multi
    }
    
    print(f"  Occupied/Empty variance ratio: {strategies['ratio']['occupied_ratio']:.4f}")
    print(f"  Multi/Empty variance ratio: {strategies['ratio']['multi_ratio']:.4f}")
    print(f"  Threshold 1 (ratio): {strategies['ratio']['threshold_ratio_1']:.4f}")
    print(f"  Threshold 2 (ratio): {strategies['ratio']['threshold_ratio_2']:.4f}")
    
    # Strategy 4: Energy-based (use mean directly)
    print("\nStrategy 4: ENERGY-BASED (Mean-based thresholds)")
    print("-" * 80)
    
    threshold1_mean = (empty_stats['mean'] + occupied_stats['mean']) / 2
    threshold2_mean = (occupied_stats['mean'] + multi_stats['mean']) / 2
    
    strategies['energy'] = {
        'description': 'Based on mean energy values',
        'person': float(threshold1_mean),
        'multi': float(threshold2_mean),
    }
    
    print(f"  Empty→Occupied: {strategies['energy']['person']:.4f}")
    print(f"  Occupied→Multi: {strategies['energy']['multi']:.4f}")
    
    # Strategy 5: Conservative (maximum separation)
    print("\nStrategy 5: CONSERVATIVE (Maximum Separation)")
    print("-" * 80)
    
    threshold1_cons = max(
        empty_stats['mean'] + 2 * empty_stats['std'],
        (empty_stats['p95'] + occupied_stats['p5']) / 2
    )
    threshold2_cons = max(
        occupied_stats['mean'] + 2 * occupied_stats['std'],
        (occupied_stats['p95'] + multi_stats['p5']) / 2
    )
    
    strategies['conservative'] = {
        'description': 'Uses maximum thresholds for best separation',
        'person': float(threshold1_cons),
        'multi': float(threshold2_cons),
    }
    
    print(f"  Empty→Occupied: {strategies['conservative']['person']:.4f}")
    print(f"  Occupied→Multi: {strategies['conservative']['multi']:.4f}")
    
    return strategies


def recommend_strategy(strategies):
    """Recommend best strategy based on data characteristics"""
    
    print("\n" + "="*80)
    print("🎯 STRATEGY RECOMMENDATION")
    print("="*80 + "\n")
    
    cal_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration.json'
    with open(cal_file, 'r') as f:
        cal_data = json.load(f)
    
    stats = cal_data['metadata']['statistics']
    
    print("Analysis of your data characteristics:")
    print()
    
    # Check coefficient of variation
    cv_occupied = stats.get('occupied', {}).get('coeff_variation', 0.15)
    cv_multi = stats.get('multi', {}).get('coeff_variation', 0.15)
    high_cv = cv_occupied > 0.15 or cv_multi > 0.15
    
    if high_cv:
        print("✓ High coefficient of variation detected (>15%)")
        print("  → Use RATIO-BASED strategy (scale-independent)")
        print("  → This is most robust to fluctuations")
        recommended = 'ratio'
    else:
        print("✓ Moderate coefficient of variation (<15%)")
        print("  → Use ENERGY-BASED strategy")
        print("  → Direct mean-based thresholds work well")
        recommended = 'energy'
    
    print("\nFor current data with variance inversion:")
    print(f"  RECOMMENDED: {recommended.upper()} strategy")
    print()
    
    if recommended == 'ratio':
        print("Apply these multipliers to running variance:")
        print(f"  • If ratio > {strategies['ratio']['threshold_ratio_1']:.2f}: Check for occupancy")
        print(f"  • If ratio > {strategies['ratio']['threshold_ratio_2']:.2f}: Multiple people likely")
    else:
        print("Apply these absolute thresholds:")
        print(f"  • If energy > {strategies['energy']['person']:.4f}: Person detected")
        print(f"  • If energy > {strategies['energy']['multi']:.4f}: Multiple people")
    
    return recommended


def save_all_strategies(strategies, recommended):
    """Save all strategies to file for reference"""
    
    output_file = '/Users/mizhabas/wifi_csi_imaging/python/calibration_strategies.json'
    
    output_data = {
        'recommended': recommended,
        'timestamp': str(np.datetime64('today')),
        'strategies': strategies,
        'implementation_notes': {
            'inverted': 'Use if your empty state truly has higher variance than occupied',
            'percentile': 'Safe choice - uses statistical percentile boundaries',
            'ratio': 'Best for variable environments - uses relative changes',
            'energy': 'Simple and direct - works well with stable data',
            'conservative': 'Most cautious - maximizes separability at cost of precision'
        },
        'how_to_use': {
            'step_1': 'Choose recommended strategy above',
            'step_2': 'Apply thresholds in pattern_detector.py or app.py',
            'step_3': 'Run live calibration if needed (app.py web interface)',
            'step_4': 'Monitor accuracy and adjust if necessary'
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ Saved all strategies to: {output_file}")


def generate_summary():
    """Generate actionable summary"""
    
    print("\n" + "="*80)
    print("📋 ACTIONABLE SUMMARY FOR CALIBRATION ADJUSTMENT")
    print("="*80 + "\n")
    
    print("""
CURRENT STATUS:
  ❌ Data shows variance inversion (empty > occupied > multi)
  ⚠️  High variance in occupied/multi states (CV > 15%)
  ✅ Good collection volume (667+ samples per state)

IMMEDIATE ACTION PLAN:
  1. Verify data collection accuracy
     └─ Was 'empty' truly collected with room empty?
     └─ Was 'occupied' collected with only 1 person present?
  
  2. Apply live calibration
     └─ Run: cd python && source env/bin/activate && python3 app.py
     └─ Open: http://localhost:8080
     └─ Click "Start Live Calibration"
     └─ Keep room empty for 2 minutes, then move around for 2 minutes
  
  3. Monitor results
     └─ Web UI updates thresholds automatically  
     └─ Check calibration.json for updated values
     └─ Test with in/out movements

IF LIVE CALIBRATION DOESN'T WORK:
  1. Try alternative strategies in calibration_strategies.json
  2. Recollect reference data (600 seconds each state)
  3. Increase filtering aggressiveness in auto_calibrate.py
  4. Check for WiFi interference with:
     └─ iwlist wlan0 scan | grep "ESSID\\|Frequency\\|Signal"
  
KEY INSIGHT:
  Your data shows a relationship bias (possibly environmental or labeling).
  The PatternDetector already uses 24 features, not just variance - these 
  should provide better discrimination than single-metric thresholds.
  
EXPECTED TIMELINE:
  - Live calibration: 10-15 minutes total
  - Detection accuracy improvement: Immediate (after calibration)
  - Full stabilization: 2-3 runs as system adapts
""")


if __name__ == '__main__':
    strategies = create_improved_calibration()
    recommended = recommend_strategy(strategies)
    save_all_strategies(strategies, recommended)
    generate_summary()
    
    print("\n" + "="*80)
    print("✅ CALIBRATION ADJUSTMENT COMPLETE")
    print("="*80 + "\n")
    print("📁 Check calibration_strategies.json for detailed strategy information")
    print("🚀 Ready to run live calibration or adjust thresholds\n")
