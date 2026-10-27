#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

class ServoManager {
 public:
  static const uint8_t SERVO_COUNT = 6;
  static const uint8_t FIRST_CHANNEL = 0;
  // These conservative pulse values are examples only. Calibrate each servo/linkage.
  static const uint16_t DEFAULT_MIN_US = 1000;
  static const uint16_t DEFAULT_MAX_US = 2000;

  bool begin() {
    connected_ = pwm_.begin();
    if (connected_) pwm_.setPWMFreq(50);
    for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
      minUs_[i] = DEFAULT_MIN_US;
      maxUs_[i] = DEFAULT_MAX_US;
      targetUs_[i] = 1500;
      currentUs_[i] = 1500;
      configured_[i] = false; // no physical joint map assumed
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
    // Deliberately does not invent a standing pose. Targets must be configured
    // by calibrated hardware-specific values before this can move any servo.
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
      pwm_.writeMicroseconds(FIRST_CHANNEL + i, currentUs_[i]);
    }
  }

  void stopCommanding() {
    // Hold current commanded positions; do not blindly detach torque.
    for (uint8_t i = 0; i < SERVO_COUNT; ++i) targetUs_[i] = currentUs_[i];
  }

 private:
  Adafruit_PWMServoDriver pwm_ = Adafruit_PWMServoDriver(0x40);
  bool connected_ = false;
  uint16_t minUs_[SERVO_COUNT], maxUs_[SERVO_COUNT];
  uint16_t targetUs_[SERVO_COUNT], currentUs_[SERVO_COUNT];
  uint16_t neutralUs_[SERVO_COUNT] = {1500,1500,1500,1500,1500,1500};
  bool configured_[SERVO_COUNT];
};
