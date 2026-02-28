# imu_infer.py (ESP32-S3 MicroPython) - UPDATED for SSD1306 0.96" 128x64
from machine import Pin, I2C, PWM
import time, struct, math
from model_params import LABELS, CENTROIDS
import ssd1306

# I2C shared by IMU + OLED
i2c = I2C(0, sda=Pin(14), scl=Pin(2), freq=400000)

# OLED
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# LEDs + buzzer
led1 = Pin(1, Pin.OUT)
led2 = Pin(44, Pin.OUT)
led3 = Pin(43, Pin.OUT)

buzzer = PWM(Pin(21))
buzzer.duty(0)

def set_leds(a, b, c):
    led1.value(a); led2.value(b); led3.value(c)

def beep(ms=120, freq=1500):
    buzzer.freq(freq)
    buzzer.duty(400)
    time.sleep_ms(ms)
    buzzer.duty(0)

# IMU init
MPU = 0x68
i2c.writeto_mem(MPU, 0x6B, b"\x00")
i2c.writeto_mem(MPU, 0x1C, b"\x00")
i2c.writeto_mem(MPU, 0x1B, b"\x00")
time.sleep_ms(50)

def read_imu():
    d = i2c.readfrom_mem(MPU, 0x3B, 14)
    ax, ay, az, _, gx, gy, gz = struct.unpack(">hhhhhhh", d)
    return (
        ax / 16384.0, ay / 16384.0, az / 16384.0,
        gx / 131.0,   gy / 131.0,   gz / 131.0
    )

def features_from_window(buf):
    amag = []
    gmag = []
    for ax, ay, az, gx, gy, gz in buf:
        amag.append(math.sqrt(ax*ax + ay*ay + az*az))
        gmag.append(math.sqrt(gx*gx + gy*gy + gz*gz))

    def stats(x):
        n = len(x)
        m = sum(x) / n
        v = sum((t - m) * (t - m) for t in x) / n
        return [m, math.sqrt(v), min(x), max(x), sum(t*t for t in x)/ n]

    return stats(amag) + stats(gmag)

def predict_label(f):
    best_lab, best_d = None, 1e18
    for lab in LABELS:
        c = CENTROIDS[lab]
        d = 0.0
        for i in range(len(f)):
            diff = f[i] - c[i]
            d += diff * diff
        if d < best_d:
            best_d, best_lab = d, lab
    return best_lab

# Window settings
HZ = 50
WIN_SEC = 3
N = HZ * WIN_SEC
PERIOD_MS = int(1000 / HZ)

def show_label(lab):
    oled.fill(0)
    oled.text("GESTURE:", 0, 0)
    oled.text(lab.upper(), 0, 16)
    oled.show()

while True:
    buf = []
    t_next = time.ticks_add(time.ticks_ms(), PERIOD_MS)

    for _ in range(N):
        buf.append(read_imu())
        sleep = time.ticks_diff(t_next, time.ticks_ms())
        if sleep > 0:
            time.sleep_ms(sleep)
        t_next = time.ticks_add(t_next, PERIOD_MS)

    f = features_from_window(buf)
    lab = predict_label(f)

    # Distinct LED patterns
    if lab == "idle":
        set_leds(0, 0, 0)
    elif lab == "wave":
        set_leds(0, 1, 0)
        beep(120)
    elif lab == "shake":
        set_leds(1, 0, 1)
        beep(60); time.sleep_ms(60); beep(60)
    elif lab == "raise":
        set_leds(1, 1, 1)
        beep(300)
    else:
        set_leds(0, 0, 0)

    show_label(lab)
    time.sleep_ms(50)
