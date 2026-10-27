import unittest

ALLOWED = {"STATUS", "STAND", "STOP", "CALIBRATE", "BALANCE"}

def make_command(command: str, request_id: str) -> str:
    if command not in ALLOWED:
        raise ValueError("unsupported command")
    if not request_id or not request_id.isalnum() or len(request_id) > 16:
        raise ValueError("invalid request id")
    return f"{command},{request_id}\n"

class ProtocolTests(unittest.TestCase):
    def test_valid_command(self):
        self.assertEqual(make_command("STATUS", "12"), "STATUS,12\n")
    def test_unknown_command_rejected(self):
        with self.assertRaises(ValueError):
            make_command("MOVE_MOTOR", "12")
    def test_bad_id_rejected(self):
        with self.assertRaises(ValueError):
            make_command("STOP", "bad,id")

if __name__ == "__main__":
    unittest.main()
