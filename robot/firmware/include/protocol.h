#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define PROTOCOL_SYNC_0 0xAA
#define PROTOCOL_SYNC_1 0x55

// Message Types
#define MSG_CMD_MOTION       0x01
#define MSG_TELEMETRY        0x02
#define MSG_CONFIG_PID_SET   0x03
#define MSG_CONFIG_PID_GET   0x04
#define MSG_CMD_ARM_STATE    0x05
#define MSG_HEARTBEAT        0x06
#define MSG_ACK_NACK         0x07
#define MSG_CONFIG_SAVE      0x08
#define MSG_EMERGENCY_STOP   0xFF

// ACK/NACK Status Codes
#define ACK_STATUS_OK        0x00
#define ACK_STATUS_CRC_ERR   0x01
#define ACK_STATUS_BOUNDS_ERR 0x02
#define ACK_STATUS_STATE_ERR 0x03

// Robot States
#define STATE_DISARMED       0x00
#define STATE_CALIBRATING    0x01
#define STATE_ARMED          0x02
#define STATE_FAULT          0x03

// Fault / Error Flags Bitmask
#define ERROR_FLAG_NONE      0x00
#define ERROR_FLAG_TILT      0x01
#define ERROR_FLAG_TIMEOUT   0x02
#define ERROR_FLAG_LOW_BATT  0x04
#define ERROR_FLAG_MOTOR     0x08
#define ERROR_FLAG_ESTOP     0x10

#pragma pack(push, 1)

struct CmdMotionPayload {
    int16_t  target_vel_x;    // mm/s (-1000 to +1000)
    int16_t  target_yaw_rate; // mrad/s (-3141 to +3141)
    uint16_t leg_height_l;    // mm (80 to 180)
    uint16_t leg_height_r;    // mm (80 to 180)
    int16_t  roll_trim;       // mrad (-350 to +350)
    uint8_t  flags;           // Bit 0: Balance enable, Bit 1: Height slew limit
    uint8_t  reserved;        // Alignment padding
    uint16_t command_id;      // Sequence tracking
};

struct TelemetryPayload {
    int16_t  pitch_cdeg;      // 0.01 deg
    int16_t  pitch_rate_cdeg; // 0.01 deg/s
    int16_t  roll_cdeg;       // 0.01 deg
    int16_t  yaw_rate_cdeg;   // 0.01 deg/s
    int32_t  wheel_pos_l;     // Accumulated steps
    int32_t  wheel_pos_r;     // Accumulated steps
    int16_t  wheel_vel_l;     // steps/s
    int16_t  wheel_vel_r;     // steps/s
    uint16_t leg_pos_l;       // mm
    uint16_t leg_pos_r;       // mm
    uint16_t v_batt_mv;       // millivolts
    uint8_t  state_code;      // 0: DISARMED, 1: CALIB, 2: ARMED, 3: FAULT
    uint8_t  error_flags;     // Bitmask
    uint16_t loop_jitter_us;  // Microseconds
    uint16_t last_cmd_id;     // Latency trace
    uint8_t  reserved[4];
};

struct ConfigPidSetPayload {
    uint8_t controller_id;    // 0: Pitch Balance, 1: Velocity/Pos, 2: Yaw
    uint8_t save_to_eeprom;   // 1 = write to EEPROM
    float   kp;
    float   ki;
    float   kd;
    float   k_ff;
    float   out_min;
    float   out_max;
};

struct CmdArmStatePayload {
    uint8_t requested_state;  // 0: DISARM, 1: CALIB, 2: ARM, 3: CLEAR_FAULT
    uint8_t force;
};

struct HeartbeatPayload {
    uint32_t timestamp_ms;
};

struct AckNackPayload {
    uint8_t  acked_msg_type;
    uint8_t  status;
    uint16_t error_code;
};

struct EmergencyStopPayload {
    uint8_t reason_code;      // 1: UI, 2: Watchdog, 3: Tilt, 4: Hardware Pin
    uint8_t reserved;
};

#pragma pack(pop)

/**
 * @brief Computes CRC-16-CCITT checksum over given buffer.
 * Polynomial: 0x1021, Initial value: 0xFFFF.
 */
static inline uint16_t calculate_crc16(const uint8_t *data, uint8_t length) {
    uint16_t crc = 0xFFFF;
    for (uint8_t i = 0; i < length; i++) {
        crc ^= ((uint16_t)data[i]) << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

#endif // PROTOCOL_H
