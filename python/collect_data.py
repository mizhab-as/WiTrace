#!/usr/bin/env python3
"""
Simple CSI Data Collector
Records variance values from ESP32 to train detection models
"""

import serial
import serial.tools.list_ports
import numpy as np
from collections import deque
import time

BAUDRATE = 115200
ENERGY_WINDOW = 50

def find_esp32_port():
    """Auto-detect ESP32 serial port"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if any(x in port.description.lower() for x in ['cp210', 'ch340', 'usb serial', 'uart']):
            return port.device
    return ports[0].device if ports else None

def collect_data(output_file, duration_seconds=60):
    """
    Collect CSI data and save variance values
    
    Args:
        output_file: Path to save the data (e.g., 'data/myroom/empty.txt')
        duration_seconds: How long to collect data (default: 60 seconds)
    """
    
    port = find_esp32_port()
    if not port:
        print("❌ No ESP32 found!")
        return False
    
    print("\n" + "="*70)
    print("  📡 CSI DATA COLLECTOR")
    print("="*70)
    print(f"📍 Port: {port}")
    print(f"💾 Output: {output_file}")
    print(f"⏱️  Duration: {duration_seconds} seconds")
    print("="*70 + "\n")
    
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        print("✅ Connected to ESP32\n")
        
        energy_buffer = deque(maxlen=ENERGY_WINDOW)
        variance_data = []
        start_time = time.time()
        
        print("🔴 RECORDING... Stay in position!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration_seconds:
                break
            
            # Show progress
            remaining = duration_seconds - elapsed
            if int(elapsed) % 5 == 0 and elapsed > 0:
                progress = (elapsed / duration_seconds) * 100
                print(f"⏳ {progress:.0f}% complete... ({len(variance_data)} samples) - {remaining:.0f}s remaining")
            
            # Read CSI data
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line.startswith('CSI_DATA:'):
                    values_str = line.split(':', 1)[1].strip()
                    values = [int(v) for v in values_str.split()]
                    
                    if values:
                        energy = np.mean(np.abs(values))
                        energy_buffer.append(energy)
                        
                        # Calculate variance once we have enough samples
                        if len(energy_buffer) >= ENERGY_WINDOW:
                            variance = np.var(list(energy_buffer))
                            variance_data.append(variance)
                            
            except (ValueError, IndexError):
                pass
        
        ser.close()
        
        print(f"\n✅ Recording complete! Collected {len(variance_data)} variance samples")
        
        # Save data
        with open(output_file, 'w') as f:
            for variance in variance_data:
                f.write(f"{variance}\n")
        
        print(f"💾 Data saved to: {output_file}")
        
        # Show statistics
        if variance_data:
            print(f"\n📊 Statistics:")
            print(f"   Mean:   {np.mean(variance_data):.2f}")
            print(f"   Std:    {np.std(variance_data):.2f}")
            print(f"   Min:    {np.min(variance_data):.2f}")
            print(f"   Max:    {np.max(variance_data):.2f}")
        
        return True
        
    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
        return False
    except KeyboardInterrupt:
        print("\n\n⚠️ Recording interrupted by user")
        if ser and ser.is_open:
            ser.close()
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("\n📖 Usage Examples:")
        print("   python collect_data.py data/myroom/empty.txt")
        print("   python collect_data.py data/myroom/occupied.txt 90")
        print("   python collect_data.py data/myroom/walking.txt 120")
        print()
        sys.exit(1)
    
    output_file = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    
    collect_data(output_file, duration)
