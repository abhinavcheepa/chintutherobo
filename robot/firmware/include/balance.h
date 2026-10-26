#ifndef BALANCE_H
#define BALANCE_H

#include <Arduino.h>
#include "protocol.h"
#include "config.h"

struct PidGains {
    float kp;
    float ki;
    float kd;
    float k_ff;
    float out_min;
    float out_max;
};

struct EepromConfigLayout {
    uint32_t magic;
    PidGains pitch_pid;
    PidGains velocity_pid;
    PidGains yaw_pid;
    uint16_t checksum;
};

class BalanceController {
public:
    BalanceController();
    void init();
    void reset();

    /**
     * @brief Computes stepper motor velocity commands for left and right wheels.
     * @param pitch_deg Current filtered robot pitch in degrees.
     * @param pitch_rate_dps Current pitch rate in deg/s.
     * @param target_vel_x_mms Forward speed setpoint in mm/s.
     * @param target_yaw_rate_mrads Turning setpoint in mrad/s.
     * @param current_leg_height_mm Active average leg height for gain scheduling.
     * @param dt Sampling time in seconds.
     * @param out_left_steps_s Output left stepper speed.
     * @param out_right_steps_s Output right stepper speed.
     */
    void compute(float pitch_deg, float pitch_rate_dps, 
                 float target_vel_x_mms, float target_yaw_rate_mrads, 
                 float current_leg_height_mm, float dt,
                 float current_vel_l_steps_s, float current_vel_r_steps_s,
                 float &out_left_steps_s, float &out_right_steps_s);

    // Gain management
    bool set_pid_gains(uint8_t controller_id, const PidGains &gains, bool save_eeprom);
    bool get_pid_gains(uint8_t controller_id, PidGains &out_gains) const;
    void load_eeprom();
    void save_eeprom();

private:
    PidGains pitch_gains_;
    PidGains vel_gains_;
    PidGains yaw_gains_;

    float pitch_integral_;
    float vel_integral_;
    float last_pitch_err_;
    float last_vel_err_;

    float wheel_accel_estimate_mps2_;

    uint16_t compute_checksum(const EepromConfigLayout &cfg);
};

extern BalanceController Balance;

#endif // BALANCE_H
