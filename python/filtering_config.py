#!/usr/bin/env python3
"""
Enhanced Filtering Configuration Tool
Allows adjustment of filtering parameters to reduce variance/fluctuations
"""

import json
import os

class FilteringConfigManager:
    def __init__(self):
        self.config_file = '/Users/mizhabas/wifi_csi_imaging/python/filtering_config.json'
        self.preset_configs = {
            'light': {
                'name': 'Light Filtering (Fast response, more noise)',
                'savgol_window': 7,
                'savgol_polyorder': 2,
                'outlier_multiplier': 2.0,
                'percentile_cutoff': [1, 99],
                'use_median_filter': False,
                'median_window': 5,
                'use_adaptive_filter': False,
            },
            'standard': {
                'name': 'Standard Filtering (Balanced)',
                'savgol_window': 11,
                'savgol_polyorder': 3,
                'outlier_multiplier': 1.5,
                'percentile_cutoff': [5, 95],
                'use_median_filter': False,
                'median_window': 5,
                'use_adaptive_filter': False,
            },
            'aggressive': {
                'name': 'Aggressive Filtering (High stability, slower response)',
                'savgol_window': 15,
                'savgol_polyorder': 3,
                'outlier_multiplier': 1.0,
                'percentile_cutoff': [10, 90],
                'use_median_filter': True,
                'median_window': 7,
                'use_adaptive_filter': False,
            },
            'ultra': {
                'name': 'Ultra Filtering (Maximum noise reduction)',
                'savgol_window': 21,
                'savgol_polyorder': 4,
                'outlier_multiplier': 1.0,
                'percentile_cutoff': [15, 85],
                'use_median_filter': True,
                'median_window': 9,
                'use_adaptive_filter': True,
            }
        }
    
    def print_presets(self):
        """Display available filtering presets"""
        print("\n" + "="*80)
        print("🔧 FILTERING CONFIGURATION PRESETS")
        print("="*80 + "\n")
        
        for name, config in self.preset_configs.items():
            print(f"{name.upper()}: {config['name']}")
            print(f"  Savitzky-Golay: window={config['savgol_window']}, polyorder={config['savgol_polyorder']}")
            print(f"  Outlier handling: {config['outlier_multiplier']}x IQR")
            print(f"  Percentile clipping: {config['percentile_cutoff'][0]}-{config['percentile_cutoff'][1]}th")
            print(f"  Median filter: {'Yes' if config['use_median_filter'] else 'No'}")
            print(f"  Adaptive: {'Yes' if config['use_adaptive_filter'] else 'No'}")
            print()
    
    def print_recommendations(self):
        """Print filtering recommendations based on data analysis"""
        print("\n" + "="*80)
        print("📊 FILTERING RECOMMENDATIONS FOR YOUR DATA")
        print("="*80 + "\n")
        
        print("Your data characteristics:")
        print("  • Coefficient of Variation (CV): 3.9% - 15.9%")
        print("  • Variance range: 0.18 - 2.32")
        print("  • State: Moderate to high variance")
        print()
        
        print("RECOMMENDED APPROACH:")
        print("-" * 80)
        print("""
Based on your variance analysis:

1. START WITH: AGGRESSIVE preset
   └─ Larger filtering window smooths out fluctuations
   └─ Better separation between states
   └─ Acceptable response time for occupancy detection
   
2. IF DETECTION IS SLUGGISH: Move to STANDARD
   └─ Faster response to real changes
   └─ Trade some noise reduction for reactivity
   
3. IF STILL TOO NOISY: Move to ULTRA
   └─ Maximum filtering
   └─ Use if environment is very noisy/interference-prone
   └─ Will have 2-3 second response lag

4. IF WORKING WELL: KEEP CURRENT
   └─ Monitor false positives/negatives
   └─ Adjust alpha parameter in live calibration
""")
    
    def save_preset(self, preset_name):
        """Save a preset configuration"""
        if preset_name not in self.preset_configs:
            print(f"❌ Unknown preset: {preset_name}")
            return False
        
        config = self.preset_configs[preset_name].copy()
        
        output_data = {
            'selected_preset': preset_name,
            'description': config['name'],
            'config': config,
            'version': '2.0',
            'timestamp': str(__import__('datetime').datetime.now()),
            'usage': {
                'python_script': 'Update auto_calibrate.py __init__ with these values',
                'web_ui': 'Live calibration uses app.py default parameters',
                'next_step': 'Run: python3 auto_calibrate.py to apply'
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"✅ Saved '{preset_name}' configuration")
        return True
    
    def print_custom_guide(self):
        """Print guide for custom configuration"""
        print("\n" + "="*80)
        print("⚙️  CUSTOM CONFIGURATION GUIDE")
        print("="*80 + "\n")
        
        print("""
To create a CUSTOM filtering configuration:

1. EDIT filtering_config.json manually, or
2. MODIFY auto_calibrate.py directly:

   In auto_calibrate.py, CSICalibrator.__init__ method:
   
   # NOISE FILTERING PARAMETERS
   self.savgol_window = XX           # Higher = more smoothing (must be odd)
   self.savgol_polyorder = XX        # 2-4 recommended
   self.outlier_std_threshold = XX   # 1.0-4.0 (lower = remove more outliers)
   self.percentile_cutoff = (A, B)   # Exclude A% bottom, B% top values

PARAMETER EFFECTS:

• savgol_window:
  - 7: Fast response, less smoothing
  - 11: Balanced
  - 15-21: Heavy smoothing, slower response

• savgol_polyorder:
  - 2: Maximum smoothing
  - 3: Balanced
  - 4+: Preserves more detail

• outlier_std_threshold:
  - 1.0: Remove extreme outliers (aggressive)
  - 1.5: Medium removal
  - 3.5+: Keep most data points

• percentile_cutoff:
  - (1, 99): Keep extreme values
  - (5, 95): Balanced
  - (10, 90): Remove 20% of extremes

EXAMPLE: For very noisy environment:

    self.savgol_window = 17
    self.savgol_polyorder = 3
    self.outlier_std_threshold = 1.0
    self.percentile_cutoff = (10, 90)

Then run: python3 auto_calibrate.py
""")
    
    def generate_report(self):
        """Generate comprehensive filtering report"""
        print("\n" + "="*80)
        print("📋 COMPLETE FILTERING ADJUSTMENT REPORT")
        print("="*80 + "\n")
        
        print("FOR YOUR SPECIFIC CASE (High variance data):")
        print()
        print("PROBLEM:")
        print("  • Occupied/Multi states show 14-16% coefficient of variation")
        print("  • Raw packet fluctuations are randomized")
        print("  • Need better noise reduction without losing response speed")
        print()
        
        print("SOLUTION:")
        print("  1. Use AGGRESSIVE filtering preset immediately")
        print("  2. Run auto-calibration: python3 auto_calibrate.py")
        print("  3. Test with live calibration in web UI")
        print("  4. If needed, adjust to ULTRA preset")
        print()
        
        print("IMPLEMENTATION STEPS:")
        print("""
Step 1: Apply Aggressive Filtering
  $ cd /Users/mizhabas/wifi_csi_imaging/python
  $ python3 -c "from adjust_calibration import *; 
    m = FilteringConfigManager(); 
    m.save_preset('aggressive')"

Step 2: Update Calibration
  $ source env/bin/activate
  $ python3 auto_calibrate.py

Step 3: Test Live Calibration
  $ python3 app.py
  Visit: http://localhost:8080
  Click: "Start Live Calibration"
  Keep room empty for 2 min, then move for 2 min

Step 4: Monitor Results
  Check: calibration.json for updated thresholds
  Test: Walk in/out of room multiple times
  Note: Detection accuracy and false positives
""")


def main():
    """Main menu"""
    print("\n" + "="*80)
    print("🎚️  FILTERING CONFIGURATION MANAGER")
    print("="*80 + "\n")
    
    manager = FilteringConfigManager()
    
    manager.print_presets()
    manager.print_recommendations()
    manager.print_custom_guide()
    manager.generate_report()
    
    # Save aggressive preset as default for high-variance scenarios
    print("\n" + "="*80)
    print("💾 APPLYING RECOMMENDED CONFIGURATION")
    print("="*80 + "\n")
    
    manager.save_preset('aggressive')
    
    print("""
Next steps:

1. Run auto-calibration with new filtering:
   python3 auto_calibrate.py

2. Review the updated calibration.json

3. Test with live calibration:
   python3 app.py
   Open http://localhost:8080
   
4. Fine-tune if needed:
   Adjust filtering_config.json parameters

📁 Check these files:
   - filtering_config.json (current configuration)
   - calibration_strategies.json (multiple thresholds)
   - calibration.json (active thresholds)
""")


if __name__ == '__main__':
    main()
