#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
Adafruit_PWMServoDriver pwm(0x40);
const uint8_t TEST_CHANNEL = 0;
// Deliberately small pulse range. Verify the servo and linkage are supported.
// Do not power MG996R servos from the Mega 5V pin.
void setup() {
  Serial.begin(115200);
  Wire.begin();
  pwm.begin();
  pwm.setPWMFreq(50);
  Serial.println("Servo test ready. Send 'L' or 'R' to change one test channel.");
  Serial.println("Check separate servo supply and mechanical clearance first.");
}
void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'L') pwm.writeMicroseconds(TEST_CHANNEL, 1475);
    if (c == 'R') pwm.writeMicroseconds(TEST_CHANNEL, 1525);
    if (c == 'C') pwm.writeMicroseconds(TEST_CHANNEL, 1500);
  }
}
