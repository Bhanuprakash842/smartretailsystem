from chatbot.rag_engine import retrieve
from app import app

def test_retrieval():
    with app.app_context():
        query = "earbuds"
        print(f"Querying for: {query}")
        results = retrieve(query, "products", top_k=5)
        print("\nResults in 'products' namespace:")
        for r in results:
            print(f"Score: {r['score']} | Source: {r['source']}")
            print(f"Text:\n{r['text']}")
            print("-" * 40)

if __name__ == "__main__":
    test_retrieval()
