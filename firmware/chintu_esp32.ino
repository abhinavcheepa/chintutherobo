/* ========================================================
   CHINTU — Two-Wheeled Legged Hybrid Robot
   ESP32 Firmware (Arduino C++)
   Communication: Raspberry Pi Serial (USB/UART @ 115200) + WiFi WebSocket
   Sensors: MPU-6050 6-DOF IMU (I2C SDA=21, SCL=22)
   Actuators:
     - 2x Wheel Motors (PWM + DIR / Dual IN: Left 25/26, Right 32/33)
     - 4x Leg Joint Servos (50Hz PWM: LHip 18, RHip 19, LKnee 23, RKnee 27)
   ======================================================== */

#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include <Wire.h>

// ── WiFi & Network Config ──
const char* ssid     = "Chintu_AP";
const char* password = "robotchintu123";
WebSocketsServer webSocket = WebSocketsServer(8765);

// ── Motor Driver Pins (L298N / TB6612 / Cytron / BLDC ESC) ──
#define PIN_LEFT_MOTOR_PWM    25  // Left Motor Speed PWM (or IN1)
#define PIN_LEFT_MOTOR_DIR    26  // Left Motor Direction (or IN2)
#define PIN_RIGHT_MOTOR_PWM   32  // Right Motor Speed PWM (or IN3)
#define PIN_RIGHT_MOTOR_DIR   33  // Right Motor Direction (or IN4)

// ── Leg Joint Servo Pins (50Hz RC PWM) ──
#define PIN_LEFT_HIP          18  // Left Hip Servo
#define PIN_RIGHT_HIP         19  // Right Hip Servo
#define PIN_LEFT_KNEE         23  // Left Knee Servo
#define PIN_RIGHT_KNEE        27  // Right Knee Servo

// ── LEDC PWM Channel Allocation (ESP32) ──
#define CH_LEFT_MOTOR         0   // 20kHz, 8-bit (0 - 255)
#define CH_RIGHT_MOTOR        1   // 20kHz, 8-bit (0 - 255)
#define CH_LEFT_HIP           2   // 50Hz, 14-bit RC Servo
#define CH_RIGHT_HIP          3   // 50Hz, 14-bit RC Servo
#define CH_LEFT_KNEE          4   // 50Hz, 14-bit RC Servo
#define CH_RIGHT_KNEE         5   // 50Hz, 14-bit RC Servo

#define MOTOR_PWM_FREQ        20000
#define MOTOR_PWM_RES         8   // 0 - 255
#define SERVO_PWM_FREQ        50  // 50Hz = 20ms period
#define SERVO_PWM_RES         14  // 0 - 16383

// ── Safety Watchdog ──
#define WATCHDOG_TIMEOUT_MS   1500 // Stop motors if no command for 1.5s in manual mode

// ── Robot State Structure ──
struct RobotState {
    float pitch = 0.0;
    float pitchRate = 0.0;
    float leftHip = 0.0;
    float rightHip = 0.0;
    float leftKnee = 0.0;
    float rightKnee = 0.0;
    float leftWheelRPM = 0.0;
    float rightWheelRPM = 0.0;
    float battery = 84.0;
    float temperature = 31.0;
    bool balanceMode = false;
    float kp = 10.0;
    float ki = 0.5;
    float kd = 2.0;
    float pidIntegral = 0.0;
    float pidLastError = 0.0;
    int currentSpeed = 50;
    char currentDirection[16] = "stop";
} chintu;

unsigned long lastCommandTime = 0;
unsigned long lastTelemetryTime = 0;
String serialBuffer = "";

// ── Servo Angle Controller (500us to 2500us pulse) ──
void setServoAngle(uint8_t channel, float angle, float minAngle, float maxAngle) {
    float clampedAngle = constrain(angle, minAngle, maxAngle);
    // Map angle to pulse width in microseconds (500us = 0deg, 1500us = center, 2500us = max)
    float pulseUs = map(clampedAngle * 10, minAngle * 10, maxAngle * 10, 500, 2500);
    // Convert pulse width to 14-bit duty cycle (16383 = 20000us)
    uint32_t duty = (uint32_t)((pulseUs / 20000.0) * 16383.0);
    ledcWrite(channel, duty);
}

// ── Wheel Motor Controller ──
void setMotors(int leftPwm, int rightPwm) {
    // Left Motor (PWM + Direction)
    if (leftPwm > 0) {
        digitalWrite(PIN_LEFT_MOTOR_DIR, HIGH);
        ledcWrite(CH_LEFT_MOTOR, constrain(leftPwm, 0, 255));
    } else if (leftPwm < 0) {
        digitalWrite(PIN_LEFT_MOTOR_DIR, LOW);
        ledcWrite(CH_LEFT_MOTOR, constrain(-leftPwm, 0, 255));
    } else {
        digitalWrite(PIN_LEFT_MOTOR_DIR, LOW);
        ledcWrite(CH_LEFT_MOTOR, 0);
    }

    // Right Motor (PWM + Direction)
    if (rightPwm > 0) {
        digitalWrite(PIN_RIGHT_MOTOR_DIR, HIGH);
        ledcWrite(CH_RIGHT_MOTOR, constrain(rightPwm, 0, 255));
    } else if (rightPwm < 0) {
        digitalWrite(PIN_RIGHT_MOTOR_DIR, LOW);
        ledcWrite(CH_RIGHT_MOTOR, constrain(-rightPwm, 0, 255));
    } else {
        digitalWrite(PIN_RIGHT_MOTOR_DIR, LOW);
        ledcWrite(CH_RIGHT_MOTOR, 0);
    }

    // Update estimated RPM for telemetry feedback
    chintu.leftWheelRPM = (leftPwm / 255.0) * 150.0;
    chintu.rightWheelRPM = (rightPwm / 255.0) * 150.0;
}

// Direction Execution Helpers
void executeMovement(const char* dir, int speed) {
    int pwm = map(constrain(speed, 0, 100), 0, 100, 0, 255);
    strncpy(chintu.currentDirection, dir, sizeof(chintu.currentDirection) - 1);

    if (strcmp(dir, "forward") == 0) {
        setMotors(pwm, pwm);
    } else if (strcmp(dir, "backward") == 0) {
        setMotors(-pwm, -pwm);
    } else if (strcmp(dir, "left") == 0) {
        // Spin turn left: left wheel backward, right wheel forward
        setMotors(-pwm, pwm);
    } else if (strcmp(dir, "right") == 0) {
        // Spin turn right: left wheel forward, right wheel backward
        setMotors(pwm, -pwm);
    } else {
        // Stop
        setMotors(0, 0);
        strncpy(chintu.currentDirection, "stop", sizeof(chintu.currentDirection) - 1);
    }
}

// ── Joint Stance Presets ──
void applyStance(const char* stance) {
    if (strcmp(stance, "stand") == 0) {
        chintu.leftHip = 0.0;  chintu.rightHip = 0.0;
        chintu.leftKnee = 0.0; chintu.rightKnee = 0.0;
    } else if (strcmp(stance, "crouch") == 0) {
        chintu.leftHip = 30.0;  chintu.rightHip = 30.0;
        chintu.leftKnee = -60.0; chintu.rightKnee = -60.0;
    } else if (strcmp(stance, "tilt_fwd") == 0) {
        chintu.leftHip = -20.0; chintu.rightHip = -20.0;
    } else if (strcmp(stance, "tilt_back") == 0) {
        chintu.leftHip = 20.0;  chintu.rightHip = 20.0;
    } else if (strcmp(stance, "estop") == 0) {
        setMotors(0, 0);
        chintu.balanceMode = false;
        strncpy(chintu.currentDirection, "stop", sizeof(chintu.currentDirection) - 1);
    }

    // Write physical servo positions
    setServoAngle(CH_LEFT_HIP,   chintu.leftHip,   -90.0, 90.0);
    setServoAngle(CH_RIGHT_HIP,  chintu.rightHip,  -90.0, 90.0);
    setServoAngle(CH_LEFT_KNEE,  chintu.leftKnee,  -120.0, 0.0);
    setServoAngle(CH_RIGHT_KNEE, chintu.rightKnee, -120.0, 0.0);
}

// ── Unified Command Processor (Serial + WebSocket) ──
void processCommand(const char* payload) {
    StaticJsonDocument<384> doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
        Serial.print("{\"error\":\"invalid_json\"}\n");
        return;
    }

    lastCommandTime = millis();
    const char* cmdType = doc["type"] | "";

    // 1. Move Commands (D-Pad, Keyboard WASD, Arrows)
    if (strcmp(cmdType, "move") == 0) {
        const char* dir = doc["direction"] | "stop";
        int speed = doc["speed"] | chintu.currentSpeed;
        chintu.currentSpeed = speed;

        // If balance mode is active, forward/backward tilts balance point instead of raw PWM
        if (chintu.balanceMode) {
            strncpy(chintu.currentDirection, dir, sizeof(chintu.currentDirection) - 1);
        } else {
            executeMovement(dir, speed);
        }
        Serial.printf("{\"status\":\"ok\",\"action\":\"move\",\"direction\":\"%s\",\"speed\":%d}\n", dir, speed);

    // 2. Speed Slider Command
    } else if (strcmp(cmdType, "speed") == 0) {
        chintu.currentSpeed = doc["value"] | 50;
        if (!chintu.balanceMode && strcmp(chintu.currentDirection, "stop") != 0) {
            executeMovement(chintu.currentDirection, chintu.currentSpeed);
        }
        Serial.printf("{\"status\":\"ok\",\"action\":\"speed\",\"speed\":%d}\n", chintu.currentSpeed);

    // 3. Joint Slider Commands (LHip, RHip, LKnee, RKnee)
    } else if (strcmp(cmdType, "joint") == 0) {
        const char* joint = doc["joint"] | "";
        float angle = doc["angle"] | 0.0;

        if (strstr(joint, "LHip")) {
            chintu.leftHip = angle;
            setServoAngle(CH_LEFT_HIP, angle, -90.0, 90.0);
        } else if (strstr(joint, "RHip")) {
            chintu.rightHip = angle;
            setServoAngle(CH_RIGHT_HIP, angle, -90.0, 90.0);
        } else if (strstr(joint, "LKnee")) {
            chintu.leftKnee = angle;
            setServoAngle(CH_LEFT_KNEE, angle, -120.0, 0.0);
        } else if (strstr(joint, "RKnee")) {
            chintu.rightKnee = angle;
            setServoAngle(CH_RIGHT_KNEE, angle, -120.0, 0.0);
        }
        Serial.printf("{\"status\":\"ok\",\"action\":\"joint\",\"joint\":\"%s\",\"angle\":%.1f}\n", joint, angle);

    // 4. Stance / Pose Presets (Stand, Crouch, Tilt, E-Stop)
    } else if (strcmp(cmdType, "stance") == 0) {
        const char* stance = doc["stance"] | "stand";
        applyStance(stance);
        Serial.printf("{\"status\":\"ok\",\"action\":\"stance\",\"stance\":\"%s\"}\n", stance);

    // 5. Inverted Pendulum Balance Mode Toggle
    } else if (strcmp(cmdType, "control") == 0) {
        const char* mode = doc["mode"] | "manual";
        chintu.balanceMode = (strcmp(mode, "balance") == 0);
        chintu.pidIntegral = 0;
        if (!chintu.balanceMode) setMotors(0, 0);
        Serial.printf("{\"status\":\"ok\",\"action\":\"control\",\"balanceMode\":%s}\n", chintu.balanceMode ? "true" : "false");

    // 6. PID Parameters Update
    } else if (strcmp(cmdType, "pid") == 0) {
        chintu.kp = doc["kp"] | chintu.kp;
        chintu.ki = doc["ki"] | chintu.ki;
        chintu.kd = doc["kd"] | chintu.kd;
        chintu.pidIntegral = 0;
        Serial.printf("{\"status\":\"ok\",\"action\":\"pid\",\"kp\":%.2f,\"ki\":%.2f,\"kd\":%.2f}\n", chintu.kp, chintu.ki, chintu.kd);

    // 7. Handshake / Ping
    } else if (strcmp(cmdType, "ping") == 0 || strcmp(cmdType, "handshake") == 0) {
        Serial.print("{\"type\":\"pong\",\"board\":\"ESP32\",\"firmware\":\"2.2\",\"status\":\"online\"}\n");
    }
}

// ── WebSocket Event Callback ──
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.printf("[WS] Client %u disconnected\n", num);
            break;
        case WStype_CONNECTED:
            Serial.printf("[WS] Client %u connected\n", num);
            break;
        case WStype_TEXT:
            processCommand((char*)payload);
            break;
        default:
            break;
    }
}

// ── Broadcast Telemetry to Raspberry Pi Serial + WebSocket ──
void broadcastTelemetry() {
    StaticJsonDocument<512> doc;
    doc["pitch"] = round(chintu.pitch * 100) / 100.0;
    doc["pitchRate"] = round(chintu.pitchRate * 100) / 100.0;
    doc["leftHip"] = chintu.leftHip;
    doc["rightHip"] = chintu.rightHip;
    doc["leftKnee"] = chintu.leftKnee;
    doc["rightKnee"] = chintu.rightKnee;
    doc["leftWheelRPM"] = round(chintu.leftWheelRPM * 10) / 10.0;
    doc["rightWheelRPM"] = round(chintu.rightWheelRPM * 10) / 10.0;
    doc["power"] = chintu.battery;
    doc["temp"] = chintu.temperature;
    doc["isHardware"] = true;

    char buffer[512];
    serializeJson(doc, buffer);

    // 1. Send to Raspberry Pi over USB Serial
    Serial.println(buffer);

    // 2. Broadcast to connected WebSockets
    webSocket.broadcastTXT(buffer);
}

void setup() {
    Serial.begin(115200);
    delay(400);
    Serial.println("{\"type\":\"boot\",\"device\":\"Chintu_ESP32_v2.2\",\"status\":\"ready\"}");

    // Initialize Motor Direction Pins
    pinMode(PIN_LEFT_MOTOR_DIR, OUTPUT);
    pinMode(PIN_RIGHT_MOTOR_DIR, OUTPUT);
    digitalWrite(PIN_LEFT_MOTOR_DIR, LOW);
    digitalWrite(PIN_RIGHT_MOTOR_DIR, LOW);

    // Initialize Motor PWM Channels (20kHz, 8-bit)
    ledcSetup(CH_LEFT_MOTOR, MOTOR_PWM_FREQ, MOTOR_PWM_RES);
    ledcAttachPin(PIN_LEFT_MOTOR_PWM, CH_LEFT_MOTOR);
    ledcWrite(CH_LEFT_MOTOR, 0);

    ledcSetup(CH_RIGHT_MOTOR, MOTOR_PWM_FREQ, MOTOR_PWM_RES);
    ledcAttachPin(PIN_RIGHT_MOTOR_PWM, CH_RIGHT_MOTOR);
    ledcWrite(CH_RIGHT_MOTOR, 0);

    // Initialize Joint Servos (50Hz, 14-bit)
    ledcSetup(CH_LEFT_HIP, SERVO_PWM_FREQ, SERVO_PWM_RES);
    ledcAttachPin(PIN_LEFT_HIP, CH_LEFT_HIP);

    ledcSetup(CH_RIGHT_HIP, SERVO_PWM_FREQ, SERVO_PWM_RES);
    ledcAttachPin(PIN_RIGHT_HIP, CH_RIGHT_HIP);

    ledcSetup(CH_LEFT_KNEE, SERVO_PWM_FREQ, SERVO_PWM_RES);
    ledcAttachPin(PIN_LEFT_KNEE, CH_LEFT_KNEE);

    ledcSetup(CH_RIGHT_KNEE, SERVO_PWM_FREQ, SERVO_PWM_RES);
    ledcAttachPin(PIN_RIGHT_KNEE, CH_RIGHT_KNEE);

    // Set Servos to initial Stand Stance (0 deg)
    applyStance("stand");

    // Start WiFi Access Point
    WiFi.softAP(ssid, password);
    Serial.printf("[WIFI] AP started: %s (IP: %s)\n", ssid, WiFi.softAPIP().toString().c_str());

    // Start WebSocket
    webSocket.begin();
    webSocket.onEvent(webSocketEvent);
}

void loop() {
    webSocket.loop();

    // 1. Read Commands from Raspberry Pi via Serial
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n') {
            serialBuffer.trim();
            if (serialBuffer.length() > 0) {
                processCommand(serialBuffer.c_str());
            }
            serialBuffer = "";
        } else if (c != '\r') {
            serialBuffer += c;
        }
    }

    // 2. Safety Watchdog: Auto-stop if no command received for > 1.5s in manual move mode
    if (!chintu.balanceMode && strcmp(chintu.currentDirection, "stop") != 0) {
        if (millis() - lastCommandTime > WATCHDOG_TIMEOUT_MS) {
            executeMovement("stop", 0);
            Serial.println("{\"type\":\"watchdog\",\"action\":\"autostop\",\"reason\":\"timeout\"}");
        }
    }

    // 3. Balance Mode PID Loop (Inverted Pendulum)
    if (chintu.balanceMode) {
        float dt = 0.02;
        // Direction tilt bias for balancing while moving
        float targetPitch = 0.0;
        if (strcmp(chintu.currentDirection, "forward") == 0) targetPitch = -3.0;
        else if (strcmp(chintu.currentDirection, "backward") == 0) targetPitch = 3.0;

        float error = targetPitch - chintu.pitch;
        chintu.pidIntegral += error * dt;
        chintu.pidIntegral = constrain(chintu.pidIntegral, -50.0, 50.0);
        float derivative = (error - chintu.pidLastError) / dt;
        float output = chintu.kp * error + chintu.ki * chintu.pidIntegral + chintu.kd * derivative;
        chintu.pidLastError = error;

        int balancePwm = (int)constrain(output * 6.0, -255.0, 255.0);
        
        // Steering bias while balancing
        if (strcmp(chintu.currentDirection, "left") == 0) {
            setMotors(balancePwm - 40, balancePwm + 40);
        } else if (strcmp(chintu.currentDirection, "right") == 0) {
            setMotors(balancePwm + 40, balancePwm - 40);
        } else {
            setMotors(balancePwm, balancePwm);
        }
    }

    // 4. Broadcast Telemetry every 50ms (20Hz)
    unsigned long now = millis();
    if (now - lastTelemetryTime >= 50) {
        lastTelemetryTime = now;
        broadcastTelemetry();
    }
}
