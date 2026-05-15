"""
rag_engine.py
=============
Core RAG engine using **Google Gemini** (free) for embeddings and
**Pinecone** for vector storage.

Responsibilities:
  - Load & chunk documents from documents/
  - Generate embeddings via Gemini text-embedding-004
  - Upsert into Pinecone (per-namespace)
  - Retrieve relevant chunks for a query
"""

import os
import re
import hashlib
from typing import List, Dict, Optional
from datetime import datetime

from chatbot.config import (
    GEMINI_API_KEY, GEMINI_EMBED_MODEL, EMBEDDING_DIMENSION,
    PINECONE_API_KEY, PINECONE_INDEX_NAME, PINECONE_CLOUD, PINECONE_REGION,
    CHUNK_SIZE, CHUNK_OVERLAP, TOP_K,
    DOCS_DIR, DOC_NAMESPACE_MAP,
    NS_PRODUCTS, NS_POLICIES, NS_ANALYTICS,
)

# ---------------------------------------------------------------------------
# Lazy-loaded clients
# ---------------------------------------------------------------------------
_genai = None
_pinecone_index = None


def _get_genai():
    """Initialise and cache the google.generativeai module."""
    global _genai
    if _genai is None:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _genai = genai
    return _genai


def _get_pinecone_index():
    """Return (and cache) the Pinecone index handle."""
    global _pinecone_index
    if _pinecone_index is None:
        from pinecone import Pinecone, ServerlessSpec
        pc = Pinecone(api_key=PINECONE_API_KEY)

        existing = [idx.name for idx in pc.list_indexes()]
        if PINECONE_INDEX_NAME not in existing:
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,     # 768 for text-embedding-004
                metric="cosine",
                spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
            )
            print(f"[RAG] Created Pinecone index '{PINECONE_INDEX_NAME}' (dim={EMBEDDING_DIMENSION})")

        _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


# ---------------------------------------------------------------------------
# Document loading & chunking
# ---------------------------------------------------------------------------

def _load_documents() -> List[Dict]:
    """Read every .txt / .md file from the documents/ directory."""
    docs = []
    if not os.path.isdir(DOCS_DIR):
        print(f"[RAG] Warning — documents/ directory not found at {DOCS_DIR}")
        return docs
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith((".txt", ".md")):
            continue
        fpath = os.path.join(DOCS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            docs.append({"filename": fname, "content": f.read()})
    return docs


def _chunk_text(text: str, source: str) -> List[Dict]:
    """Split text into overlapping chunks with sentence-boundary awareness."""
    chunks = []
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk_text = text[start:end]
        
        # Try to break at a sentence or newline for cleaner context
        if end < len(text):
            last_period = chunk_text.rfind(".")
            last_newline = chunk_text.rfind("\n")
            break_point = max(last_period, last_newline)
            if break_point > CHUNK_SIZE // 3:
                chunk_text = chunk_text[: break_point + 1]
                end = start + break_point + 1
        
        chunk_id = hashlib.md5(f"{source}:{idx}:{chunk_text[:50]}".encode()).hexdigest()
        chunks.append({
            "id": chunk_id,
            "text": chunk_text.strip(),
            "source": source,
            "chunk_index": idx,
        })
        
        if end >= len(text):
            break
            
        start = end - CHUNK_OVERLAP
        if start <= chunks[-1]["chunk_index"]: # Safety against negative progress
             start = end
        idx += 1
    return chunks


def _generate_product_chunks(products: list) -> List[Dict]:
    """Create richly detailed text chunks from live product DB records."""
    chunks = []
    for p in products:
        text = (
            f"Product: {p['name']}\n"
            f"Category: {p['category']}\n"
            f"Price: ${p['price']:.2f}\n"
            f"In Stock: {p['stock']} units\n"
            f"Description: {p['description']}\n"
        )
        cid = hashlib.md5(f"product:{p['id']}:{p['name']}".encode()).hexdigest()
        chunks.append({
            "id": cid,
            "text": text.strip(),
            "source": f"product_db:{p['name']}",
            "chunk_index": 0,
        })
    return chunks


# ---------------------------------------------------------------------------
# Embedding helpers (Google Gemini — FREE)
# ---------------------------------------------------------------------------

def _embed_texts(texts: List[str], task_type: str = "retrieval_document") -> List[List[float]]:
    """Get embeddings from Google Gemini with retry logic."""
    import time
    genai = _get_genai()
    
    for attempt in range(3):
        try:
            result = genai.embed_content(
                model=GEMINI_EMBED_MODEL,
                content=texts,
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSION,
            )
            return result["embedding"]
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = (attempt + 1) * 5
                print(f"[RAG] Rate limit hit. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Max retries exceeded for embedding generation.")


def _embed_query(text: str) -> List[float]:
    """Embed a search query with retry logic."""
    import time
    genai = _get_genai()
    
    for attempt in range(3):
        try:
            result = genai.embed_content(
                model=GEMINI_EMBED_MODEL,
                content=text,
                task_type="retrieval_query",
                output_dimensionality=EMBEDDING_DIMENSION,
            )
            return result["embedding"]
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait = (attempt + 1) * 2
                print(f"[RAG] Rate limit hit on query. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Max retries exceeded for query embedding.")


# ---------------------------------------------------------------------------
# Ingestion — upsert document chunks into Pinecone
# ---------------------------------------------------------------------------

def ingest_documents(products: Optional[list] = None) -> Dict:
    """
    Load all docs + (optionally) live products, chunk, embed, and upsert
    into Pinecone with the correct namespace per agent.
    """
    index = _get_pinecone_index()
    stats = {"documents": 0, "products": 0, "chunks_by_ns": {}}

    # 1. File-based documents → per-namespace
    docs = _load_documents()
    ns_chunks: Dict[str, List[Dict]] = {NS_PRODUCTS: [], NS_POLICIES: [], NS_ANALYTICS: []}
    for doc in docs:
        ns = DOC_NAMESPACE_MAP.get(doc["filename"], NS_POLICIES)
        ns_chunks[ns].extend(_chunk_text(doc["content"], doc["filename"]))
    stats["documents"] = len(docs)

    # 2. Live products go into the products namespace
    if products:
        ns_chunks[NS_PRODUCTS].extend(_generate_product_chunks(products))
        stats["products"] = len(products)

    # 3. Embed & upsert per namespace
    import time
    BATCH = 20
    for ns, chunks in ns_chunks.items():
        if not chunks:
            continue
        total = 0
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            texts = [c["text"] for c in batch]
            try:
                embeddings = _embed_texts(texts)
            except Exception as e:
                if "429" in str(e):
                    print("[RAG] Rate limit hit. Sleeping for 15s...")
                    time.sleep(15)
                    embeddings = _embed_texts(texts)
                else:
                    raise e
            vectors = []
            for chunk, emb in zip(batch, embeddings):
                vectors.append({
                    "id": chunk["id"],
                    "values": emb,
                    "metadata": {
                        "text": chunk["text"],
                        "source": chunk["source"],
                        "chunk_index": chunk["chunk_index"],
                    },
                })
            index.upsert(vectors=vectors, namespace=ns)
            total += len(vectors)
        stats["chunks_by_ns"][ns] = total
        print(f"[RAG] Ingested {total} chunks into namespace '{ns}'")

    stats["status"] = "success"
    stats["timestamp"] = datetime.utcnow().isoformat()
    return stats


# ---------------------------------------------------------------------------
# Retrieval — search a specific namespace
# ---------------------------------------------------------------------------

def retrieve(query: str, namespace: str, top_k: int = TOP_K) -> List[Dict]:
    """Embed the query, search a Pinecone namespace, return top_k matches."""
    q_emb = _embed_query(query)
    index = _get_pinecone_index()
    results = index.query(
        vector=q_emb,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
    )
    matches = []
    for m in results.get("matches", []):
        matches.append({
            "score": round(m["score"], 4),
            "text": m["metadata"].get("text", ""),
            "source": m["metadata"].get("source", ""),
        })
    return matches


def retrieve_multi(query: str, namespaces: List[str], top_k: int = TOP_K) -> List[Dict]:
    """Search across multiple namespaces and merge results by score."""
    all_matches = []
    for ns in namespaces:
        all_matches.extend(retrieve(query, ns, top_k))
    all_matches.sort(key=lambda x: x["score"], reverse=True)
    return all_matches[:top_k]
