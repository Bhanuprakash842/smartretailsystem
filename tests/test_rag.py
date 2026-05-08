import os
from app import app
from chatbot.rag_engine import ingest_documents
from chatbot.agents import run_agent
from chatbot.chat_routes import _get_products_from_db

def test_system():
    with app.app_context():
        print("1. Testing Ingestion (after clearing Pinecone)...")
        try:
            products = _get_products_from_db()
            stats = ingest_documents(products=products)
            print("Ingestion Stats:", stats)
        except Exception as e:
            print(f"Error during ingestion: {e}")
            # return # Continue even if it failed partially

        print("\n2. Testing Agents...")
        queries = [
            "Are wireless earbuds available? If so, what is the price?",
            "What is your return policy?",
            "What are our sales analytics and total revenue?"
        ]

        for q in queries:
            print(f"\nQ: {q}")
            try:
                res = run_agent(q)
                agent_lbl = res.get('agent_label', '')
                print(f"Agent: {agent_lbl.encode('utf-8', 'replace').decode('utf-8')}")
                ans = res.get('answer', '')
                print(f"Answer: {ans.encode('utf-8', 'replace').decode('utf-8')}")
            except Exception as e:
                print(f"Error asking agent: {e}")

if __name__ == "__main__":
    test_system()
