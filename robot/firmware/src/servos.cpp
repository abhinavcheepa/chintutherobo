#include "servos.h"
#include "config.h"

ServoController Servos;

ServoController::ServoController()
    : is_attached_(false) {
    for (uint8_t i = 0; i < 6; i++) {
        target_angles_[i] = 0.0f;
        current_angles_[i] = 0.0f;
        calib_offsets_us_[i] = 0;
    }
}

void ServoController::init() {
    attach_all();

    // Initial neutral positions
    for (uint8_t i = 0; i < 6; i++) {
        target_angles_[i] = 0.0f;
        current_angles_[i] = 0.0f;
    }
}

void ServoController::attach_all() {
    if (!is_attached_) {
        servo_hip_roll_l_.attach(PIN_SERVO_HIP_ROLL_L, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
        servo_hip_pitch_l_.attach(PIN_SERVO_HIP_PITCH_L, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
        servo_knee_l_.attach(PIN_SERVO_KNEE_L, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);

        servo_hip_roll_r_.attach(PIN_SERVO_HIP_ROLL_R, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
        servo_hip_pitch_r_.attach(PIN_SERVO_HIP_PITCH_R, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
        servo_knee_r_.attach(PIN_SERVO_KNEE_R, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
        is_attached_ = true;
    }
}

void ServoController::detach_all() {
    if (is_attached_) {
        servo_hip_roll_l_.detach();
        servo_hip_pitch_l_.detach();
        servo_knee_l_.detach();

        servo_hip_roll_r_.detach();
        servo_hip_pitch_r_.detach();
        servo_knee_r_.detach();
        is_attached_ = false;
    }
}

void ServoController::set_target_joints_left(const LegJointAngles &joints) {
    target_angles_[0] = joints.hip_roll_deg;
    target_angles_[1] = joints.hip_pitch_deg;
    target_angles_[2] = joints.knee_pitch_deg;
}

void ServoController::set_target_joints_right(const LegJointAngles &joints) {
    target_angles_[3] = joints.hip_roll_deg;
    target_angles_[4] = joints.hip_pitch_deg;
    target_angles_[5] = joints.knee_pitch_deg;
}

void ServoController::set_calibration_offset(uint8_t servo_idx, int16_t offset_us) {
    if (servo_idx < 6) {
        calib_offsets_us_[servo_idx] = offset_us;
    }
}

float ServoController::get_joint_angle_deg(uint8_t servo_idx) const {
    if (servo_idx < 6) {
        return current_angles_[servo_idx];
    }
    return 0.0f;
}

uint16_t ServoController::angle_to_pulse_us(float angle_deg, uint8_t servo_idx, bool invert) {
    // Standard mapping: 0 deg = 1500 us (neutral), 10 us per degree
    float eff_angle = invert ? -angle_deg : angle_deg;
    float pulse = 1500.0f + (eff_angle * 10.0f) + (float)calib_offsets_us_[servo_idx];

    if (pulse < (float)SERVO_PULSE_MIN_US) pulse = (float)SERVO_PULSE_MIN_US;
    if (pulse > (float)SERVO_PULSE_MAX_US) pulse = (float)SERVO_PULSE_MAX_US;

    return (uint16_t)pulse;
}

void ServoController::update(float dt) {
    float max_delta = SERVO_MAX_SLEW_DEG_PER_SEC * dt;

    // Apply slew rate limiter to each joint
    for (uint8_t i = 0; i < 6; i++) {
        float diff = target_angles_[i] - current_angles_[i];
        if (diff > max_delta) {
            current_angles_[i] += max_delta;
        } else if (diff < -max_delta) {
            current_angles_[i] -= max_delta;
        } else {
            current_angles_[i] = target_angles_[i];
        }
    }

    // Write pulses to hardware servo instances if attached
    if (is_attached_) {
        servo_hip_roll_l_.writeMicroseconds(angle_to_pulse_us(current_angles_[0], 0, false));
        servo_hip_pitch_l_.writeMicroseconds(angle_to_pulse_us(current_angles_[1], 1, false));
        servo_knee_l_.writeMicroseconds(angle_to_pulse_us(current_angles_[2], 2, false));

        servo_hip_roll_r_.writeMicroseconds(angle_to_pulse_us(current_angles_[3], 3, true));
        servo_hip_pitch_r_.writeMicroseconds(angle_to_pulse_us(current_angles_[4], 4, true));
        servo_knee_r_.writeMicroseconds(angle_to_pulse_us(current_angles_[5], 5, true));
    }
}
