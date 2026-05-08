"""
analytics_routes.py
===================
Enhanced analytics API routes for comprehensive demand forecasting insights.

FIX LOG:
  - Removed `from forecasting.analytics import PRODUCT_CATALOG` — PRODUCT_CATALOG
    lives in predict.py, not analytics.py. This was causing an ImportError that
    silently broke all /analytics/weekly/all and /analytics/seasonal/all routes.
  - All routes now import PRODUCT_CATALOG from forecasting.predict consistently.
  - Added try/except around CSV-dependent calls so a missing data file returns
    a clear 503 instead of an unhandled 500.
"""

import os
from datetime import date, timedelta
from flask import Blueprint, jsonify, request, session

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def _require_admin():
    return session.get("role") == "admin"


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_catalog():
    """Return PRODUCT_CATALOG from the single source of truth."""
    from forecasting.predict import PRODUCT_CATALOG
    return PRODUCT_CATALOG


# ── routes ────────────────────────────────────────────────────────────────────

@analytics_bp.route("/product/<int:product_id>", methods=["GET"])
def product_analytics(product_id):
    """GET /analytics/product/<id> — comprehensive product analytics."""
    try:
        days = int(request.args.get("days", 30))
        from forecasting.analytics import get_product_analytics
        return jsonify(get_product_analytics(product_id, days))
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/products", methods=["GET"])
def all_products_analytics():
    """GET /analytics/products — analytics for all products."""
    try:
        days    = int(request.args.get("days", 30))
        catalog = _get_catalog()
        from forecasting.analytics import get_product_analytics
        all_analytics = {pid: get_product_analytics(pid, days) for pid in catalog}
        return jsonify(all_analytics)
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/weekly/<int:product_id>", methods=["GET"])
def weekly_analytics(product_id):
    """GET /analytics/weekly/<id> — week-wise analytics."""
    try:
        weeks = int(request.args.get("weeks", 12))
        from forecasting.analytics import get_weekly_analytics
        return jsonify(get_weekly_analytics(product_id, weeks))
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/weekly/all", methods=["GET"])
def all_weekly_analytics():
    """GET /analytics/weekly/all — weekly analytics for all products."""
    try:
        weeks   = int(request.args.get("weeks", 12))
        catalog = _get_catalog()                         # FIX: was wrongly from analytics
        from forecasting.analytics import get_weekly_analytics
        all_weekly = {pid: get_weekly_analytics(pid, weeks) for pid in catalog}
        return jsonify(all_weekly)
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/daily/<int:product_id>", methods=["GET"])
def daily_analytics(product_id):
    """GET /analytics/daily/<id> — day-wise analytics."""
    try:
        days = int(request.args.get("days", 30))
        from forecasting.analytics import get_daily_analytics
        return jsonify(get_daily_analytics(product_id, days))
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/daily/all", methods=["GET"])
def all_daily_analytics():
    """GET /analytics/daily/all — daily analytics for all products."""
    try:
        days    = int(request.args.get("days", 30))
        catalog = _get_catalog()                         # FIX: was wrongly from analytics
        from forecasting.analytics import get_daily_analytics
        all_daily = {pid: get_daily_analytics(pid, days) for pid in catalog}
        return jsonify(all_daily)
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/categories", methods=["GET"])
def category_performance():
    """GET /analytics/categories — category-wise performance."""
    try:
        from forecasting.analytics import get_category_performance
        return jsonify(get_category_performance())
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/seasonal/<int:product_id>", methods=["GET"])
def seasonal_patterns(product_id):
    """GET /analytics/seasonal/<id> — seasonal patterns for a product."""
    try:
        from forecasting.analytics import get_seasonal_patterns
        return jsonify(get_seasonal_patterns(product_id))
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/seasonal/all", methods=["GET"])
def all_seasonal_patterns():
    """GET /analytics/seasonal/all — seasonal patterns for all products."""
    try:
        catalog = _get_catalog()                         # FIX: was wrongly from analytics
        from forecasting.analytics import get_seasonal_patterns
        all_patterns = {pid: get_seasonal_patterns(pid) for pid in catalog}
        return jsonify(all_patterns)
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/top-performers", methods=["GET"])
def top_performers():
    """GET /analytics/top-performers — top performing products."""
    try:
        metric = request.args.get("metric", "revenue")
        limit  = int(request.args.get("limit", 10))
        from forecasting.analytics import get_top_performers
        return jsonify(get_top_performers(metric, limit))
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/forecast-summary/<int:product_id>", methods=["GET"])
def forecast_summary(product_id):
    """GET /analytics/forecast-summary/<id> — forecast summary."""
    try:
        days = int(request.args.get("days", 30))
        from forecasting.analytics import get_demand_forecast_summary
        return jsonify(get_demand_forecast_summary(product_id, days))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@analytics_bp.route("/dashboard-data", methods=["GET"])
def dashboard_data():
    """GET /analytics/dashboard-data — comprehensive dashboard data."""
    try:
        from forecasting.analytics import (
            get_category_performance,
            get_weekly_analytics,
            get_top_performers,
        )
        from forecasting.predict import PRODUCT_CATALOG, predict_all_products

        today              = date.today()
        todays_predictions = predict_all_products(today)
        categories         = get_category_performance()
        top_revenue        = get_top_performers("revenue", 5)
        top_quantity       = get_top_performers("quantity", 5)

        weekly_trends = {pid: get_weekly_analytics(pid, 8) for pid in PRODUCT_CATALOG}

        return jsonify({
            "todays_predictions": todays_predictions,
            "categories":         categories,
            "top_revenue":        top_revenue,
            "top_quantity":       top_quantity,
            "weekly_trends":      weekly_trends,
            "products":           PRODUCT_CATALOG,
        })
    except FileNotFoundError:
        return jsonify({"error": "Data file not found. Run generate_data.py first."}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 400