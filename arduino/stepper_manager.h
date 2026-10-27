#pragma once
#include <Arduino.h>
#include <AccelStepper.h>

class StepperManager {
 public:
  // Proposed example pins; verify driver/shield compatibility before wiring.
  static const uint8_t STEP1 = 2, DIR1 = 3, STEP2 = 4, DIR2 = 5;
  static const uint8_t ENABLE1 = 6, ENABLE2 = 7;

  bool begin() {
    motor1_ = new AccelStepper(AccelStepper::DRIVER, STEP1, DIR1);
    motor2_ = new AccelStepper(AccelStepper::DRIVER, STEP2, DIR2);
    pinMode(ENABLE1, OUTPUT);
    pinMode(ENABLE2, OUTPUT);
    // A4988/DRV8825 commonly use active-low ENABLE; verify the exact module.
    digitalWrite(ENABLE1, HIGH);
    digitalWrite(ENABLE2, HIGH);
    motor1_->setMaxSpeed(200.0);
    motor2_->setMaxSpeed(200.0);
    motor1_->setAcceleration(100.0);
    motor2_->setAcceleration(100.0);
    initialized_ = motor1_ && motor2_;
    return initialized_;
  }

  bool beginStatus() const { return initialized_; }

  bool configureLimits(float maxSpeed, float acceleration, long maxAbsSteps) {
    if (!initialized_ || maxSpeed <= 0 || maxSpeed > 1000 ||
        acceleration <= 0 || acceleration > 1000 ||
        maxAbsSteps <= 0) return false;
    maxSpeed_ = maxSpeed;
    acceleration_ = acceleration;
    maxAbsSteps_ = maxAbsSteps;
    motor1_->setMaxSpeed(maxSpeed_);
    motor2_->setMaxSpeed(maxSpeed_);
    motor1_->setAcceleration(acceleration_);
    motor2_->setAcceleration(acceleration_);
    limitsConfigured_ = true;
    return true;
  }

  bool moveRelative(uint8_t motor, long steps) {
    if (!initialized_ || !limitsConfigured_ || abs(steps) > maxAbsSteps_) return false;
    AccelStepper* m = (motor == 0) ? motor1_ : (motor == 1) ? motor2_ : nullptr;
    if (!m) return false;
    digitalWrite(motor == 0 ? ENABLE1 : ENABLE2, LOW);
    m->move(steps);
    return true;
  }

  void update() {
    if (!initialized_) return;
    motor1_->run();
    motor2_->run();
  }

  void stop() {
    if (!initialized_) return;
    motor1_->stop();
    motor2_->stop();
  }

  void disableDrivers() {
    digitalWrite(ENABLE1, HIGH);
    digitalWrite(ENABLE2, HIGH);
  }

 private:
  AccelStepper* motor1_ = nullptr;
  AccelStepper* motor2_ = nullptr;
  bool initialized_ = false, limitsConfigured_ = false;
  float maxSpeed_ = 200.0, acceleration_ = 100.0;
  long maxAbsSteps_ = 200;
};
