#pragma once
#include <Arduino.h>
#include "imu_manager.h"

enum FaultCode {
  FAULT_NONE,
  FAULT_IMU,
  FAULT_PCA9685,
  FAULT_STEPPER_CONFIG,
  FAULT_IMU_READ,
  FAULT_IMU_TILT,
  FAULT_COMM_TIMEOUT
};

class SafetyManager {
 public:
  void begin() { fault_ = FAULT_NONE; }
  bool hasFault() const { return fault_ != FAULT_NONE; }
  void raiseFault(FaultCode f) { if (fault_ == FAULT_NONE) fault_ = f; }
  const char* faultName() const {
    switch (fault_) {
      case FAULT_IMU: return "IMU_INIT";
      case FAULT_PCA9685: return "PCA9685_INIT";
      case FAULT_STEPPER_CONFIG: return "STEPPER_INIT";
      case FAULT_IMU_READ: return "IMU_READ";
      case FAULT_IMU_TILT: return "TILT_LIMIT";
      case FAULT_COMM_TIMEOUT: return "COMM_TIMEOUT";
      default: return "NONE";
    }
  }
  void updateImu(const ImuReading& r, unsigned long) {
    if (!r.valid) { raiseFault(FAULT_IMU_READ); return; }
    // Conservative example threshold for test-rig fault reporting, not a validated
    // robot safety envelope. Requires physical configuration before balancing.
    if (fabs(r.pitchDeg) > 45.0f) raiseFault(FAULT_IMU_TILT);
  }
  void updateCommunication(unsigned long lastCommand, unsigned long now) {
    // Timeout only applies after a command has first been received.
    if (lastCommand != 0 && now - lastCommand > 3000UL) {
      // Do not latch a fault for ordinary inactivity in this starter version.
      // Implement a heartbeat separately if communication-loss safety is required.
    }
  }
 private:
  FaultCode fault_ = FAULT_NONE;
};
