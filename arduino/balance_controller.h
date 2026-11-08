#pragma once
#include <Arduino.h>
#include <math.h>
#include "imu_manager.h"

// Development controller for a supported test rig. Output is STEP pulses/second,
// NOT a validated gain set. Keep physical arming disabled until sensor axis and
// left/right motor signs are verified with wheels lifted.
class BalanceController {
 public:
  void configure(float kp, float ki, float kd, float outputLimitStepsPerSec) {
    kp_ = kp; ki_ = ki; kd_ = kd;
    outputLimit_ = fabs(outputLimitStepsPerSec);
    configured_ = isfinite(kp_) && isfinite(ki_) && isfinite(kd_) &&
                  isfinite(outputLimit_) && outputLimit_ > 0;
    integral_ = 0;
  }

  // Intentionally not an enable function. Physical output is gated in the .ino.
  void disable() { enabled_ = false; integral_ = 0; lastOutput_ = 0; }
  bool isEnabled() const { return enabled_; }

  // Called only after the main firmware's explicit safety gate permits it.
  bool armForValidatedRig() {
    if (!configured_) return false;
    enabled_ = true;
    integral_ = 0;
    return true;
  }

  float update(const ImuReading& r, float dt) {
    if (!configured_ || !enabled_ || !r.valid || !isfinite(dt) || dt < 0.001f || dt > 0.02f) {
      lastOutput_ = 0;
      return 0;
    }
    const float error = targetAngleDeg_ - r.pitchDeg;
    integral_ = constrain(integral_ + error * dt, -integralLimit_, integralLimit_);
    // Sign is not universally correct: validate IMU axis and motor directions first.
    const float out = kp_ * error + ki_ * integral_ - kd_ * r.gyroPitchDps;
    lastOutput_ = constrain(out, -outputLimit_, outputLimit_);
    return lastOutput_;
  }

  float lastOutput() const { return lastOutput_  ; }
  void setTargetAngle(float angleDeg) {
    if (isfinite(angleDeg) && fabs(angleDeg) <= 5.0f) targetAngleDeg_ = angleDeg;
  }

 private:
  float kp_ = 0, ki_ = 0, kd_ = 0, outputLimit_ = 0;
  float targetAngleDeg_ = 0, integral_ = 0, integralLimit_ = 5, lastOutput_ = 0;
  bool configured_ = false, enabled_ = false;
};
