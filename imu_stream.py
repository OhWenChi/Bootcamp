# imu_stream.py  (ESP32-S3 MicroPython)
from machine import Pin, I2C
import time, struct

i2c = I2C(0, sda=Pin(14), scl=Pin(2), freq=400000)
MPU = 0x68

# wake + ranges
i2c.writeto_mem(MPU, 0x6B, b"\x00")
i2c.writeto_mem(MPU, 0x1C, b"\x00")  # accel ±2g
i2c.writeto_mem(MPU, 0x1B, b"\x00")  # gyro  ±250 dps
time.sleep_ms(50)

def read_imu():
    d = i2c.readfrom_mem(MPU, 0x3B, 14)
    ax, ay, az, _, gx, gy, gz = struct.unpack(">hhhhhhh", d)
    return (
        ax / 16384.0, ay / 16384.0, az / 16384.0,
        gx / 131.0,   gy / 131.0,   gz / 131.0
    )

print("ts_ms,ax,ay,az,gx,gy,gz")

PERIOD_MS = 20  # target ~50 Hz
next_t = time.ticks_add(time.ticks_ms(), PERIOD_MS)

while True:
    ax, ay, az, gx, gy, gz = read_imu()
    ts = time.ticks_ms()
    print("{},{:.5f},{:.5f},{:.5f},{:.3f},{:.3f},{:.3f}".format(ts, ax, ay, az, gx, gy, gz))

    sleep = time.ticks_diff(next_t, time.ticks_ms())
    if sleep > 0:
        time.sleep_ms(sleep)
    next_t = time.ticks_add(next_t, PERIOD_MS)



