#ifndef SERVOS_H
#define SERVOS_H

#include <Arduino.h>
#include <Servo.h>
#include "legs_ik.h"

class ServoController {
public:
    ServoController();
    void init();
    void update(float dt);

    void set_target_joints_left(const LegJointAngles &joints);
    void set_target_joints_right(const LegJointAngles &joints);

    // Manual per-joint calibration offsets
    void set_calibration_offset(uint8_t servo_idx, int16_t offset_us);

    // Current filtered positions in degrees
    float get_joint_angle_deg(uint8_t servo_idx) const;

    // Power detachment / attachment for FAULT_SERVO_MODE
    void detach_all();
    void attach_all();
    bool is_attached() const { return is_attached_; }

private:
    bool is_attached_;
    Servo servo_hip_roll_l_;
    Servo servo_hip_pitch_l_;
    Servo servo_knee_l_;

    Servo servo_hip_roll_r_;
    Servo servo_hip_pitch_r_;
    Servo servo_knee_r_;

    float target_angles_[6];
    float current_angles_[6];
    int16_t calib_offsets_us_[6];

    uint16_t angle_to_pulse_us(float angle_deg, uint8_t servo_idx, bool invert = false);
};

extern ServoController Servos;

#endif // SERVOS_H
