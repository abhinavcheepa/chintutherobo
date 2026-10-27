"""CHINTU Defence Bot Raspberry Pi application."""
from __future__ import annotations
import logging
import time
from config import settings
from serial_manager import SerialManager
from robot_controller import RobotController
from telemetry_logger import TelemetryLogger

def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    serial_link = SerialManager(settings.serial_port, settings.baud_rate,
                                settings.serial_timeout_s)
    controller = RobotController(serial_link)
    logger = TelemetryLogger(settings.telemetry_csv)
    try:
        serial_link.connect()
        logging.info("Connected to Arduino at %s", settings.serial_port)
        controller.request_status()
        while True:
            message = serial_link.read_message()
            if message:
                logging.info("Arduino: %s", message)
                controller.consume_message(message)
                logger.log_message(message)
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        logging.info("Shutdown requested.")
        try:
            if serial_link.connected:
                serial_link.send_command("STOP")
                time.sleep(0.1)
        except Exception:
            logging.exception("Could not send software STOP during shutdown")
    except Exception:
        logging.exception("Robot application error")
        return 1
    finally:
        logger.close()
        serial_link.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
