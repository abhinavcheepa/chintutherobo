#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "safety.h"
#include "imu.h"
#include "estimator.h"
#include "legs_ik.h"
#include "servos.h"
#include "stepper_isr.h"
#include "balance.h"
#include "comms.h"

// Loop timing registers
static uint32_t last_balance_tick_us = 0;
static uint32_t last_telemetry_tick_ms = 0;
static uint16_t peak_loop_jitter_us = 0;

static uint16_t read_battery_voltage_mv() {
    int raw_adc = analogRead(PIN_BATT_ADC);
    // ADC reference = 5.0V (5000 mV) / 1023
    float pin_voltage_mv = (float)raw_adc * (5000.0f / 1023.0f);
    float bus_voltage_mv = pin_voltage_mv * BATTERY_ADC_DIVIDER_RATIO;
    return (uint16_t)bus_voltage_mv;
}

void setup() {
    // 1. Initialize Communications
    Comms.init();

    // 2. Initialize Safety Subsystem (ensures motors disabled on boot)
    Safety.init();

    // 3. Initialize Sensors
    IMU.init();
    // Calibrate stationary gyro bias
    IMU.calibrate_gyro(300);

    // 4. Initialize State Estimator
    Estimator.reset();

    // 5. Initialize Actuators
    Stepper.init();
    Servos.init();

    // 6. Initialize Balance Controller & Load EEPROM
    Balance.init();

    last_balance_tick_us = micros();
    last_telemetry_tick_ms = millis();
}

void loop() {
    uint32_t now_us = micros();
    uint32_t now_ms = millis();

    // 1. Continuous Serial Processing
    Comms.process_incoming();

    // 2. Hard Real-Time 200 Hz Balance & Estimation Loop (Every 5000 us)
    if ((now_us - last_balance_tick_us) >= LOOP_DT_BALANCE_US) {
        uint32_t loop_actual_dt = now_us - last_balance_tick_us;
        last_balance_tick_us = now_us;

        // Measure execution jitter
        int32_t jitter = (int32_t)loop_actual_dt - (int32_t)LOOP_DT_BALANCE_US;
        uint16_t abs_jitter = (uint16_t)abs(jitter);
        if (abs_jitter > peak_loop_jitter_us) {
            peak_loop_jitter_us = abs_jitter;
        }

        // 2.1 Sensor Read
        IMU.read_sensor();

        // 2.2 State Estimation
        Estimator.update(
            IMU.get_accel_x(), IMU.get_accel_y(), IMU.get_accel_z(),
            IMU.get_gyro_x(), IMU.get_gyro_y(), IMU.get_gyro_z(),
            LOOP_DT_BALANCE_S
        );

        float pitch = Estimator.get_pitch_deg();
        float pitch_rate = Estimator.get_pitch_rate_dps();
        float roll = Estimator.get_roll_deg();
        uint16_t v_batt = read_battery_voltage_mv();

        // 2.3 Safety Supervisor Update
        Safety.update(now_ms, pitch, roll, v_batt);

        // 2.4 Control & Kinematics Execution
        if (Safety.is_armed()) {
            const CmdMotionPayload &cmd = Comms.get_latest_motion_cmd();

            // Leg IK Solutions
            LegJointAngles joints_l, joints_r;
            float roll_trim_deg = (float)cmd.roll_trim / 1000.0f * (180.0f / M_PI);
            LegsIK.solve_leg_ik((float)cmd.leg_height_l, 0.0f, roll_trim_deg, true, joints_l);
            LegsIK.solve_leg_ik((float)cmd.leg_height_r, 0.0f, roll_trim_deg, false, joints_r);

            Servos.set_target_joints_left(joints_l);
            Servos.set_target_joints_right(joints_r);

            // Balance Computation
            float avg_height = ((float)cmd.leg_height_l + (float)cmd.leg_height_r) * 0.5f;
            float step_rate_l = 0.0f;
            float step_rate_r = 0.0f;

            if (cmd.flags & 0x01) { // Balance Enabled flag
                Balance.compute(
                    pitch, pitch_rate,
                    (float)cmd.target_vel_x, (float)cmd.target_yaw_rate,
                    avg_height, LOOP_DT_BALANCE_S,
                    (float)Stepper.get_current_speed_left(),
                    (float)Stepper.get_current_speed_right(),
                    step_rate_l, step_rate_r
                );
            } else {
                // Direct velocity drive without balance (bench testing mode)
                step_rate_l = (float)cmd.target_vel_x * (STEPS_PER_METER / 1000.0f);
                step_rate_r = (float)cmd.target_vel_x * (STEPS_PER_METER / 1000.0f);
            }

            Stepper.set_target_speeds(step_rate_l, step_rate_r);
        } else {
            // Safe standby: zero all motor commands
            Stepper.stop_all();
            Balance.reset();
            Comms.zero_motion_cmd();

            // Slew servos to safe neutral nominal stance
            LegJointAngles nominal_l, nominal_r;
            LegsIK.solve_leg_ik(LEG_HEIGHT_NOMINAL_MM, 0.0f, 0.0f, true, nominal_l);
            LegsIK.solve_leg_ik(LEG_HEIGHT_NOMINAL_MM, 0.0f, 0.0f, false, nominal_r);
            Servos.set_target_joints_left(nominal_l);
            Servos.set_target_joints_right(nominal_r);
        }

        // 2.5 Actuator Dynamic Updates (Only ramp steppers when armed)
        if (Safety.is_armed()) {
            Stepper.update_ramp(LOOP_DT_BALANCE_S);
        }
        Servos.update(LOOP_DT_BALANCE_S);
    }

    // 3. Telemetry Broadcast Loop (20 Hz / Every 50 ms)
    if ((now_ms - last_telemetry_tick_ms) >= LOOP_DT_TELEMETRY_MS) {
        last_telemetry_tick_ms = now_ms;

        TelemetryPayload telem;
        telem.pitch_cdeg      = (int16_t)(Estimator.get_pitch_deg() * 100.0f);
        telem.pitch_rate_cdeg = (int16_t)(Estimator.get_pitch_rate_dps() * 100.0f);
        telem.roll_cdeg       = (int16_t)(Estimator.get_roll_deg() * 100.0f);
        telem.yaw_rate_cdeg   = (int16_t)(Estimator.get_yaw_rate_dps() * 100.0f);

        telem.wheel_pos_l     = Stepper.get_position_left();
        telem.wheel_pos_r     = Stepper.get_position_right();
        telem.wheel_vel_l     = Stepper.get_current_speed_left();
        telem.wheel_vel_r     = Stepper.get_current_speed_right();

        const CmdMotionPayload &cmd = Comms.get_latest_motion_cmd();
        telem.leg_pos_l       = cmd.leg_height_l;
        telem.leg_pos_r       = cmd.leg_height_r;

        telem.v_batt_mv       = read_battery_voltage_mv();
        telem.state_code      = Safety.get_state();
        telem.error_flags     = Safety.get_error_flags();
        telem.loop_jitter_us  = peak_loop_jitter_us;
        telem.last_cmd_id     = cmd.command_id;
        telem.reserved[0]     = 0;
        telem.reserved[1]     = 0;
        telem.reserved[2]     = 0;
        telem.reserved[3]     = 0;

        Comms.send_telemetry(telem);

        // Reset peak jitter tracker for the next telemetry period
        peak_loop_jitter_us = 0;
    }
}
