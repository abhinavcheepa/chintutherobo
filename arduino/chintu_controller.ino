/*
  CHINTU Defence Bot - Arduino Mega 2560 controller
  IMPORTANT:
  - Balance mode is deliberately DISABLED until wheel/joint assignments are confirmed.
  - This is a safe integration scaffold, not a validated balancing controller.
  Required Arduino libraries:
    Adafruit MPU6050, Adafruit Unified Sensor, Adafruit PWM Servo Driver,
    AccelStepper
*/
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_PWMServoDriver.h>
#include <AccelStepper.h>

#include "imu_manager.h"
#include "servo_manager.h"
#include "stepper_manager.h"
#include "balance_controller.h"
#include "communication.h"
#include "safety_manager.h"

static const unsigned long CONTROL_PERIOD_US = 5000UL; // 200 Hz target
static const unsigned long TELEMETRY_PERIOD_MS = 100UL;
// MUST remain false until IMU axis, motor signs, current limit, and safe test rig are verified.
static const bool PHYSICAL_BALANCE_OUTPUT_VALIDATED = false;
// Placeholder gains are intentionally zero; tune only with wheels lifted and rig supported.
static const float BALANCE_KP = 0.0f, BALANCE_KI = 0.0f, BALANCE_KD = 0.0f;
static const float BALANCE_MAX_STEP_RATE = 150.0f;

ImuManager imu;
ServoManager servos;
StepperManager steppers;
BalanceController balance;
SafetyManager safety;
Communication comm;

enum RobotState {
  STATE_INITIALIZING,
  STATE_IDLE,
  STATE_STAND_REQUESTED,
  STATE_STANDING_COMMAND_SENT,
  STATE_BALANCE_DISABLED,
  STATE_FAULT,
  STATE_ESTOP
};

RobotState robotState = STATE_INITIALIZING;
unsigned long lastControlUs = 0;
unsigned long lastTelemetryMs = 0;
bool hardwareReady = false;

const char* stateName(RobotState s) {
  switch (s) {
    case STATE_INITIALIZING: return "INITIALIZING";
    case STATE_IDLE: return "IDLE";
    case STATE_STAND_REQUESTED: return "STAND_REQUESTED";
    case STATE_STANDING_COMMAND_SENT: return "STANDING_COMMAND_SENT";
    case STATE_BALANCE_DISABLED: return "BALANCE_DISABLED";
    case STATE_FAULT: return "FAULT";
    case STATE_ESTOP: return "ESTOP";
    default: return "UNKNOWN";
  }
}

void onCommand(const String& cmd, const String& requestId) {
  if (cmd == "STATUS") {
    comm.sendStatus(requestId, stateName(robotState), safety.faultName());
  } else if (cmd == "STOP") {
    // Controlled software stop: prevent new commands. This is not a substitute
    // for a physical emergency-stop circuit.
    servos.stopCommanding();
    steppers.stop();
    balance.disable();
    robotState = STATE_IDLE;
    comm.sendAck(requestId, true, "STOP_ACCEPTED");
  } else if (cmd == "CALIBRATE") {
    if (!hardwareReady || safety.hasFault()) {
      comm.sendAck(requestId, false, "HARDWARE_NOT_READY");
    } else {
      bool ok = imu.calibrateStill();
      comm.sendAck(requestId, ok, ok ? "CALIBRATION_COMPLETE" : "CALIBRATION_FAILED");
    }
  } else if (cmd == "STAND") {
    if (!hardwareReady || safety.hasFault()) {
      comm.sendAck(requestId, false, "HARDWARE_NOT_READY");
      return;
    }
    robotState = STATE_STAND_REQUESTED;
    comm.sendAck(requestId, true, "STAND_REQUEST_ACCEPTED");
    // Standing targets must be calibrated per joint before physical use.
    // Default targets are disabled until a mapping has been configured.
    if (servos.standingPoseConfigured()) {
      servos.requestStandingPose();
      robotState = STATE_STANDING_COMMAND_SENT;
      comm.sendStatus(requestId, stateName(robotState), "POSE_COMMAND_SENT_NOT_PHYSICALLY_VERIFIED");
    } else {
      robotState = STATE_IDLE;
      comm.sendStatus(requestId, stateName(robotState), "STANDING_POSE_NOT_CONFIGURED");
    }
  } else if (cmd == "BALANCE") {
    // Keep physical balance output disabled until the actual rig has been validated.
    if (!PHYSICAL_BALANCE_OUTPUT_VALIDATED || !hardwareReady || safety.hasFault() ||
        !imu.latest().valid) {
      balance.disable();
      steppers.clearBalanceSpeeds();
      robotState = STATE_BALANCE_DISABLED;
      comm.sendAck(requestId, false, "BALANCE_OUTPUT_NOT_VALIDATED");
      return;
    }
    if (balance.armForValidatedRig()) {
      comm.sendAck(requestId, true, "BALANCE_ARMED_TEST_RIG_ONLY");
    } else {
      comm.sendAck(requestId, false, "BALANCE_CONTROLLER_NOT_CONFIGURED");
    }
  } else {
    comm.sendAck(requestId, false, "UNKNOWN_COMMAND");
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin(); // Mega 2560 SDA=20, SCL=21
  Wire.setClock(400000);

  comm.begin(Serial);
  safety.begin();
  servos.begin();
  steppers.begin();
  steppers.configureLimits(BALANCE_MAX_STEP_RATE, 100.0f, 200);
  balance.configure(BALANCE_KP, BALANCE_KI, BALANCE_KD, BALANCE_MAX_STEP_RATE);
  imu.begin();

  const bool imuOk = imu.isConnected();
  const bool servoOk = servos.isConnected();
  const bool stepperInterfaceOk = steppers.beginStatus();

  hardwareReady = imuOk && servoOk && stepperInterfaceOk;
  if (!imuOk) safety.raiseFault(FAULT_IMU);
  if (!servoOk) safety.raiseFault(FAULT_PCA9685);
  if (!stepperInterfaceOk) safety.raiseFault(FAULT_STEPPER_CONFIG);

  robotState = safety.hasFault() ? STATE_FAULT : STATE_IDLE;
  lastControlUs = micros();
  comm.sendBootStatus(hardwareReady, stateName(robotState));
}

void loop() {
  comm.poll(onCommand);
  safety.checkEstop();
  const unsigned long nowUs = micros();

  if ((unsigned long)(nowUs - lastControlUs) >= CONTROL_PERIOD_US) {
    const float dt = (nowUs - lastControlUs) / 1000000.0f;
    lastControlUs = nowUs;

    ImuReading reading;
    if (imu.read(reading)) {
      safety.updateImu(reading, millis());
      const float wheelCorrection = balance.update(reading, dt);
      if (balance.isEnabled() && PHYSICAL_BALANCE_OUTPUT_VALIDATED && !safety.hasFault()) {
        // Opposite signs are a PLACEHOLDER mapping; verify each wheel's physical direction first.
        steppers.setBalanceSpeeds(wheelCorrection, -wheelCorrection);
      } else {
        steppers.clearBalanceSpeeds();
      }
    } else {
      safety.raiseFault(FAULT_IMU_READ);
    }

    servos.update();
    steppers.update();
    safety.updateCommunication(comm.lastCommandMillis(), millis());

    if (safety.hasFault()) {
      balance.disable();
      steppers.clearBalanceSpeeds();
      steppers.disableDrivers();
      robotState = STATE_FAULT;
    }
  }

  if (millis() - lastTelemetryMs >= TELEMETRY_PERIOD_MS) {
    lastTelemetryMs = millis();
    ImuReading r = imu.latest();
    comm.sendTelemetry(stateName(robotState), r.pitchDeg, r.gyroPitchDps,
                       safety.faultName(), balance.lastOutput());
  }
}
