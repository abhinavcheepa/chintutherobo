#ifndef COMMS_H
#define COMMS_H

#include <Arduino.h>
#include "protocol.h"

class CommsManager {
public:
    CommsManager();
    void init();
    void process_incoming();
    void send_telemetry(const TelemetryPayload &telemetry);
    void send_ack_nack(uint8_t msg_type, uint8_t status, uint16_t error_code);
    void send_heartbeat_pong(uint32_t timestamp_ms);

    // Latest commanded values
    const CmdMotionPayload& get_latest_motion_cmd() const { return latest_cmd_motion_; }
    void zero_motion_cmd() {
        latest_cmd_motion_.target_vel_x = 0;
        latest_cmd_motion_.target_yaw_rate = 0;
    }
    bool has_new_motion_cmd() {
        bool flag = new_motion_cmd_available_;
        new_motion_cmd_available_ = false;
        return flag;
    }

private:
    enum RxState {
        STATE_WAIT_SYNC0,
        STATE_WAIT_SYNC1,
        STATE_WAIT_LEN,
        STATE_WAIT_SEQ,
        STATE_WAIT_TYPE,
        STATE_READ_PAYLOAD,
        STATE_WAIT_CRC_L,
        STATE_WAIT_CRC_H
    };

    RxState rx_state_;
    uint8_t rx_len_;
    uint8_t rx_seq_;
    uint8_t rx_type_;
    uint8_t rx_payload_[64];
    uint8_t rx_payload_idx_;
    uint16_t rx_crc_received_;
    uint32_t rx_last_byte_time_ms_;
    
    uint8_t tx_seq_;

    CmdMotionPayload latest_cmd_motion_;
    bool new_motion_cmd_available_;

    void handle_packet();
    void send_frame(uint8_t msg_type, const uint8_t *payload, uint8_t length);
};

extern CommsManager Comms;

#endif // COMMS_H
