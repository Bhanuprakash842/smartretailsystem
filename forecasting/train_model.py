"""
train_model.py
==============
Trains a demand-forecasting model using the generated CSV data.

Pipeline:
  1. Load  data/daily_demand.csv
  2. Feature-engineer lag features, rolling statistics, month/week encodings
  3. Train a Random Forest (per-product) + a global XGBoost model
  4. Evaluate on the last 30-day holdout
  5. Persist models + scalers to  forecasting/models/

Run:
    python forecasting/train_model.py
"""

import os
import json
import warnings
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score

warnings.filterwarnings("ignore")

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "data", "daily_demand.csv")
MODEL_DIR  = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# ── feature columns used by the model ────────────────────────────────────────
FEATURE_COLS = [
    "product_id", "price",
    "day_of_week", "is_weekend", "month", "year",
    "week_of_year", "day_of_year",
    "is_promotion", "promo_discount",
    # lag features (added in engineer_features)
    "lag_1", "lag_7", "lag_14", "lag_30",
    # rolling stats
    "roll_7_mean", "roll_7_std",
    "roll_14_mean", "roll_14_std",
    "roll_30_mean",
    # category encoding
    "category_enc",
    # season encoding
    "season_enc",
]
TARGET_COL = "qty_sold"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df.sort_values(["product_id", "date"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, and encoded features to the dataframe."""

    # ── label-encode categoricals ─────────────────────────────────────────
    cat_enc  = LabelEncoder().fit(df["category"])
    sea_enc  = LabelEncoder().fit(df["season"])
    df["category_enc"] = cat_enc.transform(df["category"])
    df["season_enc"]   = sea_enc.transform(df["season"])

    # Save encoders
    with open(os.path.join(MODEL_DIR, "category_encoder.pkl"), "wb") as f:
        pickle.dump(cat_enc, f)
    with open(os.path.join(MODEL_DIR, "season_encoder.pkl"), "wb") as f:
        pickle.dump(sea_enc, f)

    # ── lag & rolling per product ─────────────────────────────────────────
    lag_days     = [1, 7, 14, 30]
    rolling_wins = [7, 14, 30]

    grp = df.groupby("product_id")["qty_sold"]
    for lag in lag_days:
        df[f"lag_{lag}"] = grp.shift(lag)

    for w in rolling_wins:
        df[f"roll_{w}_mean"] = grp.shift(1).rolling(w, min_periods=1).mean().reset_index(level=0, drop=True)
        if w in (7, 14):
            df[f"roll_{w}_std"]  = grp.shift(1).rolling(w, min_periods=1).std().reset_index(level=0, drop=True)

    # drop rows where lags are NaN (first 30 days per product)
    df.dropna(subset=[f"lag_{l}" for l in lag_days], inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


def train_global_model(X_train, y_train, X_test, y_test, product_names):
    """Train a single GradientBoosting model on all products."""
    print("\n[INFO] Training Global GradientBoosting model ...")
    model = GradientBoostingRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_leaf=10,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = np.maximum(0, model.predict(X_test))
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2   = r2_score(y_test, y_pred)
    print(f"  Global model  ->  MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.3f}")

    model_path = os.path.join(MODEL_DIR, "global_gb_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  Saved -> {model_path}")

    return model, {"mae": round(mae, 3), "rmse": round(rmse, 3), "r2": round(r2, 3)}


def train_per_product_models(df: pd.DataFrame):
    """Train one RandomForest per product for maximum accuracy."""
    print("\n[INFO] Training per-product RandomForest models ...")
    metrics_all = {}
    models = {}

    for pid in df["product_id"].unique():
        pdata = df[df["product_id"] == pid].copy()
        pname = pdata["product_name"].iloc[0]

        # time-based split: last 30 days as test
        cutoff = pdata["date"].max() - pd.Timedelta(days=30)
        train  = pdata[pdata["date"] <= cutoff]
        test   = pdata[pdata["date"] >  cutoff]

        if len(train) < 30 or len(test) < 5:
            print(f"  [WARN]  {pname}: not enough data, skipping.")
            continue

        X_train = train[FEATURE_COLS].values
        y_train = train[TARGET_COL].values
        X_test  = test[FEATURE_COLS].values
        y_test  = test[TARGET_COL].values

        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=3,
            n_jobs=-1,
            random_state=42,
        )
        rf.fit(X_train, y_train)

        y_pred = np.maximum(0, rf.predict(X_test))
        mae    = mean_absolute_error(y_test, y_pred)
        rmse   = np.sqrt(mean_squared_error(y_test, y_pred))
        r2     = r2_score(y_test, y_pred)

        print(f"  {pname:<22} MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.3f}")
        metrics_all[pid] = {"product_name": pname, "mae": round(mae,3), "rmse": round(rmse,3), "r2": round(r2,3)}
        models[pid] = rf

    # persist per-product models
    for pid, m in models.items():
        path = os.path.join(MODEL_DIR, f"product_{pid}_rf.pkl")
        with open(path, "wb") as f:
            pickle.dump(m, f)

    return models, metrics_all


def save_metrics(global_metrics, per_product_metrics, feature_cols):
    # Convert int64 keys to strings for JSON serialization
    serialized_per_product = {str(k): v for k, v in per_product_metrics.items()}
    meta = {
        "feature_cols":       feature_cols,
        "target_col":         TARGET_COL,
        "global_model":       global_metrics,
        "per_product_models": serialized_per_product,
    }
    path = os.path.join(MODEL_DIR, "model_metadata.json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n[INFO] Metadata saved -> {path}")


if __name__ == "__main__":
    print("[INFO] Loading data ...")
    df = load_data()
    print(f"   Rows: {len(df):,}  |  Products: {df['product_id'].nunique()}")

    print("[INFO] Engineering features ...")
    df = engineer_features(df)
    print(f"   After lag-drop: {len(df):,} rows")

    # ── global split ──────────────────────────────────────────────────────
    cutoff     = df["date"].max() - pd.Timedelta(days=30)
    train_df   = df[df["date"] <= cutoff]
    test_df    = df[df["date"] >  cutoff]
    product_names = df.set_index("product_id")["product_name"].to_dict()

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df[TARGET_COL].values
    X_test  = test_df[FEATURE_COLS].values
    y_test  = test_df[TARGET_COL].values

    global_model, global_metrics = train_global_model(
        X_train, y_train, X_test, y_test, product_names
    )

    per_product_models, per_product_metrics = train_per_product_models(df)

    # save feature list for inference
    with open(os.path.join(MODEL_DIR, "feature_cols.json"), "w") as f:
        json.dump(FEATURE_COLS, f)

    save_metrics(global_metrics, per_product_metrics, FEATURE_COLS)

    print("\n[SUCCESS] Training complete!  All models saved to forecasting/models/")
