import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raspberry_pi"))
from robot_controller import RobotController, RobotMode

class FakeSerial:
    connected = True
    def send_command(self, command):
        return f"id-{command}"

class RobotControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = RobotController(FakeSerial())
    def test_stand_request(self):
        self.assertEqual(self.controller.request_stand(), "id-STAND")
        self.assertEqual(self.controller.mode, RobotMode.STAND_REQUESTED)
    def test_fault_status(self):
        self.controller.consume_message("STATUS,1,FAULT,IMU_READ")
        self.assertEqual(self.controller.mode, RobotMode.FAULT)
    def test_telemetry_does_not_claim_balance(self):
        self.controller.consume_message("TEL,1,BALANCE_DISABLED,0,0,NONE,0")
        self.assertNotEqual(self.controller.mode, RobotMode.BALANCING if hasattr(RobotMode, "BALANCING") else "BALANCING")

if __name__ == "__main__":
    unittest.main()
