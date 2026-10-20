# 🍓 Chintu Robot — Raspberry Pi Connection & Setup Guide
## (रास्पबेरी पाई से कनेक्ट और सेटअप करने की पूरी गाइड)

यह गाइड आपको **Chintu (Two-Wheeled Legged Robot)** को **Raspberry Pi** के साथ पूरी तरह कनेक्ट और रन करने का पूरा तरीका बताती है।

---

## 🏗️ 2 तरीके जिससे आप Raspberry Pi को इस्तेमाल कर सकते हैं:

### 🌟 विकल्प A: Raspberry Pi + ESP32 (Recommended / सबसे आसान)
- **ESP32**: हाई-स्पीड मोटर ड्राइव, सर्वो कंट्रोल और IMU को रियल-टाइम हैंडल करता है।
- **Raspberry Pi**: रोबोट का ऑनबोर्ड दिमाग (Host Server) बनता है।
- **Connection**: Raspberry Pi को ESP32 से साधारण **USB केबल** (या UART Pins) से जोड़ें।
- **Web Dashboard**: Raspberry Pi वाई-फाई पर डैशबोर्ड होस्ट करता है। आप अपने लैपटॉप, मोबाइल या टैबलेट पर ब्राउज़र में `http://raspberrypi.local:8973` खोलकर रोबोट चला सकते हैं!

```
[Laptop / Mobile Browser]
        ▲
        │ (WiFi / Hotspot WebSocket + HTTP)
        ▼
[Raspberry Pi 3/4/5/Zero 2W]  (Runs server.py)
        ▲
        │ (USB Cable /dev/ttyUSB0 @ 115200 baud)
        ▼
[ESP32 Microcontroller]  (Runs firmware/chintu_esp32.ino)
   ├── MPU-6050 Gyro/Accel (I2C)
   ├── Left & Right Wheel Motors (PWM + DIR)
   └── Hip & Knee Joint Servos
```

---

### 🌟 विकल्प B: Raspberry Pi Direct Control (बिना ESP32 के)
- MPU6050 सीधे Raspberry Pi के I2C पिन (SDA/SCL) से जुड़ता है।
- मोटर ड्राइवर (L298N/TB6612) सीधे Raspberry Pi के GPIO PWM पिन से जुड़ता है।
- `rpi_chintu.py` सीधे हार्डवेयर और PID बैलेंस लूप चलाता है।

---

## 🔌 कनेक्शन और वायरिंग (Wiring Diagram)

### 1. USB Connection (सबसे आसान):
1. ESP32 बोर्ड को Raspberry Pi के किसी भी USB पोर्ट में प्लग करें।
2. Raspberry Pi पर यह अपने आप `/dev/ttyUSB0` या `/dev/ttyACM0` बन जाएगा।

### 2. GPIO UART Serial Wiring (यदि USB नहीं लगाना):
| Raspberry Pi Pin | ESP32 Pin | विवरण |
|------------------|-----------|-------|
| Pin 6, 9, 14, 20 (GND) | GND | **कॉमन ग्राउंड (सबसे महत्वपूर्ण)** |
| Pin 8 (GPIO 14 - TXD)  | Pin 16 (RX2) | Pi TX → ESP32 RX |
| Pin 10 (GPIO 15 - RXD) | Pin 17 (TX2) | Pi RX ← ESP32 TX |

### 3. MPU-6050 I2C Wiring (Direct Pi connection के लिए):
| MPU-6050 Pin | Raspberry Pi Pin | विवरण |
|--------------|------------------|-------|
| VCC          | Pin 1 (3.3V)     | पावर |
| GND          | Pin 6 (GND)      | ग्राउंड |
| SDA          | Pin 3 (GPIO 2 SDA)| I2C डेटा |
| SCL          | Pin 5 (GPIO 3 SCL)| I2C क्लॉक |

---

## 🚀 Raspberry Pi पर सेटअप और रन कैसे करें:

### Step 1: फाइलें Raspberry Pi पर कॉपी करें
आप Git क्लोन कर सकते हैं या प्रोजेक्ट फोल्डर को Raspberry Pi में कॉपी करें:
```bash
git clone https://github.com/abhinavcheepa/chintutherobo.git
cd chintutherobo
```

### Step 2: ऑटोमेटेड सेटअप चलाएं
हमने एक ऑटोमेटेड सेटअप स्क्रिप्ट दी है जो सभी डिपेंडेंसी, I2C, और सीरियल परमिशन एक क्लिक में सेट कर देती है:
```bash
chmod +x setup_rpi.sh start_rpi.sh
sudo ./setup_rpi.sh
```

### Step 3: रीबूट करें (ग्रुप और I2C एक्टिवेट करने के लिए)
```bash
sudo reboot
```

### Step 4: सर्वर स्टार्ट करें
```bash
cd chintutherobo
./start_rpi.sh
```
*या सीधे चलाएं:*
```bash
python3 server.py --auto-serial
```

---

## 💻 लैपटॉप या मोबाइल से कनेक्ट कैसे करें:

1. सुनिश्चित करें कि आपका लैपटॉप/फोन और Raspberry Pi **एक ही Wi-Fi नेटवर्क या Hotspot** से कनेक्ट हैं।
2. लैपटॉप/मोबाइल के क्रोम ब्राउज़र में खोलें:
   ```text
   http://raspberrypi.local:8973
   ```
   *(या Raspberry Pi का IP address, जैसे `http://192.168.1.45:8973`)*
3. **Connection Panel** में:
   - **"Raspberry Pi"** बटन पर क्लिक करें।
   - Quick IP में **"Raspberry Pi"** चिप चुनें।
   - **"CONNECT"** बटन दबाएं।
4. **Robot Hardware Serial** बॉक्स में:
   - "🔄" (Scan) बटन दबाएं — यह अपने आप `/dev/ttyUSB0` या ESP32 पोर्ट खोज लेगा।
   - **"Link HW"** पर क्लिक करें।
   - टॉप बार में `HW: ACTIVE` (ग्रीन ग्लो) दिखाई देगा!

---

## 🤖 ऑटो-स्टार्ट ऑन बूट (Headless Mode):
रोबोट में स्क्रीन/कीबोर्ड लगाए बिना Raspberry Pi ऑन होते ही Chintu को चालू करने के लिए:
```bash
sudo systemctl enable chintu
sudo systemctl start chintu
```
अब जब भी Raspberry Pi में बैटरी पावर देंगे, Chintu अपने आप बैकग्राउंड में स्टार्ट हो जाएगा!

## 🎮 इंटरफेस बटन और मोटर मूवमेंट मैपिंग (Button to Motor Movement)

जब आप वेब डैशबोर्ड में कोई भी बटन दबाते हैं या स्लाइडर मूव करते हैं, तो मोटर नीचे दिए अनुसार हरकत करेगी:

| इंटरफ़ेस कंट्रोल | कीबोर्ड शॉर्टकट | हार्डवेयर पिन / चैनल | मोटर का मूवमेंट |
|---|---|---|---|
| **▲ UP (Forward)** | `W` या `Up Arrow` | Left Motor (25/26), Right Motor (32/33) | दोनों पहिए आगे की दिशा में घूमेंगे (`speed%` PWM पर) |
| **▼ DOWN (Backward)** | `S` या `Down Arrow` | Left Motor (25/26), Right Motor (32/33) | दोनों पहिए पीछे की दिशा में घूमेंगे (`speed%` PWM पर) |
| **◀ LEFT (Spin Turn)** | `A` या `Left Arrow` | Left Motor (25/26), Right Motor (32/33) | बायां पहिया पीछे, दायां पहिया आगे (रोबोट बाएं घूमेगा) |
| **▶ RIGHT (Spin Turn)** | `D` या `Right Arrow` | Left Motor (25/26), Right Motor (32/33) | बायां पहिया आगे, दायां पहिया पीछे (रोबोट दाएं घूमेगा) |
| **■ STOP** | `Spacebar` | Both Motor PWM Channels | दोनों पहियों की पावर 0% (तुरंत रुक जाएगा) |
| **SPEED SLIDER** | — | PWM Duty Cycle (0 - 255) | 0% से 100% के बीच मोटर की स्पीड रियल-टाइम बदलेगी |
| **L-HIP SLIDER** | — | Left Hip Servo (GPIO 18) | बायां हिप सर्वो -90° से +90° तक सेट एंगल पर मुड़ेगा |
| **R-HIP SLIDER** | — | Right Hip Servo (GPIO 19) | दायां हिप सर्वो -90° से +90° तक सेट एंगल पर मुड़ेगा |
| **L-KNEE SLIDER** | — | Left Knee Servo (GPIO 23) | बायां घुटना सर्वो 0° से -120° तक मुड़ेगा |
| **R-KNEE SLIDER** | — | Right Knee Servo (GPIO 27) | दायां घुटना सर्वो 0° से -120° तक मुड़ेगा |
| **🧍 STAND** | — | All 4 Servos | रोबोट सीधा खड़ा होगा (Hip=0°, Knee=0°) |
| **🧎 CROUCH** | — | All 4 Servos | रोबोट झुककर बैठेगा (Hip=30°, Knee=-60°) |
| **📐 TILT FWD** | — | Hip Servos | रोबोट आगे की तरफ झुकेगा (Hip=-20°) |
| **📐 TILT BACK** | — | Hip Servos | रोबोट पीछे की तरफ झुकेगा (Hip=20°) |
| **🛑 E-STOP** | — | All Motors & Servos | **इमरजेंसी स्टॉप**: सभी मोटरों की पावर कट और न्यूट्रल पोज़ |
| **⚖️ BALANCE** | — | Inverted Pendulum PID Loop | IMU MPU6050 से 2 पहियों पर खुद बैलेंस बनाए रखेगा |

---

## 🛠️ समस्या निवारण (Troubleshooting):

1. **सीरियल पोर्ट नहीं मिल रहा (`/dev/ttyUSB0` not found)**:
   - चेक करें केबल डेटा केबल है या सिर्फ चार्जिंग केबल।
   - `ls /dev/ttyUSB* /dev/ttyACM*` चलाकर पोर्ट का नाम देखें।
   - परमिशन ठीक करने के लिए: `sudo usermod -a -G dialout $USER`

2. **ब्राउज़र में `raspberrypi.local` नहीं खुल रहा**:
   - Raspberry Pi का IP पता निकालें: `hostname -I`
   - सीधे IP से खोलें, उदाहरण: `http://192.168.43.150:8973`

3. **ESP32 को फ्लैश करना**:
   - Arduino IDE में `firmware/chintu_esp32.ino` खोलें।
   - `WebSocketsServer` और `ArduinoJson` लाइब्रेरी इंस्टॉल करें।
   - ESP32 बोर्ड सेलेक्ट करके अपलोड करें।
