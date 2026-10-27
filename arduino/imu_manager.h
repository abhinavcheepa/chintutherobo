#pragma once
#include <Arduino.h>
#include <math.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

struct ImuReading {
  float accelX = 0, accelY = 0, accelZ = 0;
  float gyroX = 0, gyroY = 0, gyroZ = 0; // deg/s
  float pitchDeg = 0;
  float gyroPitchDps = 0;
  bool valid = false;
};

class ImuManager {
 public:
  bool begin() {
    connected_ = mpu_.begin();
    if (connected_) {
      mpu_.setAccelerometerRange(MPU6050_RANGE_4_G);
      mpu_.setGyroRange(MPU6050_RANGE_500_DEG);
      mpu_.setFilterBandwidth(MPU6050_BAND_21_HZ);
      lastUs_ = micros();
    }
    return connected_;
  }
  bool isConnected() const { return connected_; }

  bool calibrateStill() {
    if (!connected_) return false;
    // Call only while robot is rigidly supported and completely still.
    const int samples = 200;
    float sumGyro = 0, sumPitch = 0;
    for (int i = 0; i < samples; ++i) {
      sensors_event_t a, g, temp;
      mpu_.getEvent(&a, &g, &temp);
      sumGyro += g.gyro.y;
      sumPitch += atan2(a.acceleration.x,
                        sqrt(a.acceleration.y * a.acceleration.y +
                             a.acceleration.z * a.acceleration.z)) * RAD_TO_DEG;
      delay(5); // calibration only; not part of the control loop
    }
    gyroBiasPitch_ = (sumGyro / samples) * RAD_TO_DEG;
    pitchOffsetDeg_ = sumPitch / samples;
    calibrated_ = true;
    return true;
  }

  bool read(ImuReading& out) {
    if (!connected_) return false;
    sensors_event_t a, g, temp;
    mpu_.getEvent(&a, &g, &temp);
    const unsigned long nowUs = micros();
    float dt = (nowUs - lastUs_) / 1000000.0f;
    lastUs_ = nowUs;
    if (dt <= 0 || dt > 0.1f) dt = 0.005f;

    out.accelX = a.acceleration.x;
    out.accelY = a.acceleration.y;
    out.accelZ = a.acceleration.z;
    out.gyroX = g.gyro.x;
    out.gyroY = g.gyro.y;
    out.gyroZ = g.gyro.z;

    // Assumed pitch axis is rotation about Y and gravity-based pitch uses X/Z.
    // Verify sensor orientation on the actual torso before use.
    const float accelPitch = atan2(a.acceleration.x,
      sqrt(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z))
      * RAD_TO_DEG - pitchOffsetDeg_;
    const float gyroPitch = g.gyro.y * RAD_TO_DEG - gyroBiasPitch_;

    if (!filterInitialized_) {
      filteredPitchDeg_ = accelPitch;
      filterInitialized_ = true;
    } else {
      // Complementary filter: gyro follows fast motion, accelerometer corrects drift.
      filteredPitchDeg_ = 0.98f * (filteredPitchDeg_ + gyroPitch * dt)
                        + 0.02f * accelPitch;
    }
    out.pitchDeg = filteredPitchDeg_;
    out.gyroPitchDps = gyroPitch;
    out.valid = isfinite(out.pitchDeg) && isfinite(out.gyroPitchDps);
    latest_ = out;
    return out.valid;
  }

  ImuReading latest() const { return latest_; }

 private:
  Adafruit_MPU6050 mpu_;
  bool connected_ = false, calibrated_ = false, filterInitialized_ = false;
  float gyroBiasPitch_ = 0, pitchOffsetDeg_ = 0, filteredPitchDeg_ = 0;
  unsigned long lastUs_ = 0;
  ImuReading latest_;
};
