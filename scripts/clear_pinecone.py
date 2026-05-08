from pinecone import Pinecone
import os
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = "luxecart-agents"

def clear_pinecone():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    
    stats = index.describe_index_stats()
    print("Before deletion stats:", stats)
    
    for ns in stats['namespaces']:
        print(f"Deleting namespace: {ns}")
        index.delete(delete_all=True, namespace=ns)
    
    print("After deletion stats:", index.describe_index_stats())

if __name__ == "__main__":
    clear_pinecone()
