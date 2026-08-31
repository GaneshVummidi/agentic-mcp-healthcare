"""
MCP Server: Document Store (RAG)
Tools:
  - ingest_document(title, text) -> chunks, embeds (nomic-embed-text via Ollama), stores
  - search(query, top_k) -> top matching chunks with similarity scores

This lets admins upload hospital guidelines/policies/protocols so the
Answer Agent can ground responses in institution-specific documents, not
just public web/medical-API sources. Embeddings are generated locally via
Ollama's embeddings API (no external calls, no extra API keys).
"""
import math
import re
import sqlite3
import time
import uuid
import json
import requests

from config import settings
from infrastructure.logger import error_logger, system_logger

TOOL_SCHEMA = {
    "name": "document_search",
    "description": "Search uploaded hospital documents (guidelines, protocols) for relevant context.",
    "parameters": {"query": "string", "top_k": "int"},
}

CHUNK_SIZE = 700          # characters per chunk
CHUNK_OVERLAP = 100


def _get_conn():
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_document_store():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            uploaded_at REAL NOT NULL,
            chunk_count INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            title TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _chunk_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def _embed(text: str) -> list[float] | None:
    try:
        resp = requests.post(
            f"{settings.OLLAMA_HOST}/api/embeddings",
            json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"Embedding failed (is Ollama + {settings.OLLAMA_EMBED_MODEL} available?): {e}")
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def ingest_document(title: str, text: str) -> dict:
    init_document_store()
    doc_id = str(uuid.uuid4())
    chunks = _chunk_text(text)

    conn = _get_conn()
    embedded_count = 0
    for i, chunk in enumerate(chunks):
        embedding = _embed(chunk)
        conn.execute(
            """INSERT INTO document_chunks (id, document_id, title, chunk_index, text, embedding, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), doc_id, title, i, chunk,
             json.dumps(embedding) if embedding else None, time.time()),
        )
        if embedding:
            embedded_count += 1

    conn.execute(
        "INSERT INTO documents (id, title, uploaded_at, chunk_count) VALUES (?, ?, ?, ?)",
        (doc_id, title, time.time(), len(chunks)),
    )
    conn.commit()
    conn.close()

    system_logger.info(f"[DocumentStore] ingested '{title}' -> {len(chunks)} chunks ({embedded_count} embedded)")
    return {"document_id": doc_id, "title": title, "chunk_count": len(chunks), "embedded_chunks": embedded_count}


def list_documents() -> list[dict]:
    init_document_store()
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(document_id: str) -> bool:
    conn = _get_conn()
    conn.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
    cur = conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def search(query: str, top_k: int = 3) -> list[dict]:
    init_document_store()
    query_embedding = _embed(query)
    if not query_embedding:
        return []  # RAG gracefully degrades to zero results if embeddings are unavailable

    conn = _get_conn()
    rows = conn.execute("SELECT title, text, embedding FROM document_chunks WHERE embedding IS NOT NULL").fetchall()
    conn.close()

    scored = []
    for r in rows:
        emb = json.loads(r["embedding"])
        score = _cosine(query_embedding, emb)
        scored.append({"title": r["title"], "text": r["text"], "score": round(score, 3)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored[:top_k] if s["score"] > 0.3]  # relevance floor


def call(query: str, top_k: int = 3):
    return search(query, top_k)
