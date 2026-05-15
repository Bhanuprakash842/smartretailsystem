"""
config.py
=========
Centralised configuration for the RAG multi-agent chatbot.
Uses Google Gemini (free tier) for LLM + embeddings and Pinecone for vector storage.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Google Gemini (FREE) ──────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_MODEL    = "gemini-2.0-flash"           # Confirmed available
GEMINI_EMBED_MODEL   = "models/gemini-embedding-001" # Confirmed available
EMBEDDING_DIMENSION  = 768                           # Truncated to match Pinecone index


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_CHAT_MODEL      = "llama-3.3-70b-versatile"  # or "openai/gpt-oss-120b"

# ── Pinecone ──────────────────────────────────────────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = "luxecart-agents"
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# Namespaces — one per agent
NS_PRODUCTS = "products"
NS_POLICIES = "policies"
NS_ANALYTICS = "analytics"

# ── RAG parameters ────────────────────────────────────────────────────────────
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
TOP_K = 5                      # chunks to retrieve per query

# ── Document directory ────────────────────────────────────────────────────────
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "documents")

# ── File → namespace mapping (which docs feed which agent) ────────────────────
DOC_NAMESPACE_MAP = {
    "product_catalog.txt":       NS_PRODUCTS,
    "shipping_policy.txt":       NS_POLICIES,
    "return_refund_policy.txt":  NS_POLICIES,
    "faq.txt":                   NS_POLICIES,
    "about_luxecart.txt":        NS_ANALYTICS,
    "inventory_management.txt":  NS_ANALYTICS,
    "platform_info.txt":         NS_ANALYTICS,
}
