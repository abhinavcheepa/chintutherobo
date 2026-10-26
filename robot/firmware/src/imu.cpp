#include "imu.h"
#include "config.h"

Mpu6050Driver IMU;

Mpu6050Driver::Mpu6050Driver()
    : is_initialized_(false),
      accel_x_(0.0f), accel_y_(0.0f), accel_z_(1.0f),
      gyro_x_(0.0f), gyro_y_(0.0f), gyro_z_(0.0f),
      gyro_bias_x_(0.0f), gyro_bias_y_(0.0f), gyro_bias_z_(0.0f) {}

void Mpu6050Driver::write_register(uint8_t reg, uint8_t data) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    Wire.write(data);
    Wire.endTransmission(true);
}

bool Mpu6050Driver::init() {
    Wire.begin();
    Wire.setClock(I2C_CLOCK_SPEED); // 400 kHz Fast Mode
    
    // Enable bus timeout: 3000 microseconds (3 ms), reset bus on timeout
    #if defined(WIRE_HAS_TIMEOUT)
    Wire.setWireTimeout(3000, true);
    #endif
    
    // Check connection by reading WHO_AM_I (reg 0x75, should be 0x68)
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x75);
    if (Wire.endTransmission(false) != 0) {
        is_initialized_ = false;
        return false;
    }
    Wire.requestFrom(MPU_ADDR, (uint8_t)1, (uint8_t)true);
    if (Wire.available() < 1 || Wire.read() != 0x68) {
        is_initialized_ = false;
        return false;
    }

    // Wake up from sleep (PWR_MGMT_1: register 0x6B = 0x01, clock source = PLL Gyro X)
    write_register(0x6B, 0x01);
    
    // Set Sample Rate Divider: 1 kHz / (1 + 4) = 200 Hz (SMPLRT_DIV: reg 0x19 = 0x04)
    write_register(0x19, 0x04);
    
    // Set Digital Low Pass Filter: DLPF_CFG = 3 (Acc: 44 Hz, Gyro: 42 Hz) (CONFIG: reg 0x1A = 0x03)
    write_register(0x1A, 0x03);
    
    // Set Gyroscope Full Scale Range: +/- 1000 deg/s (GYRO_CONFIG: reg 0x1B = 0x10)
    // Scale factor: 32.8 LSB / (deg/s)
    write_register(0x1B, 0x10);
    
    // Set Accelerometer Full Scale Range: +/- 4g (ACCEL_CONFIG: reg 0x1C = 0x08)
    // Scale factor: 8192 LSB / g
    write_register(0x1C, 0x08);

    is_initialized_ = true;
    return true;
}

static inline int16_t read_i16_be() {
    uint8_t msb = (uint8_t)Wire.read();
    uint8_t lsb = (uint8_t)Wire.read();
    return (int16_t)(((uint16_t)msb << 8) | (uint16_t)lsb);
}

bool Mpu6050Driver::calibrate_gyro(uint16_t sample_count) {
    if (!is_initialized_) return false;

    float sum_x = 0.0f;
    float sum_y = 0.0f;
    float sum_z = 0.0f;

    for (uint16_t i = 0; i < sample_count; i++) {
        Wire.beginTransmission(MPU_ADDR);
        Wire.write(0x43); // Start at GYRO_XOUT_H
        if (Wire.endTransmission(false) != 0) return false;
        
        Wire.requestFrom(MPU_ADDR, (uint8_t)6, (uint8_t)true);
        if (Wire.available() < 6) return false;

        int16_t raw_gx = read_i16_be();
        int16_t raw_gy = read_i16_be();
        int16_t raw_gz = read_i16_be();

        sum_x += ((float)raw_gx / 32.8f);
        sum_y += ((float)raw_gy / 32.8f);
        sum_z += ((float)raw_gz / 32.8f);

        delayMicroseconds(2000); // 2 ms delay per sample
    }

    gyro_bias_x_ = sum_x / (float)sample_count;
    gyro_bias_y_ = sum_y / (float)sample_count;
    gyro_bias_z_ = sum_z / (float)sample_count;

    return true;
}

bool Mpu6050Driver::read_sensor() {
    if (!is_initialized_) return false;

    Wire.beginTransmission(MPU_ADDR);
    Wire.write(0x3B); // Start at ACCEL_XOUT_H
    if (Wire.endTransmission(false) != 0) return false;

    // Burst read 14 bytes: 6 accel + 2 temp + 6 gyro
    Wire.requestFrom(MPU_ADDR, (uint8_t)14, (uint8_t)true);
    if (Wire.available() < 14) return false;

    int16_t raw_ax = read_i16_be();
    int16_t raw_ay = read_i16_be();
    int16_t raw_az = read_i16_be();
    
    // Skip 2 temp bytes
    Wire.read();
    Wire.read();

    int16_t raw_gx = read_i16_be();
    int16_t raw_gy = read_i16_be();
    int16_t raw_gz = read_i16_be();

    // Scale to engineering units (4g -> 8192 LSB/g, 1000 dps -> 32.8 LSB/dps)
    accel_x_ = (float)raw_ax / 8192.0f;
    accel_y_ = (float)raw_ay / 8192.0f;
    accel_z_ = (float)raw_az / 8192.0f;

    gyro_x_ = ((float)raw_gx / 32.8f) - gyro_bias_x_;
    gyro_y_ = ((float)raw_gy / 32.8f) - gyro_bias_y_;
    gyro_z_ = ((float)raw_gz / 32.8f) - gyro_bias_z_;

    return true;
}
