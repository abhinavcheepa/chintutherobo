#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Servo.h>
#include <Adafruit_PWMServoDriver.h>

class ServoManager {
 public:
  static const uint8_t SERVO_COUNT = 6;
  static const uint8_t FIRST_CHANNEL = 0;
  // Canonical Arduino Mega 2560 direct pins matching main branch:
  // Left: Hip Roll (44), Hip Pitch (45), Knee (46)
  // Right: Hip Roll (11), Hip Pitch (12), Knee (38)
  const uint8_t directPins_[SERVO_COUNT] = {44, 45, 46, 11, 12, 38};

  static const uint16_t DEFAULT_MIN_US = 1000;
  static const uint16_t DEFAULT_MAX_US = 2000;

  bool begin() {
    // 1. Probe for external PCA9685 expander at I2C address 0x40
    Wire.beginTransmission(0x40);
    byte i2cErr = Wire.endTransmission();
    if (i2cErr == 0) {
      connected_ = pwm_.begin();
      if (connected_) {
        pwm_.setPWMFreq(50);
        useDirect_ = false;
      }
    }

    // 2. If no PCA9685 board is connected, fallback to direct Mega 2560 pins
    if (!connected_) {
      for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
        directServos_[i].attach(directPins_[i], DEFAULT_MIN_US, DEFAULT_MAX_US);
      }
      useDirect_ = true;
      connected_ = true;
    }

    for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
      minUs_[i] = DEFAULT_MIN_US;
      maxUs_[i] = DEFAULT_MAX_US;
      targetUs_[i] = 1500;
      currentUs_[i] = 1500;
      configured_[i] = false;
    }
    return connected_;
  }
  bool isConnected() const { return connected_; }

  void setCalibration(uint8_t index, uint16_t minUs, uint16_t maxUs,
                      uint16_t neutralUs) {
    if (index >= SERVO_COUNT || minUs < 500 || maxUs > 2500 ||
        minUs >= maxUs || neutralUs < minUs || neutralUs > maxUs) return;
    minUs_[index] = minUs;
    maxUs_[index] = maxUs;
    targetUs_[index] = currentUs_[index] = neutralUs;
    configured_[index] = true;
  }

  bool setTargetMicroseconds(uint8_t index, uint16_t pulseUs) {
    if (!connected_ || index >= SERVO_COUNT || !configured_[index]) return false;
    if (pulseUs < minUs_[index] || pulseUs > maxUs_[index]) return false;
    targetUs_[index] = pulseUs;
    return true;
  }

  bool standingPoseConfigured() const {
    for (uint8_t i = 0; i < SERVO_COUNT; ++i)
      if (!configured_[i]) return false;
    return true;
  }

  void requestStandingPose() {
    if (!standingPoseConfigured()) return;
    for (uint8_t i = 0; i < SERVO_COUNT; ++i) targetUs_[i] = neutralUs_[i];
  }

  void setNeutral(uint8_t index, uint16_t pulseUs) {
    if (index < SERVO_COUNT && configured_[index] &&
        pulseUs >= minUs_[index] && pulseUs <= maxUs_[index]) neutralUs_[index] = pulseUs;
  }

  void update() {
    if (!connected_) return;
    // Slew-limited transition. Change by at most 5 microseconds per update.
    for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
      if (!configured_[i]) continue;
      if (currentUs_[i] < targetUs_[i]) {
        uint16_t next = currentUs_[i] + 5;
        currentUs_[i] = (next > targetUs_[i]) ? targetUs_[i] : next;
      } else if (currentUs_[i] > targetUs_[i]) {
        uint16_t next = (currentUs_[i] >= 5) ? currentUs_[i] - 5 : 0;
        currentUs_[i] = (next < targetUs_[i]) ? targetUs_[i] : next;
      }
      if (useDirect_) {
        directServos_[i].writeMicroseconds(currentUs_[i]);
      } else {
        pwm_.writeMicroseconds(FIRST_CHANNEL + i, currentUs_[i]);
      }
    }
  }

  void stopCommanding() {
    for (uint8_t i = 0; i < SERVO_COUNT; ++i) targetUs_[i] = currentUs_[i];
  }

 private:
  Adafruit_PWMServoDriver pwm_ = Adafruit_PWMServoDriver(0x40);
  Servo directServos_[SERVO_COUNT];
  bool useDirect_ = true;
  bool connected_ = false;
  uint16_t minUs_[SERVO_COUNT], maxUs_[SERVO_COUNT];
  uint16_t targetUs_[SERVO_COUNT], currentUs_[SERVO_COUNT];
  uint16_t neutralUs_[SERVO_COUNT] = {1500,1500,1500,1500,1500,1500};
  bool configured_[SERVO_COUNT];
};
