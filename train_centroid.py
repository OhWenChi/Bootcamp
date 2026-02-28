# train_centroid.py (Laptop)
import os, glob
import numpy as np
import pandas as pd

DATA_DIR = "imu_data"
OUT_MODEL = "model_params.py"

def features_from_df(df: pd.DataFrame):
    a = df[["ax", "ay", "az"]].to_numpy(dtype=np.float32)
    g = df[["gx", "gy", "gz"]].to_numpy(dtype=np.float32)

    amag = np.sqrt((a * a).sum(axis=1))
    gmag = np.sqrt((g * g).sum(axis=1))

    def stats(x):
        return [
            float(x.mean()),
            float(x.std()),
            float(x.min()),
            float(x.max()),
            float((x * x).sum() / len(x)),
        ]

    return np.array(stats(amag) + stats(gmag), dtype=np.float32)

def main():
    files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    if not files:
        print("No CSV files found in imu_data/")
        return

    X, y = [], []
    for fn in files:
        df = pd.read_csv(fn)
        label = str(df["label"].iloc[0])
        X.append(features_from_df(df))
        y.append(label)

    X = np.vstack(X)
    y = np.array(y, dtype=str)

    labels = sorted(set(y.tolist()))
    centroids = {lab: [float(v) for v in X[y == lab].mean(axis=0)] for lab in labels}

    def predict(x):
        best_lab, best_d = None, 1e18
        for lab in labels:
            c = np.array(centroids[lab], dtype=np.float32)
            d = float(((x - c) ** 2).sum())
            if d < best_d:
                best_d, best_lab = d, lab
        return best_lab

    acc = (np.array([predict(x) for x in X]) == y).mean()
    print(f"Training accuracy: {acc*100:.1f}%")

    with open(OUT_MODEL, "w", encoding="utf-8") as f:
        f.write("# Auto-generated model parameters (nearest-centroid)\n")
        f.write("LABELS = " + repr(labels) + "\n")
        f.write("CENTROIDS = " + repr(centroids) + "\n")

    print("Wrote:", OUT_MODEL)

if __name__ == "__main__":
    main()
