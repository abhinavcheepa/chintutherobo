#ifndef IMU_H
#define IMU_H

#include <Arduino.h>
#include <Wire.h>

class Mpu6050Driver {
public:
    Mpu6050Driver();
    bool init();
    bool calibrate_gyro(uint16_t sample_count = 500);
    bool read_sensor();

    // Accelerations in Gs
    float get_accel_x() const { return accel_x_; }
    float get_accel_y() const { return accel_y_; }
    float get_accel_z() const { return accel_z_; }

    // Angular velocities in deg/s
    float get_gyro_x() const { return gyro_x_; }
    float get_gyro_y() const { return gyro_y_; }
    float get_gyro_z() const { return gyro_z_; }

    bool is_healthy() const { return is_initialized_; }

private:
    static const uint8_t MPU_ADDR = 0x68;

    bool is_initialized_;
    float accel_x_;
    float accel_y_;
    float accel_z_;
    float gyro_x_;
    float gyro_y_;
    float gyro_z_;

    float gyro_bias_x_;
    float gyro_bias_y_;
    float gyro_bias_z_;

    void write_register(uint8_t reg, uint8_t data);
};

extern Mpu6050Driver IMU;

#endif // IMU_H
