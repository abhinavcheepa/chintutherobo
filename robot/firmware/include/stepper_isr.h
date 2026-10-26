#ifndef STEPPER_ISR_H
#define STEPPER_ISR_H

#include <Arduino.h>

class StepperCore {
public:
    StepperCore();
    void init();
    
    // Command velocities with acceleration limiting
    void set_target_speeds(float left_steps_per_sec, float right_steps_per_sec);
    void update_ramp(float dt);
    
    // Immediate stop
    void stop_all();

    // Invert flags
    void set_inversion(bool invert_left, bool invert_right);

    // Telemetry getters
    int32_t get_position_left();
    int32_t get_position_right();
    int16_t get_current_speed_left();
    int16_t get_current_speed_right();

    // ISR step execution helpers (called from ISRs)
    void handle_step_left_isr();
    void handle_step_right_isr();

private:
    volatile int32_t step_pos_l_;
    volatile int32_t step_pos_r_;
    volatile int8_t dir_sign_l_; // -1, 0, or +1 (atomic 8-bit)
    volatile int8_t dir_sign_r_; // -1, 0, or +1 (atomic 8-bit)

    float target_speed_l_;
    float target_speed_r_;
    float current_speed_l_;
    float current_speed_r_;

    bool invert_l_;
    bool invert_r_;

    void configure_timer3_frequency(float frequency_hz);
    void configure_timer4_frequency(float frequency_hz);
};

extern StepperCore Stepper;

#endif // STEPPER_ISR_H
