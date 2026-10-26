#ifndef SAFETY_H
#define SAFETY_H

#include <Arduino.h>
#include "protocol.h"
#include "config.h"

class SafetyManager {
public:
    SafetyManager();
    void init();
    void update(uint32_t now_ms, float current_pitch_deg, float current_roll_deg, uint16_t v_batt_mv);
    
    // State query & transition
    uint8_t get_state() const { return current_state_; }
    uint8_t get_error_flags() const { return error_flags_; }
    bool is_armed() const { return current_state_ == STATE_ARMED; }
    
    bool request_state_transition(uint8_t new_state, bool force = false);
    void trigger_fault(uint8_t error_flag);
    void trigger_estop(uint8_t reason);
    
    // Watchdog feed
    void feed_heartbeat(uint32_t now_ms);

private:
    uint8_t  current_state_;
    uint8_t  error_flags_;
    uint32_t last_heartbeat_time_ms_;
    uint32_t calibration_start_time_ms_;
    uint32_t low_batt_start_ms_;
};

extern SafetyManager Safety;

#endif // SAFETY_H
