#include <AccelStepper.h>
// Verify pins and driver polarity against your exact driver wiring.
const uint8_t STEP_PIN = 2, DIR_PIN = 3, ENABLE_PIN = 6;
AccelStepper motor(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);
bool authorized = false;
void setup() {
  Serial.begin(115200);
  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, HIGH); // commonly disabled for active-low ENABLE
  motor.setMaxSpeed(50);
  motor.setAcceleration(25);
  Serial.println("Stepper test: support mechanism; send ARM then F or B for 20 steps.");
}
void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'A') {
      authorized = true;
      digitalWrite(ENABLE_PIN, LOW);
      Serial.println("ARMED");
    } else if (c == 'F' && authorized) {
      motor.move(20);
    } else if (c == 'B' && authorized) {
      motor.move(-20);
    } else if (c == 'S') {
      authorized = false;
      motor.stop();
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("STOPPED");
    }
  }
  motor.run();
}
