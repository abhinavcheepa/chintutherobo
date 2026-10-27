"""Runtime configuration for CHINTU Defence Bot."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    serial_port: str = os.getenv("CHINTU_SERIAL_PORT", "/dev/ttyACM0")
    baud_rate: int = int(os.getenv("CHINTU_BAUD_RATE", "115200"))
    serial_timeout_s: float = float(os.getenv("CHINTU_SERIAL_TIMEOUT", "0.25"))
    reconnect_delay_s: float = float(os.getenv("CHINTU_RECONNECT_DELAY", "2.0"))
    log_dir: str = os.getenv("CHINTU_LOG_DIR", "logs")
    telemetry_csv: str = os.getenv("CHINTU_TELEMETRY_CSV", "logs/telemetry.csv")

settings = Settings()
