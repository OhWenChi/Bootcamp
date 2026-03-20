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

    # Axis mean features for differentiate shake and wave
    ax_mean = float(a[:, 0].mean())
    ay_mean = float(a[:, 1].mean())
    az_mean = float(a[:, 2].mean())

    return np.array(
        stats(amag) + stats(gmag) + [ax_mean, ay_mean, az_mean],
        dtype=np.float32
    )

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

    # Predictions
    y_pred = np.array([predict(x) for x in X])
    
    # Accuracy
    acc = (y_pred == y).mean()
    print(f"Accuracy: {acc*100:.1f}%\n")
    
    # Detailed metrics for Precision, Recall and F1-score
    for lab in labels:
        tp = np.sum((y_pred == lab) & (y == lab))
        fp = np.sum((y_pred == lab) & (y != lab))
        fn = np.sum((y_pred != lab) & (y == lab))
    
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    
        print(f"{lab}:")
        print(f"  Precision: {precision:.2f}")
        print(f"  Recall:    {recall:.2f}")
        print(f"  F1-score:  {f1:.2f}\n")

    with open(OUT_MODEL, "w", encoding="utf-8") as f:
        f.write("# Auto-generated model parameters (nearest-centroid)\n")
        f.write("LABELS = " + repr(labels) + "\n")
        f.write("CENTROIDS = " + repr(centroids) + "\n")

    print("Wrote:", OUT_MODEL)

if __name__ == "__main__":
    main()
