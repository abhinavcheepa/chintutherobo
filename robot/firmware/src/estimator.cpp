#include "estimator.h"
#include <math.h>

StateEstimator Estimator;

StateEstimator::StateEstimator()
    : pitch_deg_(0.0f),
      pitch_rate_dps_(0.0f),
      roll_deg_(0.0f),
      yaw_rate_dps_(0.0f),
      alpha_(0.985f) {}

void StateEstimator::reset() {
    pitch_deg_ = 0.0f;
    pitch_rate_dps_ = 0.0f;
    roll_deg_ = 0.0f;
    yaw_rate_dps_ = 0.0f;
}

void StateEstimator::update(float ax, float ay, float az, float gx, float gy, float gz, float dt, float wheel_accel_mps2) {
    // 1. Compensate forward accelerometer measurement for wheel linear acceleration:
    // ax_measured = ax_gravity + ax_linear / 9.80665
    float ax_corrected = ax - (wheel_accel_mps2 / 9.80665f);

    // 2. Compute pitch and roll angles from gravity vector
    // Pitch (rotation around Y-axis, forward tilt is positive)
    float pitch_acc = atan2(-ax_corrected, sqrt(ay * ay + az * az)) * (180.0f / M_PI);
    
    // Roll (rotation around X-axis, right tilt is positive)
    float roll_acc = atan2(ay, az) * (180.0f / M_PI);

    // 3. Gyro rates (Gyro Y = pitch rate, Gyro Z = yaw rate, Gyro X = roll rate)
    pitch_rate_dps_ = gy;
    yaw_rate_dps_ = gz;

    // 4. Complementary filter fusion
    pitch_deg_ = alpha_ * (pitch_deg_ + pitch_rate_dps_ * dt) + (1.0f - alpha_) * pitch_acc;
    roll_deg_ = alpha_ * (roll_deg_ + gx * dt) + (1.0f - alpha_) * roll_acc;
}
