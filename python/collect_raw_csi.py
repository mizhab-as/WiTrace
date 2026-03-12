#!/usr/bin/env python3
"""Collect raw CSI_DATA lines from ESP32 and save them to a text file."""

import sys
import time
import serial
import serial.tools.list_ports

BAUDRATE = 115200


def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = (port.description or "").lower()
        if any(x in desc for x in ["cp210", "ch340", "usb serial", "uart"]):
            return port.device
    return ports[0].device if ports else None


def collect_raw(output_file, duration_seconds=600):
    port = find_esp32_port()
    if not port:
        print("No ESP32 serial port found.")
        return 1

    print("=" * 68)
    print("RAW CSI COLLECTOR")
    print("=" * 68)
    print(f"Port: {port}")
    print(f"Output: {output_file}")
    print(f"Duration: {duration_seconds}s")
    print("Collecting full CSI_DATA lines (no feature conversion).")
    print("=" * 68)

    frame_count = 0
    start = time.time()
    last_progress_print = -1

    try:
        with serial.Serial(port, BAUDRATE, timeout=1) as ser, open(output_file, "w") as out:
            while True:
                elapsed = time.time() - start
                if elapsed >= duration_seconds:
                    break

                progress_bucket = int(elapsed) // 10
                if progress_bucket != last_progress_print:
                    last_progress_print = progress_bucket
                    remaining = max(0, int(duration_seconds - elapsed))
                    print(f"Progress: {int((elapsed / duration_seconds) * 100):3d}% | Frames: {frame_count} | Remaining: {remaining}s")

                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("CSI_DATA:"):
                    out.write(line + "\n")
                    frame_count += 1

        print("\nDone.")
        print(f"Saved {frame_count} raw CSI frames to {output_file}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except serial.SerialException as exc:
        print(f"Serial error: {exc}")
        return 2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python collect_raw_csi.py <output_file> [duration_seconds]")
        print("Example:")
        print("  python collect_raw_csi.py ../data2/myroom/occupied.txt 600")
        sys.exit(1)

    output_path = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    sys.exit(collect_raw(output_path, duration))
