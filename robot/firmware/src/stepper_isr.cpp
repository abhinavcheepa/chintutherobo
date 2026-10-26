#include "stepper_isr.h"
#include "config.h"

StepperCore Stepper;

// Timer 3 Compare Match A Interrupt (Left Stepper)
ISR(TIMER3_COMPA_vect) {
    Stepper.handle_step_left_isr();
}

// Timer 4 Compare Match A Interrupt (Right Stepper)
ISR(TIMER4_COMPA_vect) {
    Stepper.handle_step_right_isr();
}

StepperCore::StepperCore()
    : step_pos_l_(0),
      step_pos_r_(0),
      target_speed_l_(0.0f),
      target_speed_r_(0.0f),
      current_speed_l_(0.0f),
      current_speed_r_(0.0f),
      invert_l_(false),
      invert_r_(true) {} // Right motor physically inverted in symmetric biped

void StepperCore::init() {
    pinMode(PIN_STEP_LEFT, OUTPUT);
    pinMode(PIN_DIR_LEFT, OUTPUT);
    pinMode(PIN_STEP_RIGHT, OUTPUT);
    pinMode(PIN_DIR_RIGHT, OUTPUT);

    digitalWrite(PIN_STEP_LEFT, LOW);
    digitalWrite(PIN_STEP_RIGHT, LOW);

    // 1. Configure Timer 3 (Left Motor) - CTC Mode, Prescaler 8
    cli(); // Disable interrupts during configuration
    TCCR3A = 0;
    TCCR3B = (1 << WGM32) | (1 << CS31); // CTC, Prescaler = 8 (2 MHz clock)
    TCNT3 = 0;
    OCR3A = 0xFFFF;
    TIMSK3 &= ~(1 << OCIE3A); // Interrupt disabled initially

    // 2. Configure Timer 4 (Right Motor) - CTC Mode, Prescaler 8
    TCCR4A = 0;
    TCCR4B = (1 << WGM42) | (1 << CS41); // CTC, Prescaler = 8 (2 MHz clock)
    TCNT4 = 0;
    OCR4A = 0xFFFF;
    TIMSK4 &= ~(1 << OCIE4A); // Interrupt disabled initially
    sei(); // Re-enable interrupts
}

void StepperCore::set_inversion(bool invert_left, bool invert_right) {
    invert_l_ = invert_left;
    invert_r_ = invert_right;
}

void StepperCore::set_target_speeds(float left_steps_per_sec, float right_steps_per_sec) {
    // Clamp to hardware maximum limits
    if (left_steps_per_sec > STEPPER_MAX_SPEED_STEPS_SEC) left_steps_per_sec = STEPPER_MAX_SPEED_STEPS_SEC;
    if (left_steps_per_sec < -STEPPER_MAX_SPEED_STEPS_SEC) left_steps_per_sec = -STEPPER_MAX_SPEED_STEPS_SEC;

    if (right_steps_per_sec > STEPPER_MAX_SPEED_STEPS_SEC) right_steps_per_sec = STEPPER_MAX_SPEED_STEPS_SEC;
    if (right_steps_per_sec < -STEPPER_MAX_SPEED_STEPS_SEC) right_steps_per_sec = -STEPPER_MAX_SPEED_STEPS_SEC;

    target_speed_l_ = left_steps_per_sec;
    target_speed_r_ = right_steps_per_sec;
}

void StepperCore::update_ramp(float dt) {
    float max_delta = STEPPER_MAX_ACCEL_STEPS_S2 * dt;

    // 1. Slew rate / Acceleration ramp for Left Stepper
    float diff_l = target_speed_l_ - current_speed_l_;
    if (diff_l > max_delta) {
        current_speed_l_ += max_delta;
    } else if (diff_l < -max_delta) {
        current_speed_l_ -= max_delta;
    } else {
        current_speed_l_ = target_speed_l_;
    }

    // Direction output left
    bool dir_l = (current_speed_l_ >= 0.0f);
    dir_sign_l_ = (current_speed_l_ >= 0.0f) ? 1 : -1;
    if (invert_l_) dir_l = !dir_l;
    digitalWrite(PIN_DIR_LEFT, dir_l ? HIGH : LOW);

    configure_timer3_frequency(fabs(current_speed_l_));

    // 2. Slew rate / Acceleration ramp for Right Stepper
    float diff_r = target_speed_r_ - current_speed_r_;
    if (diff_r > max_delta) {
        current_speed_r_ += max_delta;
    } else if (diff_r < -max_delta) {
        current_speed_r_ -= max_delta;
    } else {
        current_speed_r_ = target_speed_r_;
    }

    // Direction output right
    bool dir_r = (current_speed_r_ >= 0.0f);
    dir_sign_r_ = (current_speed_r_ >= 0.0f) ? 1 : -1;
    if (invert_r_) dir_r = !dir_r;
    digitalWrite(PIN_DIR_RIGHT, dir_r ? HIGH : LOW);

    configure_timer4_frequency(fabs(current_speed_r_));
}

void StepperCore::configure_timer3_frequency(float frequency_hz) {
    if (frequency_hz < 10.0f) {
        TIMSK3 &= ~(1 << OCIE3A); // Disable interrupt
        return;
    }

    // Prescaler 8 -> Timer Clock = 2,000,000 Hz
    uint32_t ocr_val = (uint32_t)(2000000.0f / frequency_hz) - 1;
    if (ocr_val < 79) ocr_val = 79; // Cap at 25 kHz max (79 = 25000 Hz)
    if (ocr_val > 65535) ocr_val = 65535;

    cli();
    OCR3A = (uint16_t)ocr_val;
    TIMSK3 |= (1 << OCIE3A); // Enable interrupt
    sei();
}

void StepperCore::configure_timer4_frequency(float frequency_hz) {
    if (frequency_hz < 10.0f) {
        cli();
        TIMSK4 &= ~(1 << OCIE4A); // Disable interrupt
        sei();
        return;
    }

    uint32_t ocr_val = (uint32_t)(2000000.0f / frequency_hz) - 1;
    if (ocr_val < 79) ocr_val = 79;
    if (ocr_val > 65535) ocr_val = 65535;

    cli();
    OCR4A = (uint16_t)ocr_val;
    TIMSK4 |= (1 << OCIE4A);
    sei();
}

void StepperCore::handle_step_left_isr() {
    // Generate pulse on Pin 5 (PORTE, bit 3)
    PORTE |= (1 << 3);
    step_pos_l_ += dir_sign_l_;
    __builtin_avr_delay_cycles(16); // Guaranteed 1.0 us pulse width for A4988 / TMC2209
    PORTE &= ~(1 << 3);
}

void StepperCore::handle_step_right_isr() {
    // Generate pulse on Pin 7 (PORTH, bit 4)
    PORTH |= (1 << 4);
    step_pos_r_ += dir_sign_r_;
    __builtin_avr_delay_cycles(16); // Guaranteed 1.0 us pulse width for A4988 / TMC2209
    PORTH &= ~(1 << 4);
}

void StepperCore::stop_all() {
    cli();
    TIMSK3 &= ~(1 << OCIE3A);
    TIMSK4 &= ~(1 << OCIE4A);
    current_speed_l_ = 0.0f;
    current_speed_r_ = 0.0f;
    target_speed_l_ = 0.0f;
    target_speed_r_ = 0.0f;
    dir_sign_l_ = 0;
    dir_sign_r_ = 0;
    // Force step pins LOW to prevent continuous coil heat/holding
    digitalWrite(PIN_STEP_LEFT, LOW);
    digitalWrite(PIN_STEP_RIGHT, LOW);
    sei();
}

int32_t StepperCore::get_position_left() {
    int32_t pos;
    cli();
    pos = step_pos_l_;
    sei();
    return pos;
}

int32_t StepperCore::get_position_right() {
    int32_t pos;
    cli();
    pos = step_pos_r_;
    sei();
    return pos;
}

int16_t StepperCore::get_current_speed_left() {
    return (int16_t)current_speed_l_;
}

int16_t StepperCore::get_current_speed_right() {
    return (int16_t)current_speed_r_;
}
