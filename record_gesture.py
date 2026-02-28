# record_gesture.py (Laptop)
import os, time
from datetime import datetime
import serial
from serial.tools import list_ports

BAUD = 115200
OUT_DIR = "imu_data"
SAMPLE_SECONDS = 3.0

MAP = {"i": "idle", "s": "shake", "w": "wave", "r": "raise"}
VALID = set(MAP.values())

def choose_port():
    ports = list(list_ports.comports())
    for idx, p in enumerate(ports):
        print(f"[{idx}] {p.device}  {p.description}")
    return ports[int(input("Choose port index: ").strip())].device

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    port = choose_port()

    ser = serial.Serial(port, BAUD, timeout=1)
    time.sleep(1.0)
    ser.reset_input_buffer()

    while True:
        x = input("Label (idle(i)/shake(s)/wave(w)/raise(r)) or q: ").strip().lower()
        if x == "q":
            break

        label = MAP.get(x, x)
        if label not in VALID:
            print("Invalid input. Use i/s/w/r or q.")
            continue

        # IMPORTANT: clear any backlog right before recording
        ser.reset_input_buffer()

        # Optional but nice for students
        print("Ready... 3")
        time.sleep(0.3)
        print("2")
        time.sleep(0.3)
        print("1")
        time.sleep(0.3)
        print("GO!")

        fname = os.path.join(
            OUT_DIR, f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        rows = 0
        with open(fname, "w", encoding="utf-8") as f:
            f.write("ts_ms,ax,ay,az,gx,gy,gz,label\n")

            t0 = time.time()
            while time.time() - t0 < SAMPLE_SECONDS:
                line = ser.readline().decode(errors="ignore").strip()
                if not line or line.startswith("ts"):
                    continue
                parts = line.split(",")
                if len(parts) != 7:
                    continue
                f.write(",".join(parts) + f",{label}\n")
                rows += 1

        print(f"Recorded {rows} lines into {fname}")
        print(f"Approx sampling rate: {rows / SAMPLE_SECONDS:.1f} Hz\n")

    ser.close()

if __name__ == "__main__":
    main()
