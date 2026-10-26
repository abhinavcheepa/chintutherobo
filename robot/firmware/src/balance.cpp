#include "balance.h"
#include <EEPROM.h>
#include <math.h>

BalanceController Balance;

BalanceController::BalanceController()
    : pitch_integral_(0.0f),
      vel_integral_(0.0f),
      last_pitch_err_(0.0f),
      last_vel_err_(0.0f),
      wheel_accel_estimate_mps2_(0.0f) {
    // Default Fallback Gains
    pitch_gains_ = {30.0f, 0.15f, 1.45f, 0.05f, -STEPPER_MAX_SPEED_STEPS_SEC, STEPPER_MAX_SPEED_STEPS_SEC};
    vel_gains_   = {0.012f, 0.001f, 0.001f, 0.0f, -8.0f, 8.0f}; // Target tilt in degrees
    yaw_gains_   = {1.5f, 0.0f, 0.08f, 0.0f, -6000.0f, 6000.0f};
}

void BalanceController::init() {
    load_eeprom();
    reset();
}

void BalanceController::reset() {
    pitch_integral_ = 0.0f;
    vel_integral_ = 0.0f;
    last_pitch_err_ = 0.0f;
    last_vel_err_ = 0.0f;
    wheel_accel_estimate_mps2_ = 0.0f;
}

void BalanceController::compute(float pitch_deg, float pitch_rate_dps, 
                              float target_vel_x_mms, float target_yaw_rate_mrads, 
                              float current_leg_height_mm, float dt,
                              float current_vel_l_steps_s, float current_vel_r_steps_s,
                              float &out_left_steps_s, float &out_right_steps_s) {
    // 1. Height Gain Scheduling Factor (relative to nominal 118mm height)
    float height_ratio = current_leg_height_mm / LEG_HEIGHT_NOMINAL_MM;
    if (height_ratio < 0.6f) height_ratio = 0.6f;
    if (height_ratio > 1.6f) height_ratio = 1.6f;
    float sched_factor = sqrt(height_ratio);

    float eff_kp = pitch_gains_.kp * sched_factor;
    float eff_kd = pitch_gains_.kd * pow(sched_factor, 1.5f);

    // 2. Outer Loop: True Closed-Loop Velocity Feedback -> Desired Pitch Angle (θ_ref)
    // Convert current wheel step rate into forward velocity (mm/s)
    float actual_vel_x_mms = ((current_vel_l_steps_s + current_vel_r_steps_s) * 0.5f) * MM_PER_STEP;
    float vel_err = target_vel_x_mms - actual_vel_x_mms;
    vel_integral_ += vel_err * dt;
    // Anti-windup
    if (vel_integral_ > 300.0f) vel_integral_ = 300.0f;
    if (vel_integral_ < -300.0f) vel_integral_ = -300.0f;

    // Outer PID output: computes target chassis tilt to resist drift / track commanded speed
    float target_pitch_deg = (vel_gains_.kp * vel_err) + (vel_gains_.ki * vel_integral_);
    // Bound target pitch angle to prevent fall runaway
    if (target_pitch_deg > vel_gains_.out_max) target_pitch_deg = vel_gains_.out_max;
    if (target_pitch_deg < vel_gains_.out_min) target_pitch_deg = vel_gains_.out_min;

    // 3. Inner Loop: Pitch Balance PID
    float pitch_err = pitch_deg - target_pitch_deg;
    pitch_integral_ += pitch_err * dt;
    // Anti-windup
    if (pitch_integral_ > 30.0f) pitch_integral_ = 30.0f;
    if (pitch_integral_ < -30.0f) pitch_integral_ = -30.0f;

    // Derivative on gyro measurement directly to avoid setpoint kick:
    float d_term = -eff_kd * pitch_rate_dps;
    float p_term = eff_kp * pitch_err;
    float i_term = pitch_gains_.ki * pitch_integral_;

    // Target balance acceleration / velocity in steps/sec:
    // When falling forward (+pitch_err), drive forward (+steps/sec) to move wheels under COM:
    float balance_cmd = (p_term + i_term + d_term) * (STEPS_PER_METER / 1000.0f) * 10.0f;

    // 4. Yaw Differential Control
    // target_yaw_rate in mrad/s -> convert to differential steps/sec
    float yaw_cmd = (target_yaw_rate_mrads / 1000.0f) * yaw_gains_.kp * (STEPS_PER_METER * 0.15f); // 0.15m track width
    if (yaw_cmd > yaw_gains_.out_max) yaw_cmd = yaw_gains_.out_max;
    if (yaw_cmd < yaw_gains_.out_min) yaw_cmd = yaw_gains_.out_min;

    // 5. Motor Velocity Distribution
    out_left_steps_s = balance_cmd + yaw_cmd;
    out_right_steps_s = balance_cmd - yaw_cmd;

    last_pitch_err_ = pitch_err;
}

uint16_t BalanceController::compute_checksum(const EepromConfigLayout &cfg) {
    const uint8_t *p = (const uint8_t *)&cfg;
    uint16_t sum = 0;
    // Compute sum over everything except the 2 checksum bytes at the end
    size_t length = sizeof(EepromConfigLayout) - sizeof(uint16_t);
    for (size_t i = 0; i < length; i++) {
        sum += p[i];
    }
    return sum;
}

void BalanceController::load_eeprom() {
    EepromConfigLayout cfg;
    EEPROM.get(EEPROM_CONFIG_START_ADDR, cfg);

    if (cfg.magic == EEPROM_MAGIC_HEADER && cfg.checksum == compute_checksum(cfg)) {
        pitch_gains_ = cfg.pitch_pid;
        vel_gains_   = cfg.velocity_pid;
        yaw_gains_   = cfg.yaw_pid;
    }
}

void BalanceController::save_eeprom() {
    EepromConfigLayout cfg;
    cfg.magic = EEPROM_MAGIC_HEADER;
    cfg.pitch_pid = pitch_gains_;
    cfg.velocity_pid = vel_gains_;
    cfg.yaw_pid = yaw_gains_;
    cfg.checksum = compute_checksum(cfg);

    EEPROM.put(EEPROM_CONFIG_START_ADDR, cfg);
}

bool BalanceController::set_pid_gains(uint8_t controller_id, const PidGains &gains, bool save) {
    if (controller_id == 0) {
        pitch_gains_ = gains;
    } else if (controller_id == 1) {
        vel_gains_ = gains;
    } else if (controller_id == 2) {
        yaw_gains_ = gains;
    } else {
        return false;
    }

    if (save) {
        save_eeprom();
    }
    return true;
}

bool BalanceController::get_pid_gains(uint8_t controller_id, PidGains &out_gains) const {
    if (controller_id == 0) {
        out_gains = pitch_gains_;
        return true;
    } else if (controller_id == 1) {
        out_gains = vel_gains_;
        return true;
    } else if (controller_id == 2) {
        out_gains = yaw_gains_;
        return true;
    }
    return false;
}
