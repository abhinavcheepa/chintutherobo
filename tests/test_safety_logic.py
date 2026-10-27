import unittest

def command_allowed(command: str, hardware_ready: bool, faulted: bool) -> bool:
    if command == "STOP":
        return True
    if command in {"STAND", "CALIBRATE"}:
        return hardware_ready and not faulted
    if command == "BALANCE":
        return False  # disabled pending confirmed mechanics and validation
    return False

class SafetyLogicTests(unittest.TestCase):
    def test_stop_always_allowed(self):
        self.assertTrue(command_allowed("STOP", False, True))
    def test_stand_requires_ready_hardware(self):
        self.assertFalse(command_allowed("STAND", False, False))
        self.assertTrue(command_allowed("STAND", True, False))
    def test_balance_disabled(self):
        self.assertFalse(command_allowed("BALANCE", True, False))

if __name__ == "__main__":
    unittest.main()
