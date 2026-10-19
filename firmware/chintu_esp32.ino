/* ========================================================
   CHINTU — Two-Wheeled Legged Hybrid Robot
   ESP32 Firmware (Arduino C++)
   Communication: WiFi (WebSocket) & Bluetooth Serial
   Sensors: MPU6050 (IMU)
   Actuators: BLDC Wheel Motors + Hip/Knee Joint Servos
   ======================================================== */

#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include <Wire.h>

// ── WiFi & Network Config ──
const char* ssid     = "Chintu_AP";
const char* password = "robotchintu123";
WebSocketsServer webSocket = WebSocketsServer(8765);

// ── Pin Definitions ──
#define PIN_LEFT_HIP      18
#define PIN_RIGHT_HIP     19
#define PIN_LEFT_KNEE     21
#define PIN_RIGHT_KNEE    22
#define PIN_LEFT_MOTOR_PWM  25
#define PIN_LEFT_MOTOR_DIR  26
#define PIN_RIGHT_MOTOR_PWM 32
#define PIN_RIGHT_MOTOR_DIR 33

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
} chintu;

// ── WebSocket Event Callback ──
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.printf("[%u] Disconnected!\n", num);
            break;
        case WStype_CONNECTED:
            Serial.printf("[%u] Connected from url: %s\n", num, payload);
            break;
        case WStype_TEXT: {
            StaticJsonDocument<256> doc;
            DeserializationError error = deserializeJson(doc, payload);
            if (!error) {
                const char* cmdType = doc["type"];
                if (strcmp(cmdType, "move") == 0) {
                    const char* dir = doc["direction"];
                    int speed = doc["speed"] | 50;
                    Serial.printf("Move: %s at %d%%\n", dir, speed);
                } else if (strcmp(cmdType, "pid") == 0) {
                    chintu.kp = doc["kp"];
                    chintu.ki = doc["ki"];
                    chintu.kd = doc["kd"];
                    Serial.printf("PID updated: Kp=%.2f Ki=%.2f Kd=%.2f\n", chintu.kp, chintu.ki, chintu.kd);
                } else if (strcmp(cmdType, "control") == 0) {
                    const char* mode = doc["mode"];
                    chintu.balanceMode = (strcmp(mode, "balance") == 0);
                    Serial.printf("Balance Mode: %s\n", chintu.balanceMode ? "ON" : "OFF");
                }
            }
            break;
        }
        default:
            break;
    }
}

// ── Send Telemetry Telecast ──
void broadcastTelemetry() {
    StaticJsonDocument<512> doc;
    doc["pitch"] = chintu.pitch;
    doc["pitchRate"] = chintu.pitchRate;
    doc["leftHip"] = chintu.leftHip;
    doc["rightHip"] = chintu.rightHip;
    doc["leftKnee"] = chintu.leftKnee;
    doc["rightKnee"] = chintu.rightKnee;
    doc["leftWheelRPM"] = chintu.leftWheelRPM;
    doc["rightWheelRPM"] = chintu.rightWheelRPM;
    doc["power"] = chintu.battery;
    doc["temp"] = chintu.temperature;

    char buffer[512];
    serializeJson(doc, buffer);
    webSocket.broadcastTXT(buffer);
}

void setup() {
    Serial.begin(115200);

    // Setup AP or Connect to WiFi
    WiFi.softAP(ssid, password);
    Serial.println("Chintu WiFi AP Started");
    Serial.print("IP Address: ");
    Serial.println(WiFi.softAPIP());

    // Start WebSocket
    webSocket.begin();
    webSocket.onEvent(webSocketEvent);
    Serial.println("WebSocket Server listening on port 8765");
}

unsigned long lastTelemetryTime = 0;

void loop() {
    webSocket.loop();

    // Broadcast telemetry every 50ms (20Hz)
    unsigned long now = millis();
    if (now - lastTelemetryTime >= 50) {
        lastTelemetryTime = now;
        broadcastTelemetry();
    }
}
