"""
chat_routes.py
==============
Flask Blueprint for the RAG-based multi-agent QA chatbot.

Routes:
  POST /chat/api/ask       — Send a question → LangGraph multi-agent pipeline
  POST /chat/api/ingest    — (Admin) Re-ingest documents + products into Pinecone
  GET  /chat/api/status    — Health-check / readiness of the RAG system
"""

import os
import traceback
from flask import Blueprint, request, jsonify, session

from chatbot.config import GEMINI_API_KEY, PINECONE_API_KEY

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rag_available() -> bool:
    """Check whether the required API keys are configured."""
    return bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your-gemini-api-key-here" and \
           bool(PINECONE_API_KEY) and PINECONE_API_KEY != "your-pinecone-api-key-here"


def _get_products_from_db() -> list:
    """Fetch all products from the database as dicts."""
    from models import db, ProductModel
    products = ProductModel.query.all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "price": p.price,
            "category": p.category or "",
            "stock": p.stock,
        }
        for p in products
    ]


# ── Status ────────────────────────────────────────────────────────────────────

@chat_bp.route("/api/status", methods=["GET"])
def chat_status():
    """Return whether the RAG system is ready."""
    keys_ok = _rag_available()
    return jsonify({
        "rag_ready": keys_ok,
        "gemini_key": bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your-gemini-api-key-here",
        "pinecone_key": bool(PINECONE_API_KEY) and PINECONE_API_KEY != "your-pinecone-api-key-here",
        "architecture": "LangGraph Multi-Agent (3 Agents)",
        "agents": [
            {"name": "Product Specialist", "emoji": "🛍️", "namespace": "products"},
            {"name": "Customer Support", "emoji": "🎧", "namespace": "policies"},
            {"name": "Business Intelligence", "emoji": "📊", "namespace": "analytics"},
        ],
        "llm": "Google Gemini 2.0 Flash (free)",
        "embeddings": "Google text-embedding-004 (free)",
        "vector_db": "Pinecone",
        "message": "RAG system is ready" if keys_ok else "Missing API keys — configure GEMINI_API_KEY and PINECONE_API_KEY in .env",
    })


# ── Ask (Main endpoint) ──────────────────────────────────────────────────────

@chat_bp.route("/api/ask", methods=["POST"])
def chat_ask():
    """
    POST { "question": "..." }
    → Runs LangGraph multi-agent pipeline
    → Returns { "answer", "agent_type", "agent_label", "sources", ... }
    """
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Please provide a question."}), 400

    if not _rag_available():
        return jsonify({
            "error": "RAG system is not configured. Please add GEMINI_API_KEY and PINECONE_API_KEY to your .env file. Get a free Gemini API key at https://aistudio.google.com/apikey",
        }), 503

    try:
        from chatbot.agents import run_agent
        result = run_agent(question)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"RAG processing error: {str(e)}",
            "answer": "I'm sorry, I encountered an error processing your question. Please try again or contact support.",
        }), 500


# ── Ingest ────────────────────────────────────────────────────────────────────

@chat_bp.route("/api/ingest", methods=["POST"])
def chat_ingest():
    """
    (Admin only) Trigger re-ingestion of all documents + products into Pinecone.
    Chunks are split across namespaces: products, policies, analytics.
    """
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required."}), 403

    if not _rag_available():
        return jsonify({"error": "RAG system is not configured. Add GEMINI_API_KEY and PINECONE_API_KEY to .env"}), 503

    try:
        from chatbot.rag_engine import ingest_documents
        products = _get_products_from_db()
        result = ingest_documents(products=products)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
