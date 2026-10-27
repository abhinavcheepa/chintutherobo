#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
Adafruit_MPU6050 mpu;
void setup() {
  Serial.begin(115200);
  Wire.begin();
  if (!mpu.begin()) {
    Serial.println("ERROR: MPU6050 not found");
    while (true) delay(100);
  }
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("MPU6050 test started; no actuators are moved.");
}
void loop() {
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  float pitch = atan2(a.acceleration.x,
      sqrt(a.acceleration.y*a.acceleration.y + a.acceleration.z*a.acceleration.z)) * RAD_TO_DEG;
  Serial.print("accel_mps2,");
  Serial.print(a.acceleration.x); Serial.print(",");
  Serial.print(a.acceleration.y); Serial.print(",");
  Serial.print(a.acceleration.z); Serial.print(",gyro_rads,");
  Serial.print(g.gyro.x); Serial.print(",");
  Serial.print(g.gyro.y); Serial.print(",");
  Serial.print(g.gyro.z); Serial.print(",pitch_deg,");
  Serial.println(pitch);
  delay(50);
}
