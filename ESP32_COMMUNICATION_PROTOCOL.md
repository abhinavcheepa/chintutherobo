# 📡 ESP32 ↔ Raspberry Pi Serial Communication Protocol
### (यह डॉक्यूमेंट अपने ESP32 डेवलपर / टीममेट को भेजें)

**CHINTU Robot Platform**
- **Raspberry Pi Role**: Host Server, Web Dashboard & High-level Commander
- **ESP32 Role**: Real-time Motor Driver, Servo Joint Actuation & IMU Reader
- **Physical Link**: USB Cable (`/dev/ttyUSB0` or `/dev/ttyACM0`) OR Hardware UART
- **Baud Rate**: `115200`
- **Data Format**: Newline-delimited JSON (`\n` at the end of each JSON string)

---

## 1. 📤 Raspberry Pi → ESP32 (जब यूजर इंटरफेस पर बटन दबाता है)

Raspberry Pi सीरियल पोर्ट पर हर कमांड को एक JSON लाइन के रूप में भेजता है:

### A. Movement / D-Pad Buttons (पहिए चलाना)
जब यूजर UP, DOWN, LEFT, RIGHT या STOP दबाता है:
```json
{"type": "move", "direction": "forward", "speed": 60}
```
* **`direction`**: `"forward"` | `"backward"` | `"left"` | `"right"` | `"stop"`
* **`speed`**: `0` से `100` (प्रतिशत)

### B. Speed Slider (स्पीड बदलना)
```json
{"type": "speed", "value": 75}
```
* **`value`**: `0` से `100`

### C. Joint Servos / Sliders (पैर के जोड़ों को मोड़ना)
जब यूजर L-Hip, R-Hip, L-Knee, या R-Knee स्लाइडर हिलाता है:
```json
{"type": "joint", "joint": "LHip", "angle": 25.0}
```
* **`joint`**: `"LHip"` | `"RHip"` | `"LKnee"` | `"RKnee"`
* **`angle`**:
  - Hips: `-90.0` से `+90.0` डिग्री
  - Knees: `-120.0` से `0.0` डिग्री

### D. Robot Stances / Poses (खड़े होना, बैठना, टिल्ट)
जब यूजर पोज बटन दबाता है:
```json
{"type": "stance", "stance": "crouch"}
```
* **`stance`**:
  - `"stand"`: सारे सर्वो 0° (सीधा खड़ा होना)
  - `"crouch"`: Hips = 30°, Knees = -60° (बैठना)
  - `"tilt_fwd"`: Hips = -20°
  - `"tilt_back"`: Hips = 20°
  - `"estop"`: सभी मोटरों को तुरंत रोकना

### E. Inverted Pendulum Balance Mode (बैलेंस ऑन/ऑफ)
```json
{"type": "control", "mode": "balance"}
```
* **`mode`**: `"balance"` (IMU बैलेंस चालू) | `"manual"` (मैनुअल मोड)

### F. PID Tuning Parameters
```json
{"type": "pid", "kp": 12.5, "ki": 0.6, "kd": 2.2}
```

### G. Handshake / Ping
```json
{"type": "handshake", "source": "raspberrypi-server"}
```
* ESP32 का जवाब होना चाहिए:
  `{"type":"pong","board":"ESP32","status":"online"}`

---

## 2. 📥 ESP32 → Raspberry Pi (लाइव सेंसर डेटा भेजना)

ESP32 को हर **50ms (20Hz)** में नीचे दिए फॉर्मेट में सीरियल पर एक JSON लाइन प्रिंट करनी है (`Serial.println`):

```json
{"pitch": 1.25, "pitchRate": -0.04, "leftHip": 0.0, "rightHip": 0.0, "leftKnee": 0.0, "rightKnee": 0.0, "leftWheelRPM": 45.2, "rightWheelRPM": 45.0, "power": 84.0, "temp": 31.5, "isHardware": true}
```

### फील्ड्स का विवरण:
| Field | Type | Description |
|---|---|---|
| `pitch` | float | IMU (MPU6050) से रोबोट का झुकाव (डिग्री में, 0 = सीधा) |
| `pitchRate` | float | जाइरोस्कोप से पिच वेलोसिटी (deg/s) |
| `leftHip` | float | बायां हिप वर्तमान एंगल |
| `rightHip` | float | दायां हिप वर्तमान एंगल |
| `leftKnee` | float | बायां घुटना वर्तमान एंगल |
| `rightKnee` | float | दायां घुटना वर्तमान एंगल |
| `leftWheelRPM` | float | बाएं पहिए की स्पीड (RPM) |
| `rightWheelRPM`| float | दाएं पहिए की स्पीड (RPM) |
| `power` | float | बैटरी वोल्टेज / प्रतिशत (उदा. 84.0) |
| `temp` | float | तापमान (°C) |
| `isHardware` | bool | हमेशा `true` रखें (ताकि Pi को पता चले रियल डेटा है) |

---

## 3. 📝 ESP32 डेवलपर के लिए रेडीमेड C++ कोड स्निपेट (Arduino)

आपका टीममेट इसे सीधे अपने कोड में शामिल कर सकता है:

```cpp
#include <ArduinoJson.h>

void setup() {
    Serial.begin(115200);
}

void processIncomingCommand(const char* jsonLine) {
    StaticJsonDocument<384> doc;
    DeserializationError error = deserializeJson(doc, jsonLine);
    if (error) return;

    const char* type = doc["type"] | "";

    if (strcmp(type, "move") == 0) {
        const char* dir = doc["direction"] | "stop";
        int speed = doc["speed"] | 50;
        // पहिए चलाएं: dir ("forward", "backward", "left", "right", "stop")
    }
    else if (strcmp(type, "speed") == 0) {
        int speed = doc["value"] | 50;
        // स्पीड अपडेट करें
    }
    else if (strcmp(type, "joint") == 0) {
        const char* joint = doc["joint"] | "";
        float angle = doc["angle"] | 0.0;
        // सर्वो मोटर सेट करें
    }
    else if (strcmp(type, "stance") == 0) {
        const char* stance = doc["stance"] | "stand";
        // पोज़ लगाएं
    }
    else if (strcmp(type, "control") == 0) {
        const char* mode = doc["mode"] | "manual";
        bool balanceOn = (strcmp(mode, "balance") == 0);
    }
}

String readBuf = "";
unsigned long lastTelemetry = 0;

void loop() {
    // 1. Pi से आने वाले JSON कमांड्स पढ़ें
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n') {
            readBuf.trim();
            if (readBuf.length() > 0) processIncomingCommand(readBuf.c_str());
            readBuf = "";
        } else if (c != '\r') {
            readBuf += c;
        }
    }

    // 2. हर 50ms में Pi को लाइव टेलीमेट्री भेजें
    if (millis() - lastTelemetry >= 50) {
        lastTelemetry = millis();
        StaticJsonDocument<300> doc;
        doc["pitch"] = 0.0; // MPU6050 वैल्यू
        doc["pitchRate"] = 0.0;
        doc["leftWheelRPM"] = 0.0;
        doc["rightWheelRPM"] = 0.0;
        doc["power"] = 84.0;
        doc["temp"] = 31.0;
        doc["isHardware"] = true;

        serializeJson(doc, Serial);
        Serial.println();
    }
}
```

---

## 4. 🔌 वायरिंग (Wiring)
* **USB केबल (Best)**: ESP32 को सीधे Raspberry Pi के USB पोर्ट में लगाएं।
* **UART**: Pi Pin 8 (TX) → ESP32 RX2, Pi Pin 10 (RX) → ESP32 TX2, और दोनों का **GND कॉमन** रखें।
