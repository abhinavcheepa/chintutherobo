#ifndef ESTIMATOR_H
#define ESTIMATOR_H

#include <Arduino.h>

class StateEstimator {
public:
    StateEstimator();
    void reset();
    void update(float ax, float ay, float az, float gx, float gy, float gz, float dt, float wheel_accel_mps2 = 0.0f);

    float get_pitch_deg() const { return pitch_deg_; }
    float get_pitch_rate_dps() const { return pitch_rate_dps_; }
    float get_roll_deg() const { return roll_deg_; }
    float get_yaw_rate_dps() const { return yaw_rate_dps_; }

private:
    float pitch_deg_;
    float pitch_rate_dps_;
    float roll_deg_;
    float yaw_rate_dps_;

    const float alpha_; // Filter weight (0.985)
};

extern StateEstimator Estimator;

#endif // ESTIMATOR_H
