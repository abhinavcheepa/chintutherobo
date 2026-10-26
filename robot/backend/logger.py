"""High-speed flight data recorder for telemetry and event logging."""

import os
import time
import json
import csv
from pathlib import Path
from typing import Optional
from backend.config import LOG_DIR, LOG_FORMAT, MAX_LOG_FILE_SIZE_BYTES
from backend.protocol import Telemetry


class BlackboxLogger:
    """Asynchronous and file-rotated blackbox logger."""

    def __init__(self, log_dir: Path = LOG_DIR, log_format: str = LOG_FORMAT):
        self.log_dir = log_dir
        self.log_format = log_format
        self.current_file_path: Optional[Path] = None
        self._file_handle = None
        self._csv_writer = None
        self._open_new_log()

    def _open_new_log(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        ext = "jsonl" if self.log_format == "jsonl" else "csv"
        self.current_file_path = self.log_dir / f"telemetry_{timestamp_str}.{ext}"

        self._file_handle = open(self.current_file_path, "a", buffering=8192, encoding="utf-8")

        if self.log_format == "csv":
            fieldnames = [
                "timestamp", "pitch_deg", "pitch_rate_dps", "roll_deg", "yaw_rate_dps",
                "wheel_pos_l", "wheel_pos_r", "wheel_vel_l", "wheel_vel_r",
                "leg_pos_l", "leg_pos_r", "v_batt_mv", "state_code", "state_str",
                "error_flags", "loop_jitter_us", "last_cmd_id"
            ]
            self._csv_writer = csv.DictWriter(self._file_handle, fieldnames=fieldnames)
            self._csv_writer.writeheader()
            self._file_handle.flush()

    def _check_rotation(self) -> None:
        if self.current_file_path and self.current_file_path.exists():
            if self.current_file_path.stat().st_size >= MAX_LOG_FILE_SIZE_BYTES:
                self._open_new_log()

    def log_telemetry(self, telem: Telemetry) -> None:
        """Logs a telemetry packet with system timestamp."""
        self._check_rotation()
        now = time.time()

        if self.log_format == "jsonl":
            record = {
                "timestamp": now,
                "pitch_deg": telem.pitch_deg,
                "pitch_rate_dps": telem.pitch_rate_dps,
                "roll_deg": telem.roll_deg,
                "yaw_rate_dps": telem.yaw_rate_dps,
                "wheel_pos_l": telem.wheel_pos_l,
                "wheel_pos_r": telem.wheel_pos_r,
                "wheel_vel_l": telem.wheel_vel_l,
                "wheel_vel_r": telem.wheel_vel_r,
                "leg_pos_l": telem.leg_pos_l,
                "leg_pos_r": telem.leg_pos_r,
                "v_batt_mv": telem.v_batt_mv,
                "state_code": telem.state_code,
                "state_str": telem.state_str,
                "error_flags": telem.error_flags,
                "loop_jitter_us": telem.loop_jitter_us,
                "last_cmd_id": telem.last_cmd_id
            }
            self._file_handle.write(json.dumps(record) + "\n")
        else:
            self._csv_writer.writerow({
                "timestamp": now,
                "pitch_deg": telem.pitch_deg,
                "pitch_rate_dps": telem.pitch_rate_dps,
                "roll_deg": telem.roll_deg,
                "yaw_rate_dps": telem.yaw_rate_dps,
                "wheel_pos_l": telem.wheel_pos_l,
                "wheel_pos_r": telem.wheel_pos_r,
                "wheel_vel_l": telem.wheel_vel_l,
                "wheel_vel_r": telem.wheel_vel_r,
                "leg_pos_l": telem.leg_pos_l,
                "leg_pos_r": telem.leg_pos_r,
                "v_batt_mv": telem.v_batt_mv,
                "state_code": telem.state_code,
                "state_str": telem.state_str,
                "error_flags": telem.error_flags,
                "loop_jitter_us": telem.loop_jitter_us,
                "last_cmd_id": telem.last_cmd_id
            })

    def close(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except Exception:
                pass
