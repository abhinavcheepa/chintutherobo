# Robot Communication Protocol Specification (Pi <-> Mega & Pi <-> Web UI)

## 1. Overview
The communication architecture consists of two distinct tiers:
1. **Tier 1 (High Reliability Embedded Link):** Raspberry Pi $\longleftrightarrow$ Arduino Mega 2560 via USB Serial (`/dev/ttyACM0` or `/dev/ttyUSB0`) running at **250,000 baud**, 8N1. Uses a framed binary protocol with CRC16-CCITT for deterministic throughput and minimal AVR cycle overhead.
2. **Tier 2 (Telemetry & Control Interface):** Raspberry Pi $\longleftrightarrow$ Web Client via WebSocket (`ws://192.168.4.1:8765/ws`) exchanging JSON payloads validated against Pydantic schemas.

---

## 2. Tier 1: Pi $\longleftrightarrow$ Mega Framed Binary Serial Protocol

### 2.1 Packet Frame Format
Every frame transmitted across the serial interface strictly adheres to the following structure:

```
+------------+------------+--------+--------+----------+-------------------+------------+------------+
| SYNC_0     | SYNC_1     | LENGTH | SEQ    | MSG_TYPE | PAYLOAD           | CRC16_L    | CRC16_H    |
| 1 Byte     | 1 Byte     | 1 Byte | 1 Byte | 1 Byte   | N Bytes           | 1 Byte     | 1 Byte     |
| 0xAA       | 0x55       | N      | 0..255 | ID       | Binary data       | Low byte   | High byte  |
+------------+------------+--------+--------+----------+-------------------+------------+------------+
```

- **`SYNC_0` (0xAA), `SYNC_1` (0x55):** Fixed 2-byte preamble for frame synchronization.
- **`LENGTH`:** Size of the payload field in bytes ($N \le 64$).
- **`SEQ`:** 8-bit rolling sequence counter incremented on every transmission.
- **`MSG_TYPE`:** Identifies payload schema.
- **`PAYLOAD`:** Little-endian packed binary struct of length $N$.
- **`CRC16`:** 16-bit CRC calculated over `LENGTH`, `SEQ`, `MSG_TYPE`, and `PAYLOAD` using CRC-16-CCITT (Polynomial `0x1021`, Initial value `0xFFFF`, no reflection, final XOR `0x0000`).

### 2.2 Message Types (`MSG_TYPE`)
| ID | Name | Direction | Target Rate | Description |
|---|---|---|---|---|
| `0x01` | `CMD_MOTION` | Pi $\rightarrow$ Mega | 20 Hz | Linear/angular setpoints, leg heights, balance flags |
| `0x02` | `TELEMETRY` | Mega $\rightarrow$ Pi | 20 Hz (or 50 Hz) | IMU state, wheel velocities, battery, jitter, state |
| `0x03` | `CONFIG_PID_SET` | Pi $\rightarrow$ Mega | On-demand | Write PID/controller gains to memory |
| `0x04` | `CONFIG_PID_GET` | Pi $\rightarrow$ Mega | On-demand | Query PID gains for specified controller ID |
| `0x05` | `CMD_ARM_STATE` | Pi $\rightarrow$ Mega | On-demand | Request state transition (Disarm, Calibrate, Arm) |
| `0x06` | `HEARTBEAT` | Pi $\longleftrightarrow$ Mega | 5-10 Hz | Keep-alive packet with sender timestamp |
| `0x07` | `ACK_NACK` | Pi $\longleftrightarrow$ Mega | On-demand | Acknowledgment or error report for request packets |
| `0x08` | `CONFIG_SAVE_EEPROM` | Pi $\rightarrow$ Mega | On-demand | Save current RAM PID parameters to EEPROM |
| `0xFF` | `EMERGENCY_STOP` | Bidirectional | Immediate | Zero-torque kill command with fault code |

### 2.3 Detailed Payload Layouts (C Struct Packing)

#### 2.3.1 `CMD_MOTION` (`MSG_TYPE = 0x01`, Length: 14 Bytes)
```c
struct __attribute__((packed)) CmdMotionPayload {
    int16_t  target_vel_x;    // Linear velocity setpoint (mm/s, e.g. -1000 to +1000)
    int16_t  target_yaw_rate; // Yaw angular rate setpoint (mrad/s, e.g. -3141 to +3141)
    uint16_t leg_height_l;    // Left leg vertical height target (mm, 80 to 180)
    uint16_t leg_height_r;    // Right leg vertical height target (mm, 80 to 180)
    int16_t  roll_trim;       // Roll trim offset for leveling (mrad, -350 to +350)
    uint8_t  flags;           // Bit 0: Balance Enable, Bit 1: Height Slew Limit, Bit 2..7: Reserved
    uint8_t  reserved;        // Alignment padding (must be 0)
    uint16_t command_id;      // Monotonically increasing command sequence identifier
};
```

#### 2.3.2 `TELEMETRY` (`MSG_TYPE = 0x02`, Length: 36 Bytes)
```c
struct __attribute__((packed)) TelemetryPayload {
    int16_t  pitch_cdeg;       // Robot pitch angle in 0.01 deg (e.g. 150 = 1.50 deg)
    int16_t  pitch_rate_cdeg;  // Pitch angular velocity in 0.01 deg/s
    int16_t  roll_cdeg;        // Robot roll angle in 0.01 deg
    int16_t  yaw_rate_cdeg;    // Yaw angular velocity in 0.01 deg/s
    int32_t  wheel_pos_l;      // Accumulated left stepper steps
    int32_t  wheel_pos_r;      // Accumulated right stepper steps
    int16_t  wheel_vel_l;      // Current left stepper speed in steps/s
    int16_t  wheel_vel_r;      // Current right stepper speed in steps/s
    uint16_t leg_pos_l;        // Actual computed left leg height in mm
    uint16_t leg_pos_r;        // Actual computed right leg height in mm
    uint16_t v_batt_mv;        // Battery bus voltage in millivolts (e.g. 11840 = 11.84V)
    uint8_t  state_code;       // 0: DISARMED, 1: CALIBRATING, 2: ARMED, 3: FAULT
    uint8_t  error_flags;      // Bit 0: Tilt, Bit 1: Timeout, Bit 2: LowBat, Bit 3: MotorFault
    uint16_t loop_jitter_us;   // Peak 200 Hz balance loop execution jitter (microseconds)
    uint16_t last_cmd_id;      // Last command ID executed (round-trip latency tracking)
    uint8_t  reserved[3];      // Padding bytes
};
```

#### 2.3.3 `CONFIG_PID_SET` (`MSG_TYPE = 0x03`, Length: 26 Bytes)
```c
struct __attribute__((packed)) ConfigPidSetPayload {
    uint8_t controller_id;     // 0: Pitch Balance PID, 1: Velocity/Pos PID, 2: Yaw PID
    uint8_t save_to_eeprom;    // 1: Commit to EEPROM after setting, 0: RAM only
    float   kp;                // Proportional gain
    float   ki;                // Integral gain
    float   kd;                // Derivative gain
    float   k_ff;              // Feedforward / Inertia compensation gain
    float   out_min;           // Output limit low (e.g. -max_steps_per_sec)
    float   out_max;           // Output limit high (e.g. +max_steps_per_sec)
};
```

#### 2.3.4 `CMD_ARM_STATE` (`MSG_TYPE = 0x05`, Length: 2 Bytes)
```c
struct __attribute__((packed)) CmdArmStatePayload {
    uint8_t requested_state;   // 0: DISARM, 1: CALIBRATE, 2: ARM, 3: CLEAR_FAULT
    uint8_t force;             // 1: Force state transition, 0: Safe transition
};
```

#### 2.3.5 `HEARTBEAT` (`MSG_TYPE = 0x06`, Length: 4 Bytes)
```c
struct __attribute__((packed)) HeartbeatPayload {
    uint32_t timestamp_ms;     // Sender monotonic timestamp (millis)
};
```

#### 2.3.6 `ACK_NACK` (`MSG_TYPE = 0x07`, Length: 4 Bytes)
```c
struct __attribute__((packed)) AckNackPayload {
    uint8_t  acked_msg_type;   // MSG_TYPE of the packet being acknowledged
    uint8_t  status;           // 0: ACK_OK, 1: NACK_CRC, 2: NACK_BOUNDS, 3: NACK_STATE
    uint16_t error_code;       // Detailed error reason or zero
};
```

#### 2.3.7 `EMERGENCY_STOP` (`MSG_TYPE = 0xFF`, Length: 2 Bytes)
```c
struct __attribute__((packed)) EmergencyStopPayload {
    uint8_t reason_code;       // 1: UI_BUTTON, 2: WATCHDOG, 3: CRITICAL_TILT, 4: BROWNOUT
    uint8_t reserved;          // Padding
};
```

---

## 3. Tier 2: Pi $\longleftrightarrow$ Web UI WebSocket Protocol

The Web UI connects to `ws://<pi-ip>:8765/ws?token=<token>`.

### 3.1 Client to Pi Commands

#### Motion Control (`command`)
```json
{
  "type": "command",
  "linear_x": 0.45,
  "angular_z": -0.15,
  "leg_height_l": 130.0,
  "leg_height_r": 130.0,
  "roll_trim": 0.0,
  "balance_enable": true
}
```

#### Arm / Disarm State Request (`arm_state`)
```json
{
  "type": "arm_state",
  "state": "ARMED"
}
```
*Valid states:* `"DISARMED"`, `"CALIBRATING"`, `"ARMED"`, `"CLEAR_FAULT"`.

#### Emergency Stop (`estop`)
```json
{
  "type": "estop",
  "reason": "USER_ACTION"
}
```

#### PID Tuning Set (`pid_set`)
```json
{
  "type": "pid_set",
  "controller_id": 0,
  "save_to_eeprom": true,
  "kp": 32.5,
  "ki": 0.20,
  "kd": 1.65,
  "k_ff": 0.08,
  "out_min": -4000.0,
  "out_max": 4000.0
}
```

### 3.2 Pi to Client Telemetry Broadcast (20 Hz)
```json
{
  "type": "telemetry",
  "timestamp": 1771932500.412,
  "state": "ARMED",
  "state_code": 2,
  "pose": {
    "pitch": 1.45,
    "pitch_rate": -0.12,
    "roll": 0.05,
    "yaw_rate": 0.00
  },
  "wheels": {
    "pos_left": 23410,
    "pos_right": 23395,
    "vel_left": 412.0,
    "vel_right": 410.5
  },
  "legs": {
    "height_left": 130.0,
    "height_right": 130.0,
    "joints_left": [12.4, 46.2, -61.0],
    "joints_right": [12.4, 46.2, -61.0]
  },
  "power": {
    "battery_voltage": 11.92,
    "low_battery": false
  },
  "diagnostics": {
    "loop_jitter_us": 14,
    "error_flags": 0,
    "error_desc": "NOMINAL"
  }
}
```
