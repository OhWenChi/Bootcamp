# guardian_phone_dashboard_logger.py (laptop)
import asyncio
import csv
import json
import os
import re
import socket
import time
from datetime import datetime

from aiohttp import web
from bleak import BleakScanner, BleakClient

from guardian_config import (
    DEVICE_NAME,
    CHAR_UUID,
    WEB_PORT,
    CSV_FILE,
    ML_WINDOW_SECONDS
)

from dashboard_page import HTML_PAGE


# ============================================================
# EDGE AIoT SMART ASSET GUARDIAN - Laptop / Phone Dashboard
# guardian_phone_dashboard_logger.py
# ============================================================
# This file handles:
#   1. BLE connection to ESP32
#   2. Parsing ESP32 live data
#   3. Sending data to phone browser dashboard
#   4. Recording labelled 3-second ML training windows
#
# The dashboard UI itself is stored in:
#   dashboard_page.py
#
# Settings are stored in:
#   guardian_config.py
# ============================================================


# ============================================================
# LIVE DASHBOARD STATE
# ============================================================

latest_data = {
    "status": "SEARCHING",
    "event": "WAITING",
    "mode": "--",
    "tilt": 0,
    "vib": 0,
    "shock": 0,
    "sens": 0,
    "time": "--:--:--",
    "ble": "Searching",
    "label": "STOPPED",
    "samples": 0,
    "events": []
}

clients = set()
event_log = []

current_label = "STOPPED"
sample_count = 0
sample_buffer = []
last_window_start = time.time()


# ============================================================
# CSV / ML WINDOW LOGGING
# ============================================================

def init_csv():
    """
    Create the CSV file if it does not exist.
    Each row is one 3-second behaviour window.
    """
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "label",
                "rule_status",
                "detected_event",
                "decision_mode",
                "tilt_mean",
                "tilt_max",
                "vibration_mean",
                "vibration_max",
                "shock_mean",
                "shock_peak",
                "sensitivity_mean",
                "n_readings"
            ])


def mean(values):
    if len(values) == 0:
        return 0
    return sum(values) / len(values)


def most_common(values):
    if len(values) == 0:
        return "UNKNOWN"

    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1

    return max(counts, key=counts.get)


def add_to_sample_buffer():
    """
    Add the latest live reading into the current 3-second ML window.
    No data is saved if recording is stopped.
    """
    global sample_buffer

    if current_label == "STOPPED":
        return

    sample_buffer.append({
        "status": latest_data["status"],
        "event": latest_data["event"],
        "mode": latest_data["mode"],
        "tilt": float(latest_data["tilt"]),
        "vib": float(latest_data["vib"]),
        "shock": float(latest_data["shock"]),
        "sens": int(latest_data["sens"])
    })


def save_window_if_ready():
    """
    Save one ML training row every ML_WINDOW_SECONDS.
    Each saved row summarises multiple live readings.
    """
    global sample_buffer, sample_count, last_window_start

    if current_label == "STOPPED":
        return

    now = time.time()

    if now - last_window_start < ML_WINDOW_SECONDS:
        return

    if len(sample_buffer) < 3:
        sample_buffer = []
        last_window_start = now
        return

    tilts = [row["tilt"] for row in sample_buffer]
    vibs = [row["vib"] for row in sample_buffer]
    shocks = [row["shock"] for row in sample_buffer]
    sens_values = [row["sens"] for row in sample_buffer]
    statuses = [row["status"] for row in sample_buffer]
    event_values = [row["event"] for row in sample_buffer]
    mode_values = [row["mode"] for row in sample_buffer]

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            current_label,
            most_common(statuses),
            most_common(event_values),
            most_common(mode_values),
            round(mean(tilts), 3),
            round(max(tilts), 3),
            round(mean(vibs), 3),
            round(max(vibs), 3),
            round(mean(shocks), 3),
            round(max(shocks), 3),
            round(mean(sens_values), 3),
            len(sample_buffer)
        ])

    sample_count += 1
    sample_buffer = []
    last_window_start = now


# ============================================================
# NETWORK HELPERS
# ============================================================

def get_laptop_ip():
    """
    Get the laptop IP address so the phone can open:
    http://<laptop-ip>:8000
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ============================================================
# BLE DATA PARSING
# ============================================================

def parse_ble_message(text):
    """
    Parse ESP32 BLE message.

    Expected format:
    SAFE,Tilt=8,Vib=12,Shock=0.04,Sens=65,Event=SAFE,Mode=ML

    Older format is also accepted:
    SAFE,Tilt=8,Vib=12,Shock=0.04,Sens=65
    """
    global latest_data, event_log

    pattern = (
        r"(SAFE|WARNING|DANGER),"
        r"Tilt=([-0-9.]+),"
        r"Vib=([-0-9.]+),"
        r"Shock=([-0-9.]+),"
        r"Sens=([0-9]+)"
        r"(?:,Event=([A-Z_]+))?"
        r"(?:,Mode=([A-Z+_]+))?"
    )

    match = re.search(pattern, text)

    if not match:
        return

    old_status = latest_data["status"]

    new_status = match.group(1)
    tilt = float(match.group(2))
    vib = float(match.group(3))
    shock = float(match.group(4))
    sens = int(match.group(5))

    event = match.group(6) if match.group(6) else "UNKNOWN"
    mode = match.group(7) if match.group(7) else "--"

    now = datetime.now().strftime("%H:%M:%S")

    latest_data.update({
        "status": new_status,
        "event": event,
        "mode": mode,
        "tilt": tilt,
        "vib": vib,
        "shock": shock,
        "sens": sens,
        "time": now,
        "ble": "Connected",
        "label": current_label,
        "samples": sample_count
    })

    if new_status != old_status:
        event_log.insert(0, f"{now}  {old_status} → {new_status} ({event})")
        event_log[:] = event_log[:6]

    latest_data["events"] = event_log

    add_to_sample_buffer()
    save_window_if_ready()


# ============================================================
# WEBSOCKET BROADCAST
# ============================================================

async def broadcast():
    """
    Send latest live data to every connected phone browser.
    """
    if not clients:
        return

    latest_data["label"] = current_label
    latest_data["samples"] = sample_count
    latest_data["events"] = event_log

    message = json.dumps(latest_data)

    disconnected = []

    for ws in clients:
        try:
            await ws.send_str(message)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        clients.discard(ws)


# ============================================================
# BLE CONNECTION TASK
# ============================================================

def notification_handler(sender, data):
    """
    Called whenever ESP32 sends a BLE notification.
    """
    try:
        text = data.decode("utf-8")
        parse_ble_message(text)
        asyncio.create_task(broadcast())
    except Exception as e:
        print("BLE parse error:", e)


async def ble_task():
    """
    Continuously scan for ESP32, connect, and listen for BLE notifications.
    """
    global latest_data

    while True:
        print("Scanning for ESP32:", DEVICE_NAME)

        latest_data["status"] = "SEARCHING"
        latest_data["event"] = "WAITING"
        latest_data["mode"] = "--"
        latest_data["ble"] = "Searching"
        await broadcast()

        device = None
        devices = await BleakScanner.discover(timeout=8)

        for d in devices:
            if d.name == DEVICE_NAME:
                device = d
                break

        if device is None:
            print("ESP32 not found. Retrying...")

            latest_data["status"] = "NOT FOUND"
            latest_data["event"] = "NOT_FOUND"
            latest_data["mode"] = "--"
            latest_data["ble"] = "Not Found"
            await broadcast()

            await asyncio.sleep(3)
            continue

        try:
            print("Connecting to", device.name)

            async with BleakClient(device.address) as client:
                latest_data["ble"] = "Connected"
                await broadcast()

                print("Connected:", client.is_connected)

                await client.start_notify(CHAR_UUID, notification_handler)

                while client.is_connected:
                    await asyncio.sleep(0.2)

        except Exception as e:
            print("BLE error:", e)

        latest_data["ble"] = "Disconnected"
        await broadcast()
        await asyncio.sleep(2)


# ============================================================
# WEB SERVER ROUTES
# ============================================================

async def index(request):
    """
    Serve the phone dashboard page.
    """
    return web.Response(text=HTML_PAGE, content_type="text/html")


async def websocket_handler(request):
    """
    Keep a live WebSocket connection with the phone browser.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    clients.add(ws)
    await ws.send_str(json.dumps(latest_data))

    async for msg in ws:
        pass

    clients.discard(ws)
    return ws


async def set_label(request):
    """
    Called when the phone dashboard button is pressed.

    Example:
    /set_label?value=SAFE
    /set_label?value=TILT
    /set_label?value=VIBRATION
    /set_label?value=SHOCK
    /set_label?value=STOPPED
    """
    global current_label, sample_buffer, last_window_start

    value = request.query.get("value", "STOPPED").upper()

    allowed = ["SAFE", "TILT", "VIBRATION", "SHOCK", "STOPPED"]

    if value not in allowed:
        value = "STOPPED"

    current_label = value
    latest_data["label"] = current_label

    # Start a fresh 3-second window whenever the label changes.
    sample_buffer = []
    last_window_start = time.time()

    print("Training label:", current_label)

    await broadcast()

    return web.json_response({
        "label": current_label,
        "samples": sample_count
    })


async def start_web_server():
    """
    Start the phone dashboard web server.
    """
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/set_label", set_label)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()

    ip = get_laptop_ip()

    print("\n======================================")
    print("Phone Dashboard + ML Logger Ready")
    print("Open this on your phone browser:")
    print(f"http://{ip}:{WEB_PORT}")
    print("CSV file:", CSV_FILE)
    print("BLE device name:", DEVICE_NAME)
    print("======================================\n")


# ============================================================
# MAIN
# ============================================================

async def main():
    init_csv()
    await start_web_server()
    asyncio.create_task(ble_task())

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())

