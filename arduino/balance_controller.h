#pragma once
#include <Arduino.h>
#include <math.h>
#include "imu_manager.h"

// This controller is intentionally disabled by default.
// Do not enable until the mechanical actuator mapping and control signs are verified.
class BalanceController {
 public:
  void configure(float kp, float ki, float kd, float outputLimit) {
    kp_ = kp; ki_ = ki; kd_ = kd; outputLimit_ = fabs(outputLimit);
    configured_ = (isfinite(kp_) && isfinite(ki_) && isfinite(kd_) && outputLimit_ > 0);
  }
  void enableForBenchSimulationOnly() { enabled_ = false; } // physical output remains disabled
  void disable() { enabled_ = false; integral_ = 0; lastOutput_ = 0; }
  bool isEnabled() const { return enabled_; }

  float update(const ImuReading& r, float dt) {
    if (!configured_ || !enabled_ || !r.valid || dt <= 0 || dt > 0.05f) {
      lastOutput_ = 0;
      return lastOutput_;
    }
    const float error = targetAngleDeg_ - r.pitchDeg;
    integral_ += error * dt;
    integral_ = constrain(integral_, -integralLimit_, integralLimit_);
    // Use gyro rate as a damping term; exact sign must be validated on the rig.
    float out = kp_ * error + ki_ * integral_ - kd_ * r.gyroPitchDps;
    lastOutput_ = constrain(out, -outputLimit_, outputLimit_);
    return lastOutput_;
  }

  float lastOutput() const { return lastOutput_; }
  void setTargetAngle(float angleDeg) {
    if (isfinite(angleDeg) && fabs(angleDeg) <= 10.0f) targetAngleDeg_ = angleDeg;
  }

 private:
  float kp_ = 0, ki_ = 0, kd_ = 0, outputLimit_ = 0;
  float targetAngleDeg_ = 0, integral_ = 0, integralLimit_ = 10, lastOutput_ = 0;
  bool configured_ = false;
  bool enabled_ = false; // no physical balancing until mechanical mapping is confirmed
};
