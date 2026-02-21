# imu_infer.py (ESP32-S3 MicroPython) - UPDATED for SSD1306 0.96" 128x64
from machine import Pin, I2C, PWM
import time, struct, math

from ssd1306 import SSD1306_I2C
from model_params import LABELS, CENTROIDS

# --- Your wiring ---
# I2C0 SDA=14, SCL=2
i2c = I2C(0, sda=Pin(14), scl=Pin(2), freq=400000)

# LEDs
led2 = Pin(1, Pin.OUT)
led4 = Pin(44, Pin.OUT)
led6 = Pin(43, Pin.OUT)

# Buzzer
buzzer = PWM(Pin(21))
buzzer.duty(0)

MPU_ADDR = 0x68
OLED_ADDR = 0x3C  # change to 0x3D if your OLED scan shows 0x3D

# --- OLED: SSD1306 128x64 ---
oled = SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)

# --- MPU6050 init ---
i2c.writeto_mem(MPU_ADDR, 0x6B, b"\x00")  # wake
i2c.writeto_mem(MPU_ADDR, 0x1C, b"\x00")  # accel +/-2g
i2c.writeto_mem(MPU_ADDR, 0x1B, b"\x00")  # gyro  +/-250 dps
time.sleep_ms(50)

def read_imu():
    data = i2c.readfrom_mem(MPU_ADDR, 0x3B, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", data)
    # scale to g and deg/s
    ax = ax / 16384.0; ay = ay / 16384.0; az = az / 16384.0
    gx = gx / 131.0;   gy = gy / 131.0;   gz = gz / 131.0
    return ax, ay, az, gx, gy, gz

def features_from_window(samples):
    amag = []
    gmag = []
    for ax, ay, az, gx, gy, gz in samples:
        amag.append(math.sqrt(ax*ax + ay*ay + az*az))
        gmag.append(math.sqrt(gx*gx + gy*gy + gz*gz))

    def feats(x):
        n = len(x)
        mean = sum(x) / n
        var = sum((v - mean) * (v - mean) for v in x) / n
        std = math.sqrt(var)
        mn = min(x)
        mx = max(x)
        energy = sum(v * v for v in x)
        return [mean, std, mn, mx, energy]

    return feats(amag) + feats(gmag)  # 10 features

def predict_label(f):
    best_lab = None
    best_d = 1e18
    for lab in LABELS:
        c = CENTROIDS[lab]
        d = 0.0
        for i in range(len(f)):
            diff = f[i] - c[i]
            d += diff * diff
        if d < best_d:
            best_d = d
            best_lab = lab
    return best_lab, best_d

# --- Outputs ---
def set_leds(a, b, c):
    led2.value(a); led4.value(b); led6.value(c)

def buzz(pattern):
    if pattern == "off":
        buzzer.duty(0)
        return
    buzzer.freq(1500)
    if pattern == "short":
        buzzer.duty(400); time.sleep_ms(80); buzzer.duty(0)
    elif pattern == "medium":
        buzzer.duty(400); time.sleep_ms(180); buzzer.duty(0)
    elif pattern == "long":
        buzzer.duty(400); time.sleep_ms(450); buzzer.duty(0)
    elif pattern == "rapid":
        for _ in range(3):
            buzzer.duty(400); time.sleep_ms(60); buzzer.duty(0); time.sleep_ms(60)

# Windowing (MATCH TRAINING: 3 seconds)
HZ = 50
WIN_SEC = 3
N = HZ * WIN_SEC
PERIOD_MS = int(1000 / HZ)

print("Inference ready. Perform gestures: idle/shake/wave/raise")

while True:
    # collect window
    buf = []
    t_next = time.ticks_add(time.ticks_ms(), PERIOD_MS)
    for _ in range(N):
        buf.append(read_imu())
        sleep = time.ticks_diff(t_next, time.ticks_ms())
        if sleep > 0:
            time.sleep_ms(sleep)
        t_next = time.ticks_add(t_next, PERIOD_MS)

    f = features_from_window(buf)
    lab, dist = predict_label(f)

    # Display + outputs
    oled.fill(0)
    oled.text("GESTURE:", 0, 0, 1)
    oled.text(lab.upper(), 0, 14, 1)

    if lab == "idle":
        set_leds(0, 0, 0); buzz("off")
        oled.text("Status: calm", 0, 34, 1)
    elif lab == "shake":
        set_leds(1, 1, 1); buzz("rapid")
        oled.text("Action: alert", 0, 34, 1)
    elif lab == "wave":
        set_leds(1, 0, 1); time.sleep_ms(80)
        buzz("medium")
        oled.text("Action: greet", 0, 34, 1)
    elif lab == "raise":
        set_leds(0, 1, 0); buzz("long")
        oled.text("Action: up", 0, 34, 1)
    else:
        set_leds(0, 0, 0); buzz("off")
        oled.text("Unknown", 0, 34, 1)

    oled.show()

