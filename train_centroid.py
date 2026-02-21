# train_centroid.py (Laptop)
import os, glob
import numpy as np
import pandas as pd
import json

DATA_DIR = "imu_data"
OUT_MODEL = "model_params.py"

# Feature extraction from one CSV file (2s window)
def features_from_df(df: pd.DataFrame) -> np.ndarray:
    # Use magnitudes (more orientation-robust)
    a = df[["ax","ay","az"]].to_numpy()
    g = df[["gx","gy","gz"]].to_numpy()

    amag = np.sqrt((a*a).sum(axis=1))
    gmag = np.sqrt((g*g).sum(axis=1))

    feats = []
    for x in [amag, gmag]:
        feats += [
            float(np.mean(x)),
            float(np.std(x)),
            float(np.min(x)),
            float(np.max(x)),
            float(np.sum(x*x)),  # energy
        ]
    return np.array(feats, dtype=np.float32)

def main():
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not files:
        raise SystemExit("No CSV files found. Record data first.")

    X_list = []
    y_list = []
    used_files = []

    for fn in files:
        df = pd.read_csv(fn)
        if not set(["ax","ay","az","gx","gy","gz","label"]).issubset(df.columns):
            continue

        # Force plain Python string label (avoid np.str_)
        label = str(df["label"].iloc[0])
        feats = features_from_df(df)

        X_list.append(feats)
        y_list.append(label)
        used_files.append(fn)

    if not X_list:
        raise SystemExit("No valid CSVs with required columns found.")

    X = np.vstack(X_list).astype(np.float32)

    # IMPORTANT: keep y as pure Python strings (NOT np.array of dtype object)
    y = [str(v) for v in y_list]
    labels = sorted(set(y))  # pure Python strings

    centroids = {}
    y_arr = np.array(y)  # only for boolean masking; we won't export this
    for lab in labels:
        mean_vec = X[y_arr == lab].mean(axis=0)
        centroids[str(lab)] = [float(v) for v in mean_vec]  # pure floats

    # quick sanity report (training-set accuracy using nearest centroid)
    def predict(x):
        best_lab, best_d = None, 1e18
        for lab in labels:
            c = centroids[lab]  # list of floats
            d = 0.0
            for i in range(len(c)):
                diff = float(x[i]) - c[i]
                d += diff * diff
            if d < best_d:
                best_d, best_lab = d, lab
        return best_lab

    preds = [predict(x) for x in X]
    acc = (np.array(preds) == np.array(y)).mean()
    print(f"Training-set accuracy (centroid): {acc*100:.1f}%  (just a quick sanity check)")

    # Export as MicroPython-friendly params file (NO numpy anywhere)
    with open(OUT_MODEL, "w", encoding="utf-8") as f:
        f.write("# Auto-generated model parameters (nearest-centroid)\n")
        f.write("LABELS = " + repr(list(labels)) + "\n")
        f.write("CENTROIDS = " + repr(centroids) + "\n")

    print(f"Wrote model params to: {OUT_MODEL}")

if __name__ == "__main__":
    main()

