#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
// HARDWARE PIN DEFINITIONS
// ============================================================================

// Stepper Drivers (A4988 / TMC2209 STEP/DIR interface)
// Left Stepper
#define PIN_STEP_LEFT       5   // Controlled via Timer3 compare match
#define PIN_DIR_LEFT        6   // Direction left
// Right Stepper
#define PIN_STEP_RIGHT      7   // Controlled via Timer4 compare match
#define PIN_DIR_RIGHT       8   // Direction right
// Stepper Global Enable (Active Low)
#define PIN_STEPPER_ENABLE  4   // LOW = Enabled, HIGH = Tri-stated / Disabled

// Servo Channels (MG995, 50 Hz PWM on Timer5 on Mega2560)
// Pins 44, 45, 46, 11, 12, 13 are driven cleanly by Servo library on Mega
#define PIN_SERVO_HIP_ROLL_L   44
#define PIN_SERVO_HIP_PITCH_L  45
#define PIN_SERVO_KNEE_L       46

#define PIN_SERVO_HIP_ROLL_R   11
#define PIN_SERVO_HIP_PITCH_R  12
#define PIN_SERVO_KNEE_R       38

// Sensors & Inputs
#define PIN_MPU_SDA         20  // Standard Mega I2C SDA
#define PIN_MPU_SCL         21  // Standard Mega I2C SCL
#define PIN_BATT_ADC        A0  // Voltage divider sensing DC bus
#define PIN_HARDWARE_ESTOP  2   // Hardware E-stop interrupt (Active LOW, pull-up)

// Status LED
#define PIN_LED_STATUS      13  // Dedicated onboard status LED

// ============================================================================
// COMMUNICATION & LOOP TIMING
// ============================================================================
#define SERIAL_BAUD_RATE    250000UL
#define I2C_CLOCK_SPEED     400000UL

#define LOOP_RATE_BALANCE_HZ   200       // 5.0 ms
#define LOOP_DT_BALANCE_S      0.005f    // dt in seconds
#define LOOP_DT_BALANCE_US     5000UL    // dt in microseconds

#define LOOP_RATE_TELEMETRY_HZ 20        // 50.0 ms
#define LOOP_DT_TELEMETRY_MS   50UL

// ============================================================================
// PHYSICAL & KINEMATIC CONSTANTS
// ============================================================================
#define ROBOT_TOTAL_MASS_G     1178.0f
#define WHEEL_DIAMETER_MM      80.0f
#define WHEEL_RADIUS_M         0.040f
#define WHEEL_CIRCUMFERENCE_M  0.251327f

// Stepper geometry: 1.8 deg/step, 16 microsteps = 3200 steps/rev
#define STEPS_PER_REV          3200.0f
#define STEPS_PER_METER        (STEPS_PER_REV / WHEEL_CIRCUMFERENCE_M) // ~12732.4 steps/m
#define MM_PER_STEP            (WHEEL_CIRCUMFERENCE_M * 1000.0f / STEPS_PER_REV)

// Leg link lengths (3-link planar model)
#define LINK1_HIP_MM           72.0f
#define LINK2_THIGH_MM         120.0f
#define LINK3_SHANK_MM         101.0f

// Leg Height Limits
#define LEG_HEIGHT_MIN_MM      80.0f
#define LEG_HEIGHT_MAX_MM      180.0f
#define LEG_HEIGHT_NOMINAL_MM  118.0f

// Stepper Motor Limits
#define STEPPER_MAX_SPEED_STEPS_SEC 24000.0f // ~1.88 m/s
#define STEPPER_MAX_ACCEL_STEPS_S2  48000.0f // ~3.77 m/s^2

// ============================================================================
// SAFETY THRESHOLDS
// ============================================================================
#define MAX_TILT_ANGLE_DEG        45.0f   // Cutoff pitch angle
#define MAX_ROLL_ANGLE_DEG        35.0f   // Cutoff roll angle
#define HEARTBEAT_TIMEOUT_MS      400UL   // Pi communication timeout
#define BATTERY_VOLTAGE_MIN_MV    9600    // 3S LiPo cutoff (3.2V/cell)
#define BATTERY_VOLTAGE_MAX_MV    12600   // 3S LiPo full (4.2V/cell)
#define BATTERY_ADC_DIVIDER_RATIO 4.20f   // (R1+R2)/R2 calibrated divider ratio

// ============================================================================
// SERVO CALIBRATION & SLEW LIMITS
// ============================================================================
#define SERVO_PULSE_MIN_US        600
#define SERVO_PULSE_MAX_US        2400
#define SERVO_MAX_SLEW_DEG_PER_SEC 180.0f // Max angle change per second

// Default servo neutral offsets in microseconds (trim values)
#define TRIM_SERVO_HIP_ROLL_L   0
#define TRIM_SERVO_HIP_PITCH_L  0
#define TRIM_SERVO_KNEE_L       0
#define TRIM_SERVO_HIP_ROLL_R   0
#define TRIM_SERVO_HIP_PITCH_R  0
#define TRIM_SERVO_KNEE_R       0

// ============================================================================
// EEPROM STORAGE CONFIGURATION
// ============================================================================
#define EEPROM_MAGIC_HEADER       0xBEEF2560UL
#define EEPROM_CONFIG_START_ADDR  0x0000

#endif // CONFIG_H
