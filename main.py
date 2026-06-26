# main.py (ESP32-S3 MicroPython)
from machine import Pin, I2C, ADC
import bluetooth
import time
import struct
import math
import neopixel
from micropython import const

# ============================================================
# EDGE AIoT SMART ASSET GUARDIAN - ESP32-S3 MicroPython
# main.py
# ============================================================
# Required files on ESP32:
#   main.py
#   ssd1306.py
#   guardian_ml_model.py   only required when USE_ML_MODEL = True
#
# Flow:
#   MPU6050 -> ESP32 feature extraction -> rule/ML decision
#   -> OLED/RGB/Buzzer -> BLE -> phone dashboard
#
# Startup behaviour:
#   Keep the device still when the program starts.
#   The ESP32 automatically calibrates the starting position
#   as the normal SAFE position.
# ============================================================

# ----------------------------
# STUDENT / TEAM SETTINGS
# ----------------------------

DEVICE_NAME = "QuMinds-AIoT-TJX"
# For classroom use, change this on both ESP32 and laptop:
# DEVICE_NAME = "Guardian-01"

# ----------------------------
# HARDWARE PIN SETTINGS
# ----------------------------

I2C_SDA = 8
I2C_SCL = 9
MPU_ADDR = 0x68

RGB_PIN = 48
BUZZER_PIN = 47
POT_PIN = 1

# ----------------------------
# FEATURE / TIMING SETTINGS
# ----------------------------

SAMPLE_INTERVAL_MS = 50        # Fast sensor sampling for shock detection
BLE_SEND_INTERVAL_MS = 500     # Slower BLE/dashboard update
FEATURE_WINDOW_SIZE = 40       # 40 samples x 50ms = 2 seconds

# ML uses dashboard-level history:
# 6 BLE updates x 500ms = about 3 seconds
ML_HISTORY_SIZE = 6

DEFAULT_SENSITIVITY = 65

# ----------------------------
# ENABLE / DISABLE MODULES
# ----------------------------

USE_OLED = True
USE_RGB = True
USE_BUZZER = True
USE_POT = True

# Main switch:
# False = use rule-based decision
# True  = use guardian_ml_model.py decision tree
USE_ML_MODEL = True

# Safety backup:
# If ML says SAFE but rule logic detects WARNING/DANGER, rule can override.
# For pure ML demo, set this to False.
USE_RULE_SAFETY_OVERRIDE = True

# Debug print:
# True = serial monitor shows live messages
# False = cleaner for demo
DEBUG_PRINT_MESSAGES = True

# BLE UUIDs
SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")

# ============================================================
# OPTIONAL ML MODEL IMPORT
# ============================================================

ML_MODEL_READY = False

if USE_ML_MODEL:
    try:
        from guardian_ml_model import predict_event, event_to_status
        ML_MODEL_READY = True
        print("ML model loaded")
    except Exception as e:
        ML_MODEL_READY = False
        print("ML model not loaded:", e)
        print("System will fall back to rule-based logic")
else:
    print("ML model disabled. Using rule-based logic")


# ============================================================
# I2C + MPU6050 SETUP
# ============================================================

i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=100000)
print("I2C scan:", i2c.scan())

# Wake MPU6050
i2c.writeto_mem(MPU_ADDR, 0x6B, b"\x00")
time.sleep(0.2)

# ============================================================
# OLED SETUP
# ============================================================

oled = None

if USE_OLED:
    try:
        import ssd1306

        devices = i2c.scan()
        if 0x3C in devices:
            oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)
            oled.fill(0)
            oled.text("AIoT Guardian", 0, 0)
            oled.text("OLED Ready", 0, 16)
            oled.text("Addr: 0x3C", 0, 32)
            oled.show()
            print("OLED found at 0x3C")
        else:
            print("OLED not found, disabled")
            oled = None

    except Exception as e:
        print("OLED disabled:", e)
        oled = None


def oled_show(status, event, tilt, vibration, shock, sensitivity, ble_connected):
    if oled is None:
        return

    oled.fill(0)
    oled.text("AIoT Guardian", 0, 0)
    oled.text("Status:" + status, 0, 12)
    oled.text("Event:" + event[:8], 0, 24)
    oled.text("T:{:.0f} V:{:.0f}".format(tilt, vibration), 0, 36)
    oled.text("S:{:.2f} Sen:{:d}".format(shock, sensitivity), 0, 48)

    if ble_connected:
        oled.text("BLE", 104, 0)
    else:
        oled.text("--", 112, 0)

    oled.show()


# ============================================================
# RGB LED SETUP
# ============================================================

rgb = None

if USE_RGB:
    try:
        rgb = neopixel.NeoPixel(Pin(RGB_PIN), 1)
        print("RGB enabled on pin", RGB_PIN)
    except Exception as e:
        print("RGB disabled:", e)
        rgb = None


def set_rgb(status, event=""):
    if rgb is None:
        return

    # Event-specific colours first
    if event == "VIBRATION":
        rgb[0] = (25, 0, 35)      # Purple
    elif event == "TILT":
        rgb[0] = (35, 18, 0)      # Yellow/orange
    elif event == "SHOCK":
        rgb[0] = (45, 0, 0)       # Red
    elif event == "SAFE":
        rgb[0] = (0, 30, 0)       # Green

    # Fallback colours
    elif status == "SAFE":
        rgb[0] = (0, 30, 0)       # Green
    elif status == "WARNING":
        rgb[0] = (35, 18, 0)      # Yellow/orange
    elif status == "DANGER":
        rgb[0] = (45, 0, 0)       # Red
    elif status == "CAL":
        rgb[0] = (0, 0, 45)       # Blue
    else:
        rgb[0] = (0, 0, 0)

    rgb.write()


# ============================================================
# BUZZER SETUP
# ============================================================

buzzer = None
last_buzzer_ms = 0
buzzer_state = False

if USE_BUZZER:
    try:
        buzzer = Pin(BUZZER_PIN, Pin.OUT)
        buzzer.value(0)
        print("Buzzer enabled on pin", BUZZER_PIN)
    except Exception as e:
        print("Buzzer disabled:", e)
        buzzer = None


def update_buzzer(status):
    global last_buzzer_ms, buzzer_state

    if buzzer is None:
        return

    now = time.ticks_ms()

    if status == "DANGER":
        # Repeated urgent beep
        if time.ticks_diff(now, last_buzzer_ms) >= 250:
            buzzer_state = not buzzer_state
            buzzer.value(1 if buzzer_state else 0)
            last_buzzer_ms = now

    elif status == "WARNING":
        # Short beep once every 1.2 seconds
        if time.ticks_diff(now, last_buzzer_ms) >= 1200:
            buzzer.value(1)
            time.sleep_ms(60)
            buzzer.value(0)
            last_buzzer_ms = now
            buzzer_state = False

    else:
        buzzer.value(0)
        buzzer_state = False


# ============================================================
# POTENTIOMETER SETUP
# ============================================================

pot = None

if USE_POT:
    try:
        pot = ADC(Pin(POT_PIN))
        try:
            pot.atten(ADC.ATTN_11DB)
        except Exception:
            pass
        print("Potentiometer enabled on pin", POT_PIN)
    except Exception as e:
        print("Potentiometer disabled:", e)
        pot = None


def get_sensitivity():
    if pot is None:
        return DEFAULT_SENSITIVITY

    try:
        try:
            raw = pot.read_u16()
            sens = int((raw / 65535) * 100)
        except AttributeError:
            raw = pot.read()
            sens = int((raw / 4095) * 100)

        return max(0, min(100, sens))

    except Exception:
        return DEFAULT_SENSITIVITY


# ============================================================
# MPU6050 SENSOR FUNCTIONS
# ============================================================

def read_mpu6050():
    data = i2c.readfrom_mem(MPU_ADDR, 0x3B, 14)
    ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", data)

    ax_g = ax / 16384
    ay_g = ay / 16384
    az_g = az / 16384

    gx_dps = gx / 131
    gy_dps = gy / 131
    gz_dps = gz / 131

    pitch = math.atan2(
        ax_g,
        math.sqrt(ay_g * ay_g + az_g * az_g)
    ) * 180 / math.pi

    roll = math.atan2(
        ay_g,
        math.sqrt(ax_g * ax_g + az_g * az_g)
    ) * 180 / math.pi

    acc_mag = math.sqrt(ax_g * ax_g + ay_g * ay_g + az_g * az_g)
    gyro_mag = math.sqrt(gx_dps * gx_dps + gy_dps * gy_dps + gz_dps * gz_dps)

    return pitch, roll, acc_mag, gyro_mag


base_pitch = 0
base_roll = 0

tilt_window = []
shock_window = []
vib_window = []


def clear_feature_windows():
    global tilt_window, shock_window, vib_window
    tilt_window = []
    shock_window = []
    vib_window = []


# ============================================================
# ML WINDOW HISTORY
# ============================================================

ml_tilt_history = []
ml_vib_history = []
ml_shock_history = []
ml_sens_history = []


def clear_ml_history():
    global ml_tilt_history, ml_vib_history, ml_shock_history, ml_sens_history

    ml_tilt_history = []
    ml_vib_history = []
    ml_shock_history = []
    ml_sens_history = []


def list_mean(values):
    if len(values) == 0:
        return 0

    return sum(values) / len(values)


def add_ml_history(tilt, vibration, shock, sensitivity):
    ml_tilt_history.append(float(tilt))
    ml_vib_history.append(float(vibration))
    ml_shock_history.append(float(shock))
    ml_sens_history.append(float(sensitivity))

    if len(ml_tilt_history) > ML_HISTORY_SIZE:
        ml_tilt_history.pop(0)

    if len(ml_vib_history) > ML_HISTORY_SIZE:
        ml_vib_history.pop(0)

    if len(ml_shock_history) > ML_HISTORY_SIZE:
        ml_shock_history.pop(0)

    if len(ml_sens_history) > ML_HISTORY_SIZE:
        ml_sens_history.pop(0)


def ml_window_ready():
    # At least 3 readings are enough to start.
    # Full window is 6 readings, about 3 seconds.
    return len(ml_tilt_history) >= 3


def get_ml_features():
    tilt_mean = list_mean(ml_tilt_history)
    tilt_max = max(ml_tilt_history)

    vibration_mean = list_mean(ml_vib_history)
    vibration_max = max(ml_vib_history)

    shock_mean = list_mean(ml_shock_history)
    shock_peak = max(ml_shock_history)

    sensitivity_mean = list_mean(ml_sens_history)
    n_readings = len(ml_tilt_history)

    return (
        tilt_mean,
        tilt_max,
        vibration_mean,
        vibration_max,
        shock_mean,
        shock_peak,
        sensitivity_mean,
        n_readings
    )


# ============================================================
# AUTOMATIC STARTUP CALIBRATION
# ============================================================

def calibrate():
    global base_pitch, base_roll

    print("Calibrating...")
    set_rgb("CAL")

    if oled is not None:
        oled.fill(0)
        oled.text("AIoT Guardian", 0, 0)
        oled.text("Calibrating...", 0, 20)
        oled.text("Keep still", 0, 36)
        oled.show()

    total_pitch = 0
    total_roll = 0
    samples = 40

    for _ in range(samples):
        pitch, roll, acc_mag, gyro_mag = read_mpu6050()
        total_pitch += pitch
        total_roll += roll
        time.sleep_ms(30)

    base_pitch = total_pitch / samples
    base_roll = total_roll / samples

    clear_feature_windows()
    clear_ml_history()

    print("Calibration done")
    print("Base pitch:", base_pitch)
    print("Base roll :", base_roll)


# ============================================================
# FEATURE ENGINE
# ============================================================

def update_features(pitch, roll, acc_mag, gyro_mag):
    global tilt_window, shock_window, vib_window

    relative_pitch = pitch - base_pitch
    relative_roll = roll - base_roll

    # Tilt is how far the asset is away from its calibrated normal position.
    tilt = max(abs(relative_pitch), abs(relative_roll))

    # At rest, acceleration magnitude is around 1g.
    # A tap/drop/shock creates a short spike away from 1g.
    shock = abs(acc_mag - 1.0)

    # Gyro magnitude represents rotational movement.
    # Sustained shaking causes a higher average gyro value.
    vibration = gyro_mag

    tilt_window.append(tilt)
    shock_window.append(shock)
    vib_window.append(vibration)

    if len(tilt_window) > FEATURE_WINDOW_SIZE:
        tilt_window.pop(0)

    if len(shock_window) > FEATURE_WINDOW_SIZE:
        shock_window.pop(0)

    if len(vib_window) > FEATURE_WINDOW_SIZE:
        vib_window.pop(0)

    tilt_latest = tilt
    vibration_mean = sum(vib_window) / len(vib_window)
    shock_peak = max(shock_window)

    return tilt_latest, vibration_mean, shock_peak


# ============================================================
# RULE-BASED BACKUP DECISION
# ============================================================

def get_thresholds(sens):
    # Higher sensitivity means lower thresholds.
    tilt_warning = 45 - (sens * 0.20)
    tilt_danger = 70 - (sens * 0.25)

    shock_warning = 1.20 - (sens * 0.006)
    shock_danger = 2.00 - (sens * 0.008)

    vib_warning = 220 - (sens * 1.20)
    vib_danger = 420 - (sens * 2.00)

    # Keep thresholds within safe ranges.
    tilt_warning = max(20, tilt_warning)
    tilt_danger = max(40, tilt_danger)

    shock_warning = max(0.45, shock_warning)
    shock_danger = max(0.90, shock_danger)

    vib_warning = max(70, vib_warning)
    vib_danger = max(150, vib_danger)

    return tilt_warning, tilt_danger, shock_warning, shock_danger, vib_warning, vib_danger


danger_hold_until = 0
warning_hold_until = 0


def decide_status(tilt, vibration, shock, sens):
    global danger_hold_until, warning_hold_until

    now = time.ticks_ms()

    tilt_w, tilt_d, shock_w, shock_d, vib_w, vib_d = get_thresholds(sens)

    danger_now = (
        tilt >= tilt_d or
        shock >= shock_d or
        vibration >= vib_d
    )

    warning_now = (
        tilt >= tilt_w or
        shock >= shock_w or
        vibration >= vib_w
    )

    if danger_now:
        danger_hold_until = time.ticks_add(now, 1800)
        return "DANGER"

    if warning_now:
        warning_hold_until = time.ticks_add(now, 1000)
        return "WARNING"

    if time.ticks_diff(danger_hold_until, now) > 0:
        return "DANGER"

    if time.ticks_diff(warning_hold_until, now) > 0:
        return "WARNING"

    return "SAFE"


def estimate_rule_event(tilt, vibration, shock, sens):
    tilt_w, tilt_d, shock_w, shock_d, vib_w, vib_d = get_thresholds(sens)

    if shock >= shock_d:
        return "SHOCK"

    if vibration >= vib_w:
        return "VIBRATION"

    if tilt >= tilt_w:
        return "TILT"

    return "SAFE"


def choose_final_decision(rule_status, ml_status):
    if not USE_RULE_SAFETY_OVERRIDE:
        return ml_status

    # Safety override:
    # Rule-based DANGER should remain DANGER.
    if rule_status == "DANGER":
        return "DANGER"

    # If ML says SAFE but rule detects WARNING, keep WARNING.
    if rule_status == "WARNING" and ml_status == "SAFE":
        return "WARNING"

    return ml_status


# ============================================================
# BLE SETUP
# ============================================================

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)

_FLAG_READ = const(0x0002)
_FLAG_NOTIFY = const(0x0010)

_UART_SERVICE = (
    SERVICE_UUID,
    (
        (CHAR_UUID, _FLAG_READ | _FLAG_NOTIFY),
    ),
)


class BLEGuardian:
    def __init__(self, name):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.irq)

        ((self.tx_handle,),) = self.ble.gatts_register_services((_UART_SERVICE,))

        self.connections = set()
        self.name = name
        self.advertise()

    def irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, addr_type, addr = data
            self.connections.add(conn_handle)
            print("BLE connected")

        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, addr_type, addr = data
            self.connections.discard(conn_handle)
            print("BLE disconnected")
            self.advertise()

    def advertise(self):
        name = self.name

        adv_payload = bytearray([
            0x02, 0x01, 0x06,
            len(name) + 1, 0x09
        ]) + name.encode()

        self.ble.gap_advertise(100000, adv_payload)
        print("Advertising as", name)

    def is_connected(self):
        return len(self.connections) > 0

    def send(self, message):
        self.ble.gatts_write(self.tx_handle, message.encode())

        for conn in self.connections:
            self.ble.gatts_notify(conn, self.tx_handle, message.encode())


# ============================================================
# MAIN PROGRAM
# ============================================================

ble = BLEGuardian(DEVICE_NAME)
calibrate()

last_sample_ms = time.ticks_ms()
last_send_ms = time.ticks_ms()

latest_tilt = 0
latest_vibration = 0
latest_shock = 0
latest_status = "SAFE"
latest_event = "SAFE"

while True:
    now = time.ticks_ms()

    # Fast sensor sampling
    if time.ticks_diff(now, last_sample_ms) >= SAMPLE_INTERVAL_MS:
        pitch, roll, acc_mag, gyro_mag = read_mpu6050()

        latest_tilt, latest_vibration, latest_shock = update_features(
            pitch,
            roll,
            acc_mag,
            gyro_mag
        )

        last_sample_ms = now

    # Slower BLE/OLED/RGB/buzzer update
    if time.ticks_diff(now, last_send_ms) >= BLE_SEND_INTERVAL_MS:
        sensitivity = get_sensitivity()

        # Rule-based status is always calculated as backup.
        rule_status = decide_status(
            latest_tilt,
            latest_vibration,
            latest_shock,
            sensitivity
        )

        # Rule-estimated event is useful during warmup or when ML is off.
        latest_event = estimate_rule_event(
            latest_tilt,
            latest_vibration,
            latest_shock,
            sensitivity
        )

        decision_mode = "RULE"

        # Add dashboard-level values into ML history.
        add_ml_history(
            latest_tilt,
            latest_vibration,
            latest_shock,
            sensitivity
        )

        if USE_ML_MODEL and ML_MODEL_READY and ml_window_ready():
            (
                tilt_mean,
                tilt_max,
                vibration_mean,
                vibration_max,
                shock_mean,
                shock_peak,
                sensitivity_mean,
                n_readings
            ) = get_ml_features()

            ml_event = predict_event(
                tilt_mean,
                tilt_max,
                vibration_mean,
                vibration_max,
                shock_mean,
                shock_peak,
                sensitivity_mean,
                n_readings
            )

            ml_status = event_to_status(ml_event)

            latest_status = choose_final_decision(
                rule_status,
                ml_status
            )

            latest_event = ml_event

            if USE_RULE_SAFETY_OVERRIDE and latest_status != ml_status:
                decision_mode = "ML+RULE"
            else:
                decision_mode = "ML"

        else:
            latest_status = rule_status

            if USE_ML_MODEL and not ML_MODEL_READY:
                decision_mode = "NO_MODEL"
            elif USE_ML_MODEL and not ml_window_ready():
                decision_mode = "WARMUP"

        set_rgb(latest_status, latest_event)
        update_buzzer(latest_status)

        # Message starts with original format so old dashboards still work.
        # Extra Event and Mode fields are added for the improved dashboard.
        message = "{},Tilt={:.0f},Vib={:.0f},Shock={:.2f},Sens={},Event={},Mode={}".format(
            latest_status,
            latest_tilt,
            latest_vibration,
            latest_shock,
            sensitivity,
            latest_event,
            decision_mode
        )

        if DEBUG_PRINT_MESSAGES:
            print(message)

        ble.send(message)

        oled_show(
            latest_status,
            latest_event,
            latest_tilt,
            latest_vibration,
            latest_shock,
            sensitivity,
            ble.is_connected()
        )

        last_send_ms = now

    time.sleep_ms(5)
