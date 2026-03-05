#!/usr/bin/env python3
"""
Simple configuration checker for WiFi CSI Presence Detection
Helps verify everything is set up correctly before running
"""

import os
import sys
import subprocess

def check_mark(condition):
    return "✅" if condition else "❌"

def check_python():
    """Check Python installation"""
    print("\n🐍 Python Environment:")
    try:
        version = sys.version.split()[0]
        major, minor = map(int, version.split('.')[:2])
        ok = major == 3 and minor >= 7
        print(f"   {check_mark(ok)} Python version: {version}")
        return ok
    except:
        print(f"   ❌ Python check failed")
        return False

def check_virtual_env():
    """Check if virtual environment exists"""
    print("\n📦 Virtual Environment:")
    venv_path = "python/env"
    exists = os.path.isdir(venv_path)
    print(f"   {check_mark(exists)} Virtual environment: {venv_path}")
    
    if exists:
        # Check for activation scripts
        if sys.platform == "win32":
            activate = os.path.exists("python/env/Scripts/activate.bat")
        else:
            activate = os.path.exists("python/env/bin/activate")
        print(f"   {check_mark(activate)} Activation script found")
    
    return exists

def check_dependencies():
    """Check Python dependencies"""
    print("\n📚 Python Dependencies:")
    
    required = ["numpy", "scipy", "matplotlib", "serial"]
    all_ok = True
    
    for module in required:
        try:
            if module == "serial":
                __import__("serial")  # pyserial
            else:
                __import__(module)
            print(f"   ✅ {module}")
        except ImportError:
            print(f"   ❌ {module} (not installed)")
            all_ok = False
    
    return all_ok

def check_esp32_firmware():
    """Check ESP32 firmware configuration"""
    print("\n🔧 ESP32 Firmware:")
    
    firmware_path = "firmware/csi_receiver/main/csi_receiver.c"
    exists = os.path.isfile(firmware_path)
    print(f"   {check_mark(exists)} Firmware file: {firmware_path}")
    
    if exists:
        with open(firmware_path, 'r') as f:
            content = f.read()
            
            # Check if WiFi is configured
            default_ssid = 'WIFI_SSID "Connecting..."' in content
            default_pass = 'WIFI_PASS "Error501"' in content
            
            if default_ssid or default_pass:
                print(f"   ⚠️  WiFi credentials: Using defaults (needs configuration)")
                print(f"      → Edit WIFI_SSID and WIFI_PASS in {firmware_path}")
            else:
                print(f"   ✅ WiFi credentials: Configured")
    
    return exists

def check_python_scripts():
    """Check if main Python scripts exist"""
    print("\n📄 Python Scripts:")
    
    scripts = [
        "python/run_presence_detection.py",
        "python/csi_detector.py",
        "python/live_plot.py"
    ]
    
    all_ok = True
    for script in scripts:
        exists = os.path.isfile(script)
        print(f"   {check_mark(exists)} {script}")
        all_ok = all_ok and exists
    
    return all_ok

def check_esp_idf():
    """Check if ESP-IDF is installed"""
    print("\n🛠️  ESP-IDF (for firmware compilation):")
    
    try:
        result = subprocess.run(
            ['idf.py', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print(f"   ✅ ESP-IDF installed: {version[:50]}")
            return True
    except:
        pass
    
    print(f"   ⚠️  ESP-IDF not found (only needed for firmware compilation)")
    return False

def main():
    """Main check function"""
    
    print("="*60)
    print("  WiFi CSI Presence Detection - System Check")
    print("="*60)
    
    # Change to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Run all checks
    checks = [
        ("Python", check_python()),
        ("Virtual Environment", check_virtual_env()),
        ("Dependencies", check_dependencies()),
        ("Python Scripts", check_python_scripts()),
        ("ESP32 Firmware", check_esp32_firmware()),
    ]
    
    # Optional check
    check_esp_idf()
    
    # Summary
    print("\n" + "="*60)
    print("  Summary")
    print("="*60)
    
    for name, status in checks:
        print(f"  {check_mark(status)} {name}")
    
    all_ok = all(status for _, status in checks)
    
    if all_ok:
        print("\n✅ All checks passed! System is ready.")
        print("\n📋 Next steps:")
        print("   1. Configure WiFi in ESP32 firmware (if not done)")
        print("   2. Flash ESP32: cd firmware/csi_receiver && idf.py flash")
        print("   3. Run detection: cd python && python3 run_presence_detection.py")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        print("\n💡 To fix:")
        print("   Run: ./setup.sh (macOS/Linux) or setup.bat (Windows)")
    
    print("\n" + "="*60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
