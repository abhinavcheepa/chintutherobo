#include "comms.h"
#include "config.h"
#include "safety.h"
#include "balance.h"

CommsManager Comms;

CommsManager::CommsManager()
    : rx_state_(STATE_WAIT_SYNC0),
      rx_len_(0),
      rx_seq_(0),
      rx_type_(0),
      rx_payload_idx_(0),
      rx_crc_received_(0),
      rx_last_byte_time_ms_(0),
      tx_seq_(0),
      new_motion_cmd_available_(false) {
    memset(&latest_cmd_motion_, 0, sizeof(latest_cmd_motion_));
    latest_cmd_motion_.leg_height_l = (uint16_t)LEG_HEIGHT_NOMINAL_MM;
    latest_cmd_motion_.leg_height_r = (uint16_t)LEG_HEIGHT_NOMINAL_MM;
}

void CommsManager::init() {
    Serial.begin(SERIAL_BAUD_RATE);
}

void CommsManager::send_frame(uint8_t msg_type, const uint8_t *payload, uint8_t length) {
    // Frame: [SYNC_0][SYNC_1][LEN][SEQ][TYPE][PAYLOAD...][CRC_L][CRC_H]
    uint8_t header[5];
    header[0] = PROTOCOL_SYNC_0;
    header[1] = PROTOCOL_SYNC_1;
    header[2] = length;
    header[3] = tx_seq_++;
    header[4] = msg_type;

    // Compute CRC over LENGTH, SEQ, TYPE, and PAYLOAD
    uint8_t crc_buffer[3 + 64];
    crc_buffer[0] = header[2];
    crc_buffer[1] = header[3];
    crc_buffer[2] = header[4];
    if (length > 0 && payload != nullptr) {
        memcpy(&crc_buffer[3], payload, length);
    }
    uint16_t crc = calculate_crc16(crc_buffer, 3 + length);

    // Send frame atomically
    Serial.write(header, 5);
    if (length > 0 && payload != nullptr) {
        Serial.write(payload, length);
    }
    Serial.write((uint8_t)(crc & 0xFF));        // Low byte
    Serial.write((uint8_t)((crc >> 8) & 0xFF)); // High byte
}

void CommsManager::send_telemetry(const TelemetryPayload &telemetry) {
    send_frame(MSG_TELEMETRY, (const uint8_t *)&telemetry, sizeof(TelemetryPayload));
}

void CommsManager::send_ack_nack(uint8_t msg_type, uint8_t status, uint16_t error_code) {
    AckNackPayload ack;
    ack.acked_msg_type = msg_type;
    ack.status = status;
    ack.error_code = error_code;
    send_frame(MSG_ACK_NACK, (const uint8_t *)&ack, sizeof(AckNackPayload));
}

void CommsManager::send_heartbeat_pong(uint32_t timestamp_ms) {
    HeartbeatPayload hb;
    hb.timestamp_ms = timestamp_ms;
    send_frame(MSG_HEARTBEAT, (const uint8_t *)&hb, sizeof(HeartbeatPayload));
}

void CommsManager::process_incoming() {
    uint32_t now = millis();

    // Inter-byte timeout: reset parser if incomplete frame stalled for > 40 ms
    if (rx_state_ != STATE_WAIT_SYNC0 && (now - rx_last_byte_time_ms_) > 40UL) {
        rx_state_ = STATE_WAIT_SYNC0;
    }

    while (Serial.available() > 0) {
        rx_last_byte_time_ms_ = millis();
        uint8_t byte = Serial.read();

        switch (rx_state_) {
            case STATE_WAIT_SYNC0:
                if (byte == PROTOCOL_SYNC_0) {
                    rx_state_ = STATE_WAIT_SYNC1;
                }
                break;

            case STATE_WAIT_SYNC1:
                if (byte == PROTOCOL_SYNC_1) {
                    rx_state_ = STATE_WAIT_LEN;
                } else {
                    rx_state_ = STATE_WAIT_SYNC0;
                }
                break;

            case STATE_WAIT_LEN:
                rx_len_ = byte;
                if (rx_len_ > sizeof(rx_payload_)) {
                    // Packet exceeds maximum allowed payload, resync
                    rx_state_ = STATE_WAIT_SYNC0;
                } else {
                    rx_state_ = STATE_WAIT_SEQ;
                }
                break;

            case STATE_WAIT_SEQ:
                rx_seq_ = byte;
                rx_state_ = STATE_WAIT_TYPE;
                break;

            case STATE_WAIT_TYPE:
                rx_type_ = byte;
                rx_payload_idx_ = 0;
                if (rx_len_ == 0) {
                    rx_state_ = STATE_WAIT_CRC_L;
                } else {
                    rx_state_ = STATE_READ_PAYLOAD;
                }
                break;

            case STATE_READ_PAYLOAD:
                rx_payload_[rx_payload_idx_++] = byte;
                if (rx_payload_idx_ >= rx_len_) {
                    rx_state_ = STATE_WAIT_CRC_L;
                }
                break;

            case STATE_WAIT_CRC_L:
                rx_crc_received_ = byte;
                rx_state_ = STATE_WAIT_CRC_H;
                break;

            case STATE_WAIT_CRC_H: {
                rx_crc_received_ |= ((uint16_t)byte << 8);

                // Compute CRC over LEN, SEQ, TYPE, and PAYLOAD
                uint8_t crc_buf[3 + 64];
                crc_buf[0] = rx_len_;
                crc_buf[1] = rx_seq_;
                crc_buf[2] = rx_type_;
                if (rx_len_ > 0) {
                    memcpy(&crc_buf[3], rx_payload_, rx_len_);
                }
                uint16_t calculated_crc = calculate_crc16(crc_buf, 3 + rx_len_);

                if (calculated_crc == rx_crc_received_) {
                    handle_packet();
                } else {
                    // Send NACK CRC error
                    send_ack_nack(rx_type_, ACK_STATUS_CRC_ERR, calculated_crc);
                }

                rx_state_ = STATE_WAIT_SYNC0;
                break;
            }
        }
    }
}

void CommsManager::handle_packet() {
    uint32_t now = millis();

    switch (rx_type_) {
        case MSG_CMD_MOTION:
            if (rx_len_ == sizeof(CmdMotionPayload)) {
                memcpy(&latest_cmd_motion_, rx_payload_, sizeof(CmdMotionPayload));
                new_motion_cmd_available_ = true;
                Safety.feed_heartbeat(now);
            }
            break;

        case MSG_HEARTBEAT:
            if (rx_len_ == sizeof(HeartbeatPayload)) {
                HeartbeatPayload hb;
                memcpy(&hb, rx_payload_, sizeof(HeartbeatPayload));
                Safety.feed_heartbeat(now);
                send_heartbeat_pong(hb.timestamp_ms);
            }
            break;

        case MSG_CMD_ARM_STATE:
            if (rx_len_ == sizeof(CmdArmStatePayload)) {
                CmdArmStatePayload arm_cmd;
                memcpy(&arm_cmd, rx_payload_, sizeof(CmdArmStatePayload));
                bool ok = Safety.request_state_transition(arm_cmd.requested_state, arm_cmd.force != 0);
                send_ack_nack(MSG_CMD_ARM_STATE, ok ? ACK_STATUS_OK : ACK_STATUS_STATE_ERR, Safety.get_state());
            }
            break;

        case MSG_CONFIG_PID_SET:
            if (rx_len_ == sizeof(ConfigPidSetPayload)) {
                ConfigPidSetPayload cfg;
                memcpy(&cfg, rx_payload_, sizeof(ConfigPidSetPayload));
                PidGains g = {cfg.kp, cfg.ki, cfg.kd, cfg.k_ff, cfg.out_min, cfg.out_max};
                bool ok = Balance.set_pid_gains(cfg.controller_id, g, cfg.save_to_eeprom != 0);
                send_ack_nack(MSG_CONFIG_PID_SET, ok ? ACK_STATUS_OK : ACK_STATUS_BOUNDS_ERR, cfg.controller_id);
            }
            break;

        case MSG_CONFIG_SAVE:
            Balance.save_eeprom();
            send_ack_nack(MSG_CONFIG_SAVE, ACK_STATUS_OK, 0);
            break;

        case MSG_EMERGENCY_STOP:
            Safety.trigger_estop(1); // Software E-Stop
            send_ack_nack(MSG_EMERGENCY_STOP, ACK_STATUS_OK, 0);
            break;

        default:
            send_ack_nack(rx_type_, ACK_STATUS_BOUNDS_ERR, 0xFFFF);
            break;
    }
}
