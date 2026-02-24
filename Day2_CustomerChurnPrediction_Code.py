# Importing Libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Data Loading
df = pd.read_csv("WA_Fn-UseC_-Telco-Customer-Churn.csv")

# Minimal Cleaning
df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
df["TotalCharges"] = df["TotalCharges"].fillna(df["TotalCharges"].median())
df = df.drop(columns=["customerID"])

# Define regression target
y = df["MonthlyCharges"]
X = df.drop(columns=["MonthlyCharges"])

print(df.head())

# Data Exploration - Exploratory Data Analysis (EDA)
plt.figure()
plt.hist(y, bins=30)
plt.title("Distribution of MonthlyCharges (Target)")
plt.xlabel("MonthlyCharges")
plt.ylabel("Frequency")
plt.show()

# Data Spliting 
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Data Preprocessing
num_cols = X.select_dtypes(include=["int64","float64"]).columns
cat_cols = X.select_dtypes(include=["object"]).columns

preprocess = ColumnTransformer(
    transformers=[
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler())
        ]), num_cols),

        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore"))
        ]), cat_cols)
    ]
)

# Train Model
lin_model = Pipeline(steps=[
    ("preprocess", preprocess),
    ("model", LinearRegression())
])
lin_model.fit(X_train, y_train)

rf_model = Pipeline(steps=[
    ("preprocess", preprocess),
    ("model", RandomForestRegressor(
        n_estimators=300,
        random_state=42
    ))
])
rf_model.fit(X_train, y_train)

# Model Evaluation + Regression Visualise
def evaluate(model, X_test, y_test, name):
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)

    print(f"\n=== {name} ===")
    print("MAE :", round(mae, 2))
    print("RMSE:", round(rmse, 2))
    print("R²  :", round(r2, 4))

    # ---- Visual: Actual vs Predicted
    plt.figure()
    plt.scatter(y_test, preds, alpha=0.4)
    plt.title(f"Actual vs Predicted ({name})")
    plt.xlabel("Actual MonthlyCharges")
    plt.ylabel("Predicted MonthlyCharges")

    # Reference line (perfect predictions)
    min_v = min(y_test.min(), preds.min())
    max_v = max(y_test.max(), preds.max())
    plt.plot([min_v, max_v], [min_v, max_v])
    plt.show()

    # ---- Visual: Residuals (errors)
    residuals = y_test - preds
    plt.figure()
    plt.scatter(preds, residuals, alpha=0.4)
    plt.title(f"Residual Plot ({name})")
    plt.xlabel("Predicted MonthlyCharges")
    plt.ylabel("Residual (Actual - Predicted)")
    plt.axhline(0)
    plt.show()

    return preds

lin_preds = evaluate(lin_model, X_test, y_test, "Linear Regression")
rf_preds = evaluate(rf_model, X_test, y_test, "Random Forest Regression")
