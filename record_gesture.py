import serial
import time
import os
from datetime import datetime

PORT = "COM4"        # change if needed
BAUD = 115200
OUT_DIR = "imu_data"
SAMPLE_SECONDS = 3.0  # 3–4s is safer than 2s
WARMUP_SECONDS = 2.0  # let USB CDC stabilise
IGNORE_FIRST_LINES = 10  # ignore initial junk

VALID_LABELS = {"idle", "shake", "wave", "raise"}

def parse_line(line: str):
    line = line.strip()
    if not line:
        return None
    if line.startswith("ts") or line.startswith("ts_ms"):
        return None
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 7:
        return None
    return parts  # [ts, ax, ay, az, gx, gy, gz]

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Opening {PORT} @ {BAUD} ...")
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        print(f"Warm-up {WARMUP_SECONDS}s (USB CDC stabilise)...")
        time.sleep(WARMUP_SECONDS)
        ser.reset_input_buffer()

        print("Ignoring a few initial lines (max 3 seconds)...")
        ignored = 0
        t_ignore = time.time()
        while ignored < IGNORE_FIRST_LINES and (time.time() - t_ignore) < 3.0:
            raw = ser.readline()
            if raw:
                ignored += 1
        print(f"Ignored {ignored} lines. Starting interactive recording.")


        print("\nReady. Type a label to record a sample, or 'q' to quit.")
        print("Valid labels:", ", ".join(sorted(VALID_LABELS)))
        print(f"Each sample records {SAMPLE_SECONDS:.1f} seconds.\n")

        while True:
            label = input("Label (idle/shake/wave/raise) or q: ").strip().lower()
            if label == "q":
                break
            if label not in VALID_LABELS:
                print("Invalid label. Try again.")
                continue

            fname = os.path.join(
                OUT_DIR, f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            with open(fname, "w", encoding="utf-8") as f:
                f.write("ts_ms,ax,ay,az,gx,gy,gz,label\n")

                print(f"Recording '{label}' NOW for {SAMPLE_SECONDS:.1f}s...")
                t0 = time.time()
                rows = 0

                while time.time() - t0 < SAMPLE_SECONDS:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode(errors="ignore")
                    parts = parse_line(line)
                    if parts is None:
                        continue
                    f.write(",".join(parts) + f",{label}\n")
                    rows += 1

            print(f"Saved {rows} rows → {fname}\n")

if __name__ == "__main__":
    main()

