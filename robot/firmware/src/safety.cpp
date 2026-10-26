#include "safety.h"
#include "stepper_isr.h"

SafetyManager Safety;

SafetyManager::SafetyManager()
    : current_state_(STATE_DISARMED),
      error_flags_(ERROR_FLAG_NONE),
      last_heartbeat_time_ms_(0),
      calibration_start_time_ms_(0),
      low_batt_start_ms_(0) {}

void SafetyManager::init() {
    pinMode(PIN_STEPPER_ENABLE, OUTPUT);
    // Boot safety: Immediately tri-state/disable stepper drivers (Active LOW)
    digitalWrite(PIN_STEPPER_ENABLE, HIGH);
    
    pinMode(PIN_HARDWARE_ESTOP, INPUT_PULLUP);
    
    current_state_ = STATE_DISARMED;
    error_flags_ = ERROR_FLAG_NONE;
    last_heartbeat_time_ms_ = millis();
    low_batt_start_ms_ = 0;
}

void SafetyManager::update(uint32_t now_ms, float current_pitch_deg, float current_roll_deg, uint16_t v_batt_mv) {
    // 1. Hardware E-STOP Pin check (Active LOW if pressed or pulled low)
    if (digitalRead(PIN_HARDWARE_ESTOP) == LOW) {
        trigger_estop(4); // Hardware E-stop reason
        return;
    }

    // 2. Debounced Battery Voltage Check (Prevents false trips from 15A servo stall sags)
    if (v_batt_mv > 0 && v_batt_mv < BATTERY_VOLTAGE_MIN_MV) {
        if (low_batt_start_ms_ == 0) {
            low_batt_start_ms_ = now_ms;
        } else if ((now_ms - low_batt_start_ms_) >= 200UL) { // 200 ms persistence required
            trigger_fault(ERROR_FLAG_LOW_BATT);
            return;
        }
    } else {
        low_batt_start_ms_ = 0; // Reset debounce timer on recovery
    }

    // 3. Heartbeat Watchdog in ARMED or CALIBRATING states
    if (current_state_ == STATE_ARMED || current_state_ == STATE_CALIBRATING) {
        if ((now_ms - last_heartbeat_time_ms_) > HEARTBEAT_TIMEOUT_MS) {
            trigger_fault(ERROR_FLAG_TIMEOUT);
            return;
        }
    }

    // 4. Critical Tilt Protection when ARMED
    if (current_state_ == STATE_ARMED) {
        if (fabs(current_pitch_deg) > MAX_TILT_ANGLE_DEG || fabs(current_roll_deg) > MAX_ROLL_ANGLE_DEG) {
            trigger_fault(ERROR_FLAG_TILT);
            return;
        }
    }

    // 5. Calibration completion timer (e.g. 2000 ms stationary)
    if (current_state_ == STATE_CALIBRATING) {
        if (now_ms - calibration_start_time_ms_ >= 2000UL) {
            // Ensure level before arming
            if (fabs(current_pitch_deg) < 5.0f && fabs(current_roll_deg) < 5.0f) {
                current_state_ = STATE_ARMED;
                digitalWrite(PIN_STEPPER_ENABLE, LOW); // Enable steppers
            } else {
                trigger_fault(ERROR_FLAG_TILT);
            }
        }
    }

    // Enforce motor state
    if (current_state_ != STATE_ARMED) {
        digitalWrite(PIN_STEPPER_ENABLE, HIGH); // Cut torque
    }
}

bool SafetyManager::request_state_transition(uint8_t new_state, bool force) {
    if (new_state == current_state_) {
        return true;
    }

    // Clearing faults
    if (new_state == STATE_DISARMED && current_state_ == STATE_FAULT) {
        error_flags_ = ERROR_FLAG_NONE;
        current_state_ = STATE_DISARMED;
        digitalWrite(PIN_STEPPER_ENABLE, HIGH);
        return true;
    }

    // Transition from DISARMED to CALIBRATING
    if (new_state == STATE_CALIBRATING && (current_state_ == STATE_DISARMED || force)) {
        current_state_ = STATE_CALIBRATING;
        calibration_start_time_ms_ = millis();
        digitalWrite(PIN_STEPPER_ENABLE, HIGH);
        return true;
    }

    // Direct arming allowed only if force flag or already calibrated
    if (new_state == STATE_ARMED && force) {
        current_state_ = STATE_ARMED;
        error_flags_ = ERROR_FLAG_NONE;
        digitalWrite(PIN_STEPPER_ENABLE, LOW);
        return true;
    }

    // Normal disarm from ARMED or CALIBRATING
    if (new_state == STATE_DISARMED) {
        current_state_ = STATE_DISARMED;
        digitalWrite(PIN_STEPPER_ENABLE, HIGH);
        return true;
    }

    return false;
}

void SafetyManager::trigger_fault(uint8_t error_flag) {
    current_state_ = STATE_FAULT;
    error_flags_ |= error_flag;
    digitalWrite(PIN_STEPPER_ENABLE, HIGH); // Instantly kill stepper outputs
    Stepper.stop_all(); // Hard disable timer interrupts and zero targets
}

void SafetyManager::trigger_estop(uint8_t reason) {
    (void)reason;
    current_state_ = STATE_FAULT;
    error_flags_ |= ERROR_FLAG_ESTOP;
    digitalWrite(PIN_STEPPER_ENABLE, HIGH);
    Stepper.stop_all();
}

void SafetyManager::feed_heartbeat(uint32_t now_ms) {
    last_heartbeat_time_ms_ = now_ms;
}
