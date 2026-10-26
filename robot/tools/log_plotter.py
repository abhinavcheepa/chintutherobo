"""Offline Blackbox Log Plotter and Flight Dynamics Analyzer."""

import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Any


def load_log_file(file_path: Path) -> List[Dict[str, Any]]:
    """Loads a JSONL or CSV telemetry log."""
    records = []
    if file_path.suffix.lower() == ".jsonl":
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    elif file_path.suffix.lower() == ".csv":
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    records.append({
                        "timestamp": float(row["timestamp"]),
                        "pitch_deg": float(row["pitch_deg"]),
                        "pitch_rate_dps": float(row["pitch_rate_dps"]),
                        "roll_deg": float(row["roll_deg"]),
                        "yaw_rate_dps": float(row["yaw_rate_dps"]),
                        "wheel_vel_l": float(row["wheel_vel_l"]),
                        "wheel_vel_r": float(row["wheel_vel_r"]),
                        "v_batt_mv": float(row["v_batt_mv"]),
                        "loop_jitter_us": float(row["loop_jitter_us"]),
                        "state_str": row.get("state_str", "UNKNOWN")
                    })
                except (ValueError, KeyError):
                    continue
    return records


def plot_flight_log(file_path: Path, output_image: Path = None):
    """Generates multi-pane diagnostic plots from flight data."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[-] matplotlib is required for plotting. Install via: pip install matplotlib")
        return

    records = load_log_file(file_path)
    if not records:
        print(f"[-] No valid records found in {file_path}")
        return

    t0 = records[0]["timestamp"]
    times = [r["timestamp"] - t0 for r in records]
    pitches = [r["pitch_deg"] for r in records]
    pitch_rates = [r["pitch_rate_dps"] for r in records]
    vel_l = [r["wheel_vel_l"] for r in records]
    vel_r = [r["wheel_vel_r"] for r in records]
    voltages = [r["v_batt_mv"] / 1000.0 for r in records]
    jitters = [r["loop_jitter_us"] for r in records]

    print("==================================================")
    print(f" Flight Log Analysis: {file_path.name}")
    print(f" Records count  : {len(records)}")
    print(f" Flight Duration: {times[-1]:.2f} seconds")
    print(f" Max Tilt Pitch : {max(map(abs, pitches)):.2f} deg")
    print(f" Max Wheel Speed: {max(max(map(abs, vel_l)), max(map(abs, vel_r))):.1f} steps/s")
    print(f" Peak MCU Jitter: {max(jitters):.1f} us")
    print(f" End Voltage    : {voltages[-1]:.2f} V")
    print("==================================================")

    fig, axs = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(f"Chintu Biped Telemetry Analysis - {file_path.name}", fontsize=14, fontweight="bold")

    # Pane 1: Pitch & Gyro Rate
    axs[0].plot(times, pitches, label="Pitch Angle (deg)", color="#00bcd4", linewidth=1.5)
    axs[0].plot(times, pitch_rates, label="Pitch Rate (deg/s)", color="#ff9800", alpha=0.6, linewidth=1.0)
    axs[0].axhline(45, color="r", linestyle="--", alpha=0.5, label="Tilt Cutoff (+/-45 deg)")
    axs[0].axhline(-45, color="r", linestyle="--", alpha=0.5)
    axs[0].set_ylabel("Angle / Rate")
    axs[0].legend(loc="upper right")
    axs[0].grid(True, alpha=0.3)

    # Pane 2: Stepper Velocities
    axs[1].plot(times, vel_l, label="Left Stepper (steps/s)", color="#4caf50", linewidth=1.2)
    axs[1].plot(times, vel_r, label="Right Stepper (steps/s)", color="#e91e63", linewidth=1.2)
    axs[1].set_ylabel("Wheel Speed")
    axs[1].legend(loc="upper right")
    axs[1].grid(True, alpha=0.3)

    # Pane 3: DC Bus Voltage
    axs[2].plot(times, voltages, label="Battery Voltage (V)", color="#ffeb3b", linewidth=1.5)
    axs[2].axhline(9.6, color="r", linestyle="--", alpha=0.7, label="Brownout Limit (9.6V)")
    axs[2].set_ylabel("Voltage (V)")
    axs[2].legend(loc="upper right")
    axs[2].grid(True, alpha=0.3)

    # Pane 4: Loop Jitter
    axs[3].plot(times, jitters, label="200 Hz Loop Jitter (us)", color="#9c27b0", linewidth=1.0)
    axs[3].axhline(200, color="r", linestyle="--", alpha=0.7, label="Max Allowable Jitter (200 us)")
    axs[3].set_ylabel("Jitter (us)")
    axs[3].set_xlabel("Time (seconds)")
    axs[3].legend(loc="upper right")
    axs[3].grid(True, alpha=0.3)

    plt.tight_layout()
    if output_image:
        plt.savefig(output_image, dpi=200)
        print(f"[+] Saved diagnostic plot to {output_image}")
    else:
        plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python log_plotter.py <path_to_telemetry_file.jsonl|csv> [output_image.png]")
        sys.exit(1)
    log_file = Path(sys.argv[1])
    out_img = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    plot_flight_log(log_file, out_img)
