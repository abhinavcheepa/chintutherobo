"""CSV telemetry logger. Telemetry format: TEL,1,state,pitch,gyro,fault,output."""
from __future__ import annotations
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

class TelemetryLogger:
    def __init__(self, csv_path: str):
        self.path = Path(csv_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if self.path.stat().st_size == 0:
            self._writer.writerow([
                "timestamp_utc", "state", "pitch_deg", "gyro_pitch_dps",
                "fault", "controller_output", "raw_message"
            ])
            self._file.flush()

    def log_message(self, message: str) -> None:
        fields = message.split(",")
        if len(fields) < 7 or fields[0] != "TEL":
            return
        self._writer.writerow([
            datetime.now(timezone.utc).isoformat(),
            fields[2], fields[3], fields[4], fields[5], fields[6], message
        ])
        self._file.flush()

    def close(self) -> None:
        self._file.close()
