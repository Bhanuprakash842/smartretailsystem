"""
generate_data.py
================
Generates synthetic historical sales order data for the LuxeCart retail system.
Produces two CSV files:
  - data/sales_orders.csv   : one row per order-item per day (raw transactions)
  - data/daily_demand.csv   : aggregated daily demand per product (ML-ready features)

Run:
    python forecasting/generate_data.py

FIX LOG:
  - Moved _get_season() definition ABOVE generate_daily_demand() which calls it.
    Previously Python raised NameError: name '_get_season' is not defined at runtime.
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import date, timedelta

# ── reproducibility ──────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── output directory ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── product catalogue (must match app.py seed data) ──────────────────────────
PRODUCTS = [
    {"id": 1,  "name": "Nova Headphones",    "category": "Electronics",  "price": 199.99,
     "base_demand": 6,  "seasonality": "winter"},
    {"id": 2,  "name": "Smart Watch Pro",    "category": "Wearables",    "price": 249.50,
     "base_demand": 4,  "seasonality": "new_year"},
    {"id": 3,  "name": "Minimalist Lamp",    "category": "Home Decor",   "price": 45.00,
     "base_demand": 8,  "seasonality": "spring"},
    {"id": 4,  "name": "Leather Crossbody",  "category": "Fashion",      "price": 129.00,
     "base_demand": 5,  "seasonality": "summer"},
    {"id": 5,  "name": "Ceramic Vase Set",   "category": "Home Decor",   "price": 68.00,
     "base_demand": 7,  "seasonality": "spring"},
    {"id": 6,  "name": "Wireless Earbuds",   "category": "Electronics",  "price": 159.99,
     "base_demand": 10, "seasonality": "winter"},
    {"id": 7,  "name": "Gaming Keyboard",    "category": "Electronics",  "price": 89.99,
     "base_demand": 9,  "seasonality": "autumn"},
    {"id": 8,  "name": "Yoga Mat Premium",   "category": "Sports",       "price": 34.99,
     "base_demand": 12, "seasonality": "summer"},
    {"id": 9,  "name": "Coffee Maker Deluxe","category": "Appliances",   "price": 149.99,
     "base_demand": 5,  "seasonality": "winter"},
    {"id": 10, "name": "Smart Speaker",      "category": "Electronics",  "price": 79.99,
     "base_demand": 8,  "seasonality": "new_year"},
]

# ── date range: history up to today ───────────────────────────────────────────
START_DATE = date(2024, 1, 1)
END_DATE   = date.today()
TOTAL_DAYS = (END_DATE - START_DATE).days + 1

# ── promotion schedule (flash sales) ─────────────────────────────────────────
PROMO_DATES = {
    # Diwali 2024
    date(2024, 11,  1): 0.40,
    date(2024, 11,  2): 0.35,
    date(2024, 11,  3): 0.30,
    # New Year 2025
    date(2025,  1,  1): 0.50,
    date(2025,  1,  2): 0.40,
    # Valentine's 2025
    date(2025,  2, 14): 0.25,
    # Diwali 2025
    date(2025, 10, 20): 0.45,
    date(2025, 10, 21): 0.38,
    date(2025, 10, 22): 0.30,
}


# ── FIX: _get_season defined BEFORE generate_daily_demand which calls it ─────
def _get_season(d: date) -> str:
    m = d.month
    if m in (12, 1, 2):  return "winter"
    if m in (3, 4, 5):   return "spring"
    if m in (6, 7, 8):   return "summer"
    return "autumn"


def seasonal_factor(d: date, seasonality: str) -> float:
    """Return a multiplier based on the product's peak season."""
    month = d.month
    if seasonality == "winter":
        return 1.0 + 0.6 * np.sin(np.pi * ((month - 10) % 12) / 5 + 0.1)
    elif seasonality == "summer":
        return 1.0 + 0.5 * np.sin(np.pi * (month - 4) / 5 + 0.1)
    elif seasonality == "spring":
        return 1.0 + 0.4 * np.sin(np.pi * (month - 2) / 4 + 0.1)
    elif seasonality == "new_year":
        return 1.3 if month in (1, 12) else 1.0
    return 1.0


def day_of_week_factor(d: date) -> float:
    """Weekend boost for retail."""
    return 1.4 if d.weekday() >= 5 else 1.0


def generate_daily_demand():
    """Generate one row per (date, product) with quantity_sold and features."""
    rows = []

    for day_offset in range(TOTAL_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)

        # global trend: +20% growth over 2 years
        trend = 1.0 + 0.20 * (day_offset / TOTAL_DAYS)

        promo_discount = PROMO_DATES.get(current_date, 0.0)
        promo_active   = 1 if promo_discount > 0 else 0
        dow_factor     = day_of_week_factor(current_date)

        for product in PRODUCTS:
            s_factor   = seasonal_factor(current_date, product["seasonality"])
            promo_lift = 1.0 + promo_discount * 3.0

            mu       = max(1, product["base_demand"] * trend * s_factor * dow_factor * promo_lift)
            qty_sold = int(np.random.poisson(mu))

            rows.append({
                "date":           current_date.isoformat(),
                "product_id":     product["id"],
                "product_name":   product["name"],
                "category":       product["category"],
                "price":          product["price"],
                "qty_sold":       qty_sold,
                "revenue":        round(qty_sold * product["price"] * (1 - promo_discount), 2),
                "day_of_week":    current_date.weekday(),
                "is_weekend":     int(current_date.weekday() >= 5),
                "month":          current_date.month,
                "year":           current_date.year,
                "week_of_year":   current_date.isocalendar()[1],
                "day_of_year":    current_date.timetuple().tm_yday,
                "is_promotion":   promo_active,
                "promo_discount": promo_discount,
                # FIX: _get_season is now defined above, no NameError
                "season":         _get_season(current_date),
            })

    return pd.DataFrame(rows)


def generate_sales_orders(daily_df: pd.DataFrame):
    """Explode daily demand into individual transaction rows."""
    order_rows = []
    order_id   = 10000

    for _, row in daily_df.iterrows():
        qty = row["qty_sold"]
        if qty == 0:
            continue
        num_orders = max(1, qty // 3)
        for _ in range(num_orders):
            qty_per_order = max(1, round(qty / num_orders + random.uniform(-0.5, 0.5)))
            order_rows.append({
                "order_id":    order_id,
                "order_date":  row["date"],
                "product_id":  row["product_id"],
                "product_name":row["product_name"],
                "category":    row["category"],
                "unit_price":  row["price"],
                "quantity":    qty_per_order,
                "discount":    row["promo_discount"],
                "total_price": round(qty_per_order * row["price"] * (1 - row["promo_discount"]), 2),
                "is_promotion":row["is_promotion"],
            })
            order_id += 1

    return pd.DataFrame(order_rows)


if __name__ == "__main__":
    print("[INFO] Generating daily demand data ...")
    daily_df   = generate_daily_demand()
    daily_path = os.path.join(DATA_DIR, "daily_demand.csv")
    daily_df.to_csv(daily_path, index=False)
    print(f"[SUCCESS] daily_demand.csv  →  {len(daily_df):,} rows  →  {daily_path}")

    print("[INFO] Generating raw sales orders ...")
    orders_df  = generate_sales_orders(daily_df)
    orders_path = os.path.join(DATA_DIR, "sales_orders.csv")
    orders_df.to_csv(orders_path, index=False)
    print(f"[SUCCESS] sales_orders.csv  →  {len(orders_df):,} rows  →  {orders_path}")

    print("\n[STATS] Quick stats:")
    print(daily_df.groupby("product_name")["qty_sold"].agg(["sum", "mean", "max"]).round(1).to_string())