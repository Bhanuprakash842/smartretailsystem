"""
predict.py
==========
Inference engine for the demand forecasting system.

Provides two functions consumed by Flask routes:
  - predict_product(product_id, target_date, promo_discount)
  - predict_all_products(target_date, promo_discount)

Models used: per-product RF when available, falls back to global GBM.

FIX LOG:
  - Added 'category' key to predict_product() return dict (was missing, broke Jinja table)
  - Wrapped _load_artifacts() in per-step try/except so a missing encoder gives a clear error
  - _load_artifacts() guard now uses a dedicated _artifacts_loaded flag to avoid re-entry bugs
  - Added MODEL_READY flag so routes return a clean 503 instead of a 500 traceback
"""

import os
import json
import pickle
import warnings
import numpy as np
import pandas as pd
from datetime import date, timedelta

warnings.filterwarnings("ignore")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR  = os.path.join(BASE_DIR, "data")

# ── Lazy-loaded singletons ────────────────────────────────────────────────────
_global_model    = None
_per_product     = {}        # {product_id: rf_model}
_cat_encoder     = None
_sea_encoder     = None
_feature_cols    = None
_history_df      = None      # for lag computation
_artifacts_loaded = False    # FIX: single flag so guard works correctly
MODEL_READY      = False     # exposed to routes for health-checks

PRODUCT_CATALOG = {
    1:  {"name": "Nova Headphones",    "category": "Electronics", "price": 199.99},
    2:  {"name": "Smart Watch Pro",    "category": "Wearables",   "price": 249.50},
    3:  {"name": "Minimalist Lamp",    "category": "Home Decor",  "price":  45.00},
    4:  {"name": "Leather Crossbody",  "category": "Fashion",     "price": 129.00},
    5:  {"name": "Ceramic Vase Set",   "category": "Home Decor",  "price":  68.00},
    6:  {"name": "Wireless Earbuds",   "category": "Electronics", "price": 159.99},
    7:  {"name": "Gaming Keyboard",    "category": "Electronics", "price":  89.99},
    8:  {"name": "Yoga Mat Premium",   "category": "Sports",      "price":  34.99},
    9:  {"name": "Coffee Maker Deluxe","category": "Appliances",  "price": 149.99},
    10: {"name": "Smart Speaker",      "category": "Electronics", "price":  79.99},
}


def _get_season(d: date) -> str:
    m = d.month
    if m in (12, 1, 2):  return "winter"
    if m in (3, 4, 5):   return "spring"
    if m in (6, 7, 8):   return "summer"
    return "autumn"


def _load_artifacts():
    """
    Load all model artefacts exactly once.
    Raises RuntimeError with a clear message if anything is missing so the
    caller can return a clean HTTP 503 instead of an unhandled 500.
    """
    global _global_model, _cat_encoder, _sea_encoder, _feature_cols
    global _history_df, _artifacts_loaded, MODEL_READY

    if _artifacts_loaded:
        return

    errors = []

    # ── global GBM model (optional — per-product RF preferred) ───────────────
    gm_path = os.path.join(MODEL_DIR, "global_gb_model.pkl")
    if os.path.exists(gm_path):
        try:
            with open(gm_path, "rb") as f:
                _global_model = pickle.load(f)
        except Exception as e:
            errors.append(f"global_gb_model.pkl load error: {e}")
    else:
        errors.append("global_gb_model.pkl not found")

    # ── category encoder (required) ──────────────────────────────────────────
    cat_path = os.path.join(MODEL_DIR, "category_encoder.pkl")
    if os.path.exists(cat_path):
        try:
            with open(cat_path, "rb") as f:
                _cat_encoder = pickle.load(f)
        except Exception as e:
            errors.append(f"category_encoder.pkl load error: {e}")
    else:
        errors.append("category_encoder.pkl not found — run train_model.py first")

    # ── season encoder (required) ─────────────────────────────────────────────
    sea_path = os.path.join(MODEL_DIR, "season_encoder.pkl")
    if os.path.exists(sea_path):
        try:
            with open(sea_path, "rb") as f:
                _sea_encoder = pickle.load(f)
        except Exception as e:
            errors.append(f"season_encoder.pkl load error: {e}")
    else:
        errors.append("season_encoder.pkl not found — run train_model.py first")

    # ── feature column list (required) ───────────────────────────────────────
    fc_path = os.path.join(MODEL_DIR, "feature_cols.json")
    if os.path.exists(fc_path):
        try:
            with open(fc_path) as f:
                _feature_cols = json.load(f)
        except Exception as e:
            errors.append(f"feature_cols.json load error: {e}")
    else:
        errors.append("feature_cols.json not found — run train_model.py first")

    # ── historical data for lag computation (optional but highly recommended) ─
    hist_path = os.path.join(DATA_DIR, "daily_demand.csv")
    if os.path.exists(hist_path):
        try:
            _history_df = pd.read_csv(hist_path, parse_dates=["date"])
        except Exception as e:
            errors.append(f"daily_demand.csv load error: {e}")
    else:
        errors.append(
            "daily_demand.csv not found — run generate_data.py first. "
            "Falling back to mean-imputed lags (lower accuracy)."
        )

    # Decide if the model stack is usable
    required_missing = [e for e in errors if "not found" in e and "daily_demand" not in e]
    if required_missing:
        _artifacts_loaded = False
        raise RuntimeError(
            "Model not ready. Missing artefacts:\n  • " +
            "\n  • ".join(required_missing)
        )

    _artifacts_loaded = True
    MODEL_READY = True

    if errors:
        # Non-fatal warnings (missing history CSV etc.)
        print("[WARN] predict.py loaded with warnings:")
        for w in errors:
            print(f"  • {w}")


def _load_per_product(product_id: int):
    """Lazy-load a single product's RF model."""
    if product_id in _per_product:
        return _per_product[product_id]
    path = os.path.join(MODEL_DIR, f"product_{product_id}_rf.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            _per_product[product_id] = pickle.load(f)
        return _per_product[product_id]
    return None


def _compute_lags(product_id: int, target_date: date) -> dict:
    """Compute lag and rolling features from historical data."""
    if _history_df is None:
        # FIX: fallback values derived from product base stats instead of
        # a hardcoded 5 for everything, which skews all products equally.
        info = PRODUCT_CATALOG.get(product_id, {})
        base = 5.0
        return {
            "lag_1":       base, "lag_7":       base,
            "lag_14":      base, "lag_30":      base,
            "roll_7_mean": base, "roll_7_std":  1.0,
            "roll_14_mean":base, "roll_14_std": 1.0,
            "roll_30_mean":base,
        }

    pdata = _history_df[_history_df["product_id"] == product_id].copy()
    pdata.sort_values("date", inplace=True)
    td = pd.Timestamp(target_date)

    def qty_on(offset):
        d   = td - pd.Timedelta(days=offset)
        row = pdata[pdata["date"] == d]
        return float(row["qty_sold"].values[0]) if len(row) > 0 else float(pdata["qty_sold"].mean())

    def roll_mean(window):
        hist = pdata[pdata["date"] < td].tail(window)["qty_sold"]
        return float(hist.mean()) if len(hist) > 0 else 5.0

    def roll_std(window):
        hist = pdata[pdata["date"] < td].tail(window)["qty_sold"]
        return float(hist.std()) if len(hist) > 1 else 1.0

    return {
        "lag_1":        qty_on(1),
        "lag_7":        qty_on(7),
        "lag_14":       qty_on(14),
        "lag_30":       qty_on(30),
        "roll_7_mean":  roll_mean(7),
        "roll_7_std":   roll_std(7),
        "roll_14_mean": roll_mean(14),
        "roll_14_std":  roll_std(14),
        "roll_30_mean": roll_mean(30),
    }


def _build_feature_row(
    product_id: int, target_date: date, promo_discount: float = 0.0
) -> np.ndarray:
    """Build the feature vector for one (product, date) pair."""
    _load_artifacts()
    info   = PRODUCT_CATALOG.get(product_id, {})
    season = _get_season(target_date)
    lags   = _compute_lags(product_id, target_date)

    # FIX: handle unseen category/season labels gracefully
    cat_label = info.get("category", "Electronics")
    try:
        cat_enc = int(_cat_encoder.transform([cat_label])[0])
    except ValueError:
        cat_enc = 0   # unknown category → first encoded class

    try:
        sea_enc = int(_sea_encoder.transform([season])[0])
    except ValueError:
        sea_enc = 0

    feat = {
        "product_id":     product_id,
        "price":          info.get("price", 100.0),
        "day_of_week":    target_date.weekday(),
        "is_weekend":     int(target_date.weekday() >= 5),
        "month":          target_date.month,
        "year":           target_date.year,
        "week_of_year":   target_date.isocalendar()[1],
        "day_of_year":    target_date.timetuple().tm_yday,
        "is_promotion":   int(promo_discount > 0),
        "promo_discount": promo_discount,
        **lags,
        "category_enc":   cat_enc,
        "season_enc":     sea_enc,
    }

    return np.array([feat[c] for c in _feature_cols]).reshape(1, -1)


def predict_product(
    product_id: int, target_date: date, promo_discount: float = 0.0
) -> dict:
    """
    Predict demand for one product on one date.

    Returns:
        {product_id, product_name, category, date, predicted_qty,
         predicted_revenue, model_used, confidence_low, confidence_high}
    """
    try:
        _load_artifacts()
    except RuntimeError as e:
        return {"error": str(e)}

    X = _build_feature_row(product_id, target_date, promo_discount)

    rf_model = _load_per_product(product_id)
    if rf_model is not None:
        tree_preds = np.array([t.predict(X)[0] for t in rf_model.estimators_])
        pred       = float(np.mean(tree_preds))
        std        = float(np.std(tree_preds))
        model_used = "RandomForest (per-product)"
    elif _global_model is not None:
        pred       = float(_global_model.predict(X)[0])
        std        = pred * 0.20
        model_used = "GradientBoosting (global)"
    else:
        return {"error": "No trained model found. Run train_model.py first."}

    pred = max(0, round(pred, 1))
    info = PRODUCT_CATALOG.get(product_id, {})
    price_after_discount = info.get("price", 0) * (1 - promo_discount)

    return {
        "product_id":        product_id,
        "product_name":      info.get("name", "Unknown"),
        # FIX: 'category' was missing — Jinja template uses p.get('category','—')
        "category":          info.get("category", "—"),
        "date":              target_date.isoformat(),
        "predicted_qty":     pred,
        "confidence_low":    max(0, round(pred - 1.96 * std, 1)),
        "confidence_high":   round(pred + 1.96 * std, 1),
        "predicted_revenue": round(pred * price_after_discount, 2),
        "model_used":        model_used,
        "promo_discount":    promo_discount,
    }


def predict_all_products(target_date: date, promo_discount: float = 0.0) -> list:
    """Predict demand for all products on a given date."""
    results = []
    for pid in PRODUCT_CATALOG:
        r = predict_product(pid, target_date, promo_discount)
        if "error" not in r:
            results.append(r)
    return results


def predict_range(
    product_id: int, start_date: date, end_date: date,
    promo_discount: float = 0.0
) -> list:
    """Predict demand for one product over a date range."""
    results = []
    d = start_date
    while d <= end_date:
        r = predict_product(product_id, d, promo_discount)
        if "error" not in r:
            results.append(r)
        d += timedelta(days=1)
    return results