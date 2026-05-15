"""
agents.py
=========
LangGraph multi-agent RAG system with THREE specialised agents and a
Supervisor/Router for the LuxeCart e-commerce platform.

Agents:
  1. 🛍️  Product Specialist   — products, specs, pricing, recommendations
  2. 🎧  Customer Support      — shipping, returns, refunds, FAQs
  3. 📊  Business Intelligence — forecasting, analytics, inventory insights

Off-topic / out-of-domain queries are politely declined.

Technology:
  - LangGraph StateGraph for orchestration
  - Google Gemini 2.0 Flash (free) for LLM
  - Pinecone + Gemini Embeddings for RAG retrieval

Usage:
  from chatbot.agents import run_agent
  result = run_agent("Tell me about Nova Headphones")
"""

from __future__ import annotations

import os
import json
import traceback
from typing import TypedDict, Literal, List, Dict, Any, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END

from chatbot.config import (
    GEMINI_API_KEY, GEMINI_CHAT_MODEL,
    GROQ_API_KEY, GROQ_CHAT_MODEL,
    NS_PRODUCTS, NS_POLICIES, NS_ANALYTICS, TOP_K,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    """Shared state flowing through the LangGraph."""
    query: str                          # original user question
    agent_type: str                     # selected: product | support | analytics
    context_chunks: List[Dict]          # retrieved RAG context
    agent_reasoning: str                # which agent was chosen and why
    answer: str                         # final formatted answer
    sources: List[str]                  # source document names
    error: Optional[str]               # error message if any


# ═══════════════════════════════════════════════════════════════════════════════
#  GEMINI LLM HELPER
# ═══════════════════════════════════════════════════════════════════════════════

# ── Providers ──
_gemini_client = None
_groq_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_client = genai.GenerativeModel(GEMINI_CHAT_MODEL)
    return _gemini_client

def _get_groq():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        except ImportError:
            print("[LLM Debug] groq package not installed — run: pip install groq")
    return _groq_client

def _llm(prompt: str) -> str:
    """Send a prompt to LLM with fallback support (Gemini -> Groq)."""
    # 1. Try Gemini
    gemini = _get_gemini()
    if gemini:
        try:
            response = gemini.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[LLM Error] Gemini failed: {e}")
    else:
        print("[LLM Debug] Gemini client not initialized (check GEMINI_API_KEY)")
    
    # 2. Try Groq
    groq = _get_groq()
    if groq:
        try:
            response = groq.chat.completions.create(
                model=GROQ_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLM Error] Groq failed: {e}")
    else:
        print("[LLM Debug] Groq client not initialized (check GROQ_API_KEY)")
            
    return "Error: All LLM providers failed. Please check your API keys in the .env file and restart the server."


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 1: ROUTER / SUPERVISOR
# ═══════════════════════════════════════════════════════════════════════════════

ROUTER_PROMPT = """You are a strict query classifier for the LuxeCart e-commerce platform.
Your job is to determine if the user's question is related to the LuxeCart retail domain.

Classify the user's question into EXACTLY ONE of these categories:
- "product"    → Questions about products, features, specs, pricing, availability, comparisons, recommendations
- "support"    → Questions about shipping, returns, refunds, payment, orders, tracking, account, FAQs, policies, how-to
- "analytics"  → Questions about demand forecasting, sales trends, inventory, analytics, business insights, company info
- "off_topic"  → ANYTHING that does NOT relate to LuxeCart products, customer support, or business analytics. This includes: general knowledge, math, science, coding, history, geography, jokes, politics, weather, personal advice, other companies/brands, etc.

IMPORTANT: Greetings like "hi", "hello", "hey" should be classified as "off_topic".
If in doubt, classify as "off_topic".

User question: "{query}"

Respond with ONLY a JSON object (no markdown, no code fences):
{{"category": "product|support|analytics|off_topic", "reasoning": "one sentence explanation"}}
"""


def router_node(state: AgentState) -> dict:
    """Classify the query and route to the appropriate agent."""
    query = state["query"]

    try:
        raw = _llm(ROUTER_PROMPT.format(query=query))
        # Clean any markdown fences
        raw = raw.strip().strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        result = json.loads(raw)
        category = result.get("category", "off_topic")
        reasoning = result.get("reasoning", "")
    except Exception:
        # Fallback classification via keyword matching
        q = query.lower()
        if any(w in q for w in ["product", "price", "buy", "headphone", "watch", "lamp",
                                 "earbuds", "vase", "crossbody", "bag", "recommend",
                                 "compare", "stock", "available", "cost", "feature"]):
            category = "product"
            reasoning = "Keyword match: product-related terms detected"
        elif any(w in q for w in ["ship", "return", "refund", "order", "track",
                                   "payment", "cancel", "delivery", "policy", "faq"]):
            category = "support"
            reasoning = "Keyword match: support-related terms detected"
        elif any(w in q for w in ["forecast", "demand", "trend", "analytics", "sales",
                                   "inventory", "insight", "company", "about", "revenue",
                                   "luxecart", "who are you"]):
            category = "analytics"
            reasoning = "Keyword match: analytics-related terms detected"
        else:
            category = "off_topic"
            reasoning = "No domain-specific keywords found — off-topic"

    return {
        "agent_type": category,
        "agent_reasoning": f"[Router] → {category}: {reasoning}",
    }


def _route_to_agent(state: AgentState) -> str:
    """Conditional edge function: return the next node name."""
    return state["agent_type"]


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 2a: PRODUCT SPECIALIST AGENT 🛍️
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCT_SYSTEM = """You are the **LuxeCart Product Specialist** — an expert on all products sold on LuxeCart.

Your expertise:
• Complete product catalog knowledge (features, specs, materials, dimensions)
• Pricing and availability information
• Product comparisons and personalised recommendations
• Warranty and care instructions
• Compatibility details

Rules:
1. Use the retrieved product context below to answer. 
2. If the context doesn't contain the answer, you may use your internal knowledge about common electronics, fashion, and decor, but state that you are providing general information.
3. Always mention the exact price with ₹ sign when discussing a product from our catalog.
4. If comparing products, use a clear format (bullet points or table-style).
5. Be enthusiastic but professional — you love these products!
6. Use markdown formatting for readability.
"""


def product_agent_node(state: AgentState) -> dict:
    """Product Specialist Agent — retrieves from products namespace and answers."""
    from chatbot.rag_engine import retrieve

    query = state["query"]
    chunks = retrieve(query, NS_PRODUCTS, TOP_K)

    if not chunks:
        return {
            "context_chunks": [],
            "answer": "I couldn't find specific product information for your query. We carry products in Electronics, Wearables, Fashion, and Home Decor. Could you try asking about a specific product like **Nova Headphones** or **Smart Watch Pro**?",
            "sources": [],
        }

    context = "\n\n---\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks])
    prompt = f"{PRODUCT_SYSTEM}\n\n## Retrieved Product Context\n{context}\n\n## Customer Question\n{query}\n\n## Your Response"

    answer = _llm(prompt)
    sources = list(set(c["source"] for c in chunks))

    return {
        "context_chunks": chunks,
        "answer": answer,
        "sources": sources,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 2b: CUSTOMER SUPPORT AGENT 🎧
# ═══════════════════════════════════════════════════════════════════════════════

SUPPORT_SYSTEM = """You are the **LuxeCart Customer Support Agent** — a friendly, helpful, and thorough support specialist.

Your expertise:
• Shipping policies (domestic, international, same-day, tracking)
• Returns and refund procedures (windows, eligibility, process)
• Payment methods and security
• Order management (placing, cancelling, tracking)
• Account assistance
• FAQ / general help

Rules:
1. Use the retrieved policy context below to answer.
2. If the answer is not in the context, use your general knowledge to provide a helpful response while advising the customer to confirm with support@luxecart.com.
3. Be warm, empathetic, and solution-oriented.
4. When explaining processes, use numbered steps.
5. Always mention relevant contact details when appropriate (email, phone, chat hours).
6. Use markdown formatting for readability.
"""


def support_agent_node(state: AgentState) -> dict:
    """Customer Support Agent — retrieves from policies namespace and answers."""
    from chatbot.rag_engine import retrieve

    query = state["query"]
    chunks = retrieve(query, NS_POLICIES, TOP_K)

    if not chunks:
        return {
            "context_chunks": [],
            "answer": "I'd love to help! Unfortunately, I couldn't find a specific policy document for your question. Please reach out to our support team:\n\n- 📧 **Email**: support@luxecart.com\n- 📞 **Phone**: +91 1800-LUXE-CART\n- 💬 **Live Chat**: Mon–Sat, 9 AM – 9 PM IST",
            "sources": [],
        }

    context = "\n\n---\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks])
    prompt = f"{SUPPORT_SYSTEM}\n\n## Retrieved Policy Context\n{context}\n\n## Customer Question\n{query}\n\n## Your Response"

    answer = _llm(prompt)
    sources = list(set(c["source"] for c in chunks))

    return {
        "context_chunks": chunks,
        "answer": answer,
        "sources": sources,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 2c: BUSINESS INTELLIGENCE AGENT 📊
# ═══════════════════════════════════════════════════════════════════════════════

BI_SYSTEM = """You are the **LuxeCart Business Intelligence Agent** — an analytics expert for the LuxeCart retail platform.

Your expertise:
• AI-powered demand forecasting (GradientBoosting & RandomForest models)
• Sales trends and seasonal patterns
• Inventory optimisation and low-stock alerts
• Promotional strategy recommendations
• Company information and technology stack

Rules:
1. Use the retrieved context AND any live data provided below.
2. If asked about general business concepts or analytics outside our specific data, feel free to use your general knowledge.
3. When discussing forecasts, mention that they use ML models (GBM & RF).
4. Provide actionable insights — don't just state numbers, explain what they mean.
5. If asked about specific product forecasts, suggest using the Demand Forecasting dashboard.
6. Be data-driven and professional.
7. Use markdown formatting for readability.
"""


def analytics_agent_node(state: AgentState) -> dict:
    """Business Intelligence Agent — retrieves from analytics namespace and augments with live data."""
    from chatbot.rag_engine import retrieve

    query = state["query"]
    chunks = retrieve(query, NS_ANALYTICS, TOP_K)

    # Augment with live data when possible
    live_data = _get_live_analytics()

    context_parts = []
    if chunks:
        context_parts.append("\n\n---\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks]))
    if live_data:
        context_parts.append(f"[live_data]\n{live_data}")

    if not context_parts:
        return {
            "context_chunks": [],
            "answer": "I don't have enough data to answer your analytics question right now. Please check the **Demand Forecasting Dashboard** at `/forecast/dashboard` for detailed predictions, or contact the admin team.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(context_parts)
    prompt = f"{BI_SYSTEM}\n\n## Retrieved Analytics Context\n{context}\n\n## Analyst Question\n{query}\n\n## Your Response"

    answer = _llm(prompt)
    sources = list(set(c["source"] for c in chunks)) if chunks else ["live_data"]

    return {
        "context_chunks": chunks or [],
        "answer": answer,
        "sources": sources,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 2d: OFF-TOPIC HANDLER 🚫
# ═══════════════════════════════════════════════════════════════════════════════

OFF_TOPIC_MESSAGE = (
    "I appreciate your question, but that falls **outside my area of expertise**. 😊\n\n"
    "I'm the **LuxeCart AI Assistant**, and I'm specifically designed to help you with:\n\n"
    "- 🛍️ **Products** — Browse our catalog, compare items, check prices & availability\n"
    "- 🎧 **Customer Support** — Shipping, returns, refunds, orders & account help\n"
    "- 📊 **Business Analytics** — Demand forecasting, sales trends & inventory insights\n\n"
    "Please ask me something related to **LuxeCart** and I'll be happy to help!"
)


def off_topic_handler_node(state: AgentState) -> dict:
    """Off-topic handler — politely declines queries outside the LuxeCart domain."""
    return {
        "context_chunks": [],
        "answer": OFF_TOPIC_MESSAGE,
        "sources": [],
    }


def _get_live_analytics() -> str:
    """Pull live stats from the database for the BI agent."""
    try:
        from models import db, ProductModel, OrderModel, UserModel
        from flask import current_app
        with current_app.app_context():
            total_products = ProductModel.query.count()
            total_orders = OrderModel.query.count()
            total_users = UserModel.query.filter_by(role='user').count()
            total_revenue = db.session.query(db.func.sum(OrderModel.total)).scalar() or 0
            low_stock = ProductModel.query.filter(ProductModel.stock < 10).all()
            low_names = [f"{p.name} ({p.stock} left)" for p in low_stock]

            return (
                f"Live Dashboard Stats (as of {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}):\n"
                f"• Total Products: {total_products}\n"
                f"• Total Orders: {total_orders}\n"
                f"• Total Customers: {total_users}\n"
                f"• Total Revenue: ${total_revenue:,.2f}\n"
                f"• Low Stock Alerts: {', '.join(low_names) if low_names else 'None — all products well-stocked'}\n"
            )
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE 3: RESPONSE FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_LABELS = {
    "product": "🛍️ Product Specialist",
    "support": "🎧 Customer Support",
    "analytics": "📊 Business Intelligence",
    "off_topic": "🚫 Off-Topic",
}


def response_node(state: AgentState) -> dict:
    """Format and finalise the response."""
    # The answer is already generated by the agent nodes.
    # This node adds metadata or post-processing if needed.
    return state


# ═══════════════════════════════════════════════════════════════════════════════
#  BUILD THE LANGGRAPH
# ═══════════════════════════════════════════════════════════════════════════════

def _build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("product_agent", product_agent_node)
    graph.add_node("support_agent", support_agent_node)
    graph.add_node("analytics_agent", analytics_agent_node)
    graph.add_node("off_topic_handler", off_topic_handler_node)
    graph.add_node("response", response_node)

    # Entry point
    graph.add_edge(START, "router")

    # Conditional routing from router to the correct agent
    graph.add_conditional_edges(
        "router",
        _route_to_agent,
        {
            "product": "product_agent",
            "support": "support_agent",
            "analytics": "analytics_agent",
            "off_topic": "off_topic_handler",
        },
    )

    # All agents flow into response formatter
    graph.add_edge("product_agent", "response")
    graph.add_edge("support_agent", "response")
    graph.add_edge("analytics_agent", "response")
    graph.add_edge("off_topic_handler", "response")

    # Response → END
    graph.add_edge("response", END)

    return graph.compile()


# Compile once at module level
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def run_agent(question: str) -> Dict[str, Any]:
    """
    Run the full LangGraph multi-agent pipeline.

    Args:
        question: The user's natural-language question.

    Returns:
        Dict with: answer, agent_type, agent_label, sources, reasoning, etc.
    """
    graph = _get_graph()

    initial_state: AgentState = {
        "query": question,
        "agent_type": "",
        "context_chunks": [],
        "agent_reasoning": "",
        "answer": "",
        "sources": [],
        "error": None,
    }

    try:
        result = graph.invoke(initial_state)
        agent_type = result.get("agent_type", "support")
        return {
            "answer": result.get("answer", "Sorry, I couldn't generate a response."),
            "agent_type": agent_type,
            "agent_label": AGENT_LABELS.get(agent_type, "🤖 AI Assistant"),
            "sources": result.get("sources", []),
            "reasoning": result.get("agent_reasoning", ""),
            "retrieved_chunks": len(result.get("context_chunks", [])),
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "answer": f"I encountered an error processing your question. Please try again or contact support at support@luxecart.com.",
            "agent_type": "error",
            "agent_label": "⚠️ System",
            "sources": [],
            "reasoning": str(e),
            "retrieved_chunks": 0,
            "error": str(e),
        }
