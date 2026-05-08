from chatbot.rag_engine import _chunk_text
import os

with open("documents/product_catalog.txt", "r", encoding="utf-8") as f:
    content = f.read()

chunks = _chunk_text(content, "product_catalog.txt")
print(f"Total chunks generated: {len(chunks)}")
for i, c in enumerate(chunks):
    print(f"\n--- Chunk {i} ---")
    print(c['text'])
    print("-" * 20)
