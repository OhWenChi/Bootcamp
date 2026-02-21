# imu_stream.py  (ESP32-S3 MicroPython)
from machine import Pin, I2C
import time
import struct

# Your confirmed wiring:
# I2C0 SDA=14, SCL=2
i2c = I2C(0, sda=Pin(14), scl=Pin(2), freq=400000)

MPU_ADDR = 0x68

# Wake MPU6050
i2c.writeto_mem(MPU_ADDR, 0x6B, b'\x00')
time.sleep_ms(50)

# Optional: set ranges (defaults usually fine)
# accel config (0x1C): 0 = +/-2g
# gyro config  (0x1B): 0 = +/-250 dps
i2c.writeto_mem(MPU_ADDR, 0x1C, b'\x00')
i2c.writeto_mem(MPU_ADDR, 0x1B, b'\x00')
time.sleep_ms(10)

def read_imu():
    # Read 14 bytes starting at ACCEL_XOUT_H (0x3B)
    data = i2c.readfrom_mem(MPU_ADDR, 0x3B, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", data)

    # Scale factors for +/-2g and +/-250 dps
    ax_g = ax / 16384.0
    ay_g = ay / 16384.0
    az_g = az / 16384.0
    gx_dps = gx / 131.0
    gy_dps = gy / 131.0
    gz_dps = gz / 131.0

    return ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps

# Print CSV header once
print("ts_ms,ax,ay,az,gx,gy,gz")

# Target ~50 Hz
period_ms = 20
next_t = time.ticks_add(time.ticks_ms(), period_ms)

while True:
    ax, ay, az, gx, gy, gz = read_imu()
    ts = time.ticks_ms()
    # Keep output simple and parseable
    print("{},{:.5f},{:.5f},{:.5f},{:.3f},{:.3f},{:.3f}".format(ts, ax, ay, az, gx, gy, gz))

    # timing
    now = time.ticks_ms()
    sleep = time.ticks_diff(next_t, now)
    if sleep > 0:
        time.sleep_ms(sleep)
    next_t = time.ticks_add(next_t, period_ms)



