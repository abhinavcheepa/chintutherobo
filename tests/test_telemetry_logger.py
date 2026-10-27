import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raspberry_pi"))
from telemetry_logger import TelemetryLogger

class TelemetryTests(unittest.TestCase):
    def test_logs_telemetry_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "telemetry.csv"
            logger = TelemetryLogger(str(p))
            logger.log_message("TEL,1,IDLE,1.25,0.5,NONE,0.0")
            logger.close()
            content = p.read_text()
            self.assertIn("IDLE", content)
            self.assertIn("1.25", content)

if __name__ == "__main__":
    unittest.main()
