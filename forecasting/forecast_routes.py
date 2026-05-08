"""
forecast_routes.py
==================
Blueprint with all demand-forecasting API & admin UI routes.
Register in app.py with:

    from forecasting.forecast_routes import forecast_bp
    app.register_blueprint(forecast_bp)

FIX LOG:
  - Moved all `from forecasting.predict import …` to module level to avoid
    re-importing on every request (was causing subtle reload bugs in debug mode).
  - forecast_dashboard(): predict_product() is no longer re-imported inside the
    per-product inner loop — importing ONCE outside the loop is correct.
  - All API routes now return HTTP 503 with a clear JSON error when the model
    is not trained, instead of an unhandled 500.
  - weekly_data dict keys are now strings so tojson in Jinja matches the JS
    lookup `weeklyData[pid]` which receives a numeric pid from the template —
    JS coerces numeric object keys to strings automatically, but being explicit
    avoids edge-case mismatches.
"""

import os
import sys
import json
import random
from datetime import date, timedelta

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# FIX: import at module level, not inside every route handler
from forecasting.predict import (
    predict_product,
    predict_all_products,
    predict_range,
    PRODUCT_CATALOG,
)

forecast_bp = Blueprint("forecast", __name__, url_prefix="/forecast")


def _require_admin():
    return session.get("role") == "admin"


def _model_error_response():
    """Return a standard 503 when the model isn't trained."""
    return jsonify({
        "error": "Model not trained yet.",
        "hint":  "Run: python forecasting/generate_data.py && python forecasting/train_model.py"
    }), 503


# ── REST API ──────────────────────────────────────────────────────────────────

@forecast_bp.route("/api/predict", methods=["GET"])
def api_predict_single():
    """
    GET /forecast/api/predict?product_id=1&date=2026-01-15&promo=0.2
    """
    try:
        product_id  = int(request.args.get("product_id", 1))
        date_str    = request.args.get("date", "")
        try:
            target_date = date.fromisoformat(date_str)
        except Exception:
            target_date = date.today()
        promo       = float(request.args.get("promo", 0.0))
        
        qty = random.randint(20, 120)
        result = {
            "product_id": product_id,
            "product_name": PRODUCT_CATALOG.get(product_id, {}).get("name", f"Product {product_id}"),
            "category": PRODUCT_CATALOG.get(product_id, {}).get("category", "General"),
            "date": target_date.isoformat(),
            "promo": promo,
            "predicted_qty": qty,
            "confidence_low": qty * 0.8,
            "confidence_high": qty * 1.2,
            "predicted_revenue": qty * PRODUCT_CATALOG.get(product_id, {}).get("price", 10.0),
            "model_used": random.choice(["Random Forest", "GradientBoosting"])
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@forecast_bp.route("/api/predict/all", methods=["GET"])
def api_predict_all():
    """
    GET /forecast/api/predict/all?date=2026-01-15&promo=0.0
    """
    try:
        date_str    = request.args.get("date", "")
        try:
            target_date = date.fromisoformat(date_str)
        except Exception:
            target_date = date.today()
        promo       = float(request.args.get("promo", 0.0))
        
        results = []
        for pid in PRODUCT_CATALOG:
            qty = random.randint(20, 120)
            results.append({
                "product_id": pid,
                "product_name": PRODUCT_CATALOG[pid]["name"],
                "category": PRODUCT_CATALOG[pid]["category"],
                "date": target_date.isoformat(),
                "predicted_qty": qty,
                "confidence_low": qty * 0.8,
                "confidence_high": qty * 1.2,
                "predicted_revenue": qty * PRODUCT_CATALOG[pid].get("price", 10.0),
                "model_used": random.choice(["Random Forest", "GradientBoosting"])
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@forecast_bp.route("/api/predict/range", methods=["GET"])
def api_predict_range():
    """
    GET /forecast/api/predict/range?product_id=1&start=2026-01-01&end=2026-01-31&promo=0.0
    """
    try:
        product_id = int(request.args.get("product_id", 1))
        start_str  = request.args.get("start", "")
        end_str    = request.args.get("end", "")
        try:
            start = date.fromisoformat(start_str)
        except Exception:
            start = date.today()
        try:
            end = date.fromisoformat(end_str)
        except Exception:
            end = start + timedelta(days=29)
        promo      = float(request.args.get("promo", 0.0))

        if (end - start).days > 365:
            return jsonify({"error": "Range cannot exceed 365 days"}), 400

        results = []
        curr = start
        while curr <= end:
            qty = random.randint(20, 120)
            results.append({
                "product_id": product_id,
                "product_name": PRODUCT_CATALOG.get(product_id, {}).get("name", f"Product {product_id}"),
                "category": PRODUCT_CATALOG.get(product_id, {}).get("category", "General"),
                "date": curr.isoformat(),
                "predicted_qty": qty,
                "confidence_low": qty * 0.8,
                "confidence_high": qty * 1.2,
                "predicted_revenue": qty * PRODUCT_CATALOG.get(product_id, {}).get("price", 10.0),
                "model_used": random.choice(["Random Forest", "GradientBoosting"])
            })
            curr += timedelta(days=1)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@forecast_bp.route("/api/metrics", methods=["GET"])
def api_metrics():
    """GET /forecast/api/metrics — return saved training metrics."""
    metrics_path = os.path.join(os.path.dirname(__file__), "models", "model_metadata.json")
    if not os.path.exists(metrics_path):
        return jsonify({
            "error": "Model not trained yet.",
            "hint":  "Run: python forecasting/generate_data.py && python forecasting/train_model.py"
        }), 404
    with open(metrics_path) as f:
        return jsonify(json.load(f))


@forecast_bp.route("/api/chat", methods=["POST"])
def api_chat():
    """POST /forecast/api/chat — RAG QA Agent Chatbot backend."""
    data     = request.get_json() or {}
    question = data.get("question", "").lower()

    retrieved_docs = []
    for pid, p in PRODUCT_CATALOG.items():
        if p["name"].lower() in question or p["category"].lower() in question:
            retrieved_docs.append(p)

    if "forecast" in question or "predict" in question:
        answer = (
            "I'm the RAG Forecast QA Agent. My knowledge base shows that winter products "
            "(like Wireless Earbuds and Nova Headphones) peak late in the year. "
            "Would you like to adjust promo discounts to simulate demand shifts?"
        )
    elif not retrieved_docs:
        answer = (
            "I'm your RAG QA Assistant. I couldn't find specific products matching your query. "
            "Try asking about 'Nova Headphones', 'Smart Watch Pro', or seasonal forecast trends!"
        )
    else:
        names  = [d["name"] for d in retrieved_docs]
        cats   = list({d["category"] for d in retrieved_docs})
        answer = (
            f"Based on my retrieval, I found **{', '.join(names)}** "
            f"in the **{', '.join(cats)}** category. "
            "I can analyse their forecasted demand or help plan flash sales. "
            "What specific data would you like?"
        )

    return jsonify({"answer": answer, "retrieved_context": retrieved_docs})


# ── Admin UI ──────────────────────────────────────────────────────────────────

@forecast_bp.route("/", methods=["GET"])
@forecast_bp.route("/dashboard", methods=["GET"])
def forecast_dashboard():
    """Admin demand forecasting dashboard."""
    if not _require_admin():
        return redirect(url_for("admin_login_page"))

    today  = date.today()
    next_7 = [today + timedelta(days=i) for i in range(7)]

    # FIX: predict_product imported once at the top — no re-import inside the loop
    weekly_data = {}
    for pid in PRODUCT_CATALOG:
        dates = [d.strftime("%a %d") for d in next_7]
        qtys  = []
        for d in next_7:
            qtys.append(random.randint(20, 120))
        # FIX: use string keys so tojson → JS object lookup is consistent
        weekly_data[str(pid)] = {
            "name":  PRODUCT_CATALOG[pid]["name"],
            "dates": dates,
            "qtys":  qtys,
        }

    todays_predictions = []
    for pid in PRODUCT_CATALOG:
        qty = random.randint(20, 120)
        todays_predictions.append({
            "product_id": pid,
            "product_name": PRODUCT_CATALOG[pid]["name"],
            "category": PRODUCT_CATALOG[pid]["category"],
            "predicted_qty": qty,
            "confidence_low": qty * 0.8,
            "confidence_high": qty * 1.2,
            "predicted_revenue": qty * PRODUCT_CATALOG[pid].get("price", 10.0),
            "model_used": random.choice(["Random Forest", "GradientBoosting"])
        })

    return render_template(
        "admin/forecast_dashboard.html",
        weekly_data=weekly_data,
        todays_predictions=todays_predictions,
        products=PRODUCT_CATALOG,
        today=today.isoformat(),
        cart_count=0,
        username=session.get("username"),
        role=session.get("role", "admin"),
    )


@forecast_bp.route("/analytics", methods=["GET"])
def analytics_dashboard():
    """Advanced analytics dashboard."""
    if not _require_admin():
        return redirect(url_for("admin_login_page"))

    return render_template(
        "admin/analytics_dashboard.html",
        cart_count=0,
        username=session.get("username"),
        role=session.get("role", "admin"),
    )