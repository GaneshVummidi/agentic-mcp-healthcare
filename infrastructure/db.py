"""
Infrastructure Layer -> SQLite (Conversation History, Evaluation Logs, User Data)
Also backs the "Database MCP Server" (cache lookup / previous answers).
"""
import sqlite3
import os
import json
import time
import uuid
from config import settings

os.makedirs(os.path.dirname(settings.SQLITE_PATH), exist_ok=True)


def get_conn():
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_logs (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            faithfulness REAL,
            relevance REAL,
            context_relevance REAL,
            hallucination_risk REAL,
            overall_score REAL,
            latency_ms REAL,
            created_at REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            session_id TEXT PRIMARY KEY,
            preferences TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content, created_at FROM conversations WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def save_evaluation(session_id, query, answer, metrics: dict, latency_ms: float):
    conn = get_conn()
    conn.execute(
        """INSERT INTO evaluation_logs
           (id, session_id, query, answer, faithfulness, relevance, context_relevance,
            hallucination_risk, overall_score, latency_ms, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()), session_id, query, answer,
            metrics.get("faithfulness"), metrics.get("relevance"),
            metrics.get("context_relevance"), metrics.get("hallucination_risk"),
            metrics.get("overall_score"), latency_ms, time.time(),
        ),
    )
    conn.commit()
    conn.close()


def get_user_preferences(session_id: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        "SELECT preferences FROM user_preferences WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return json.loads(row["preferences"]) if row else {}


def get_admin_stats(recent_limit: int = 200) -> dict:
    """
    Aggregates data already logged by the Evaluation Engine and conversation
    log for the admin analytics dashboard: volume, quality trends, latency,
    cache efficiency, and risk-level distribution.
    """
    conn = get_conn()

    total_queries = conn.execute("SELECT COUNT(*) c FROM evaluation_logs").fetchone()["c"]
    total_sessions = conn.execute("SELECT COUNT(DISTINCT session_id) c FROM conversations").fetchone()["c"]

    avg_row = conn.execute("""
        SELECT AVG(faithfulness) f, AVG(relevance) r, AVG(context_relevance) cr,
               AVG(hallucination_risk) hr, AVG(overall_score) os, AVG(latency_ms) lat
        FROM evaluation_logs
    """).fetchone()

    recent_rows = conn.execute(
        """SELECT query, answer, faithfulness, relevance, hallucination_risk,
                  overall_score, latency_ms, created_at
           FROM evaluation_logs ORDER BY created_at DESC LIMIT ?""",
        (recent_limit,),
    ).fetchall()

    doc_count = conn.execute("SELECT COUNT(*) c FROM documents").fetchone()["c"] if _table_exists(conn, "documents") else 0

    conn.close()

    recent = [dict(r) for r in recent_rows]

    # Rolling daily volume + average quality for the last 14 days (bucketed by day)
    import datetime
    daily = {}
    for r in recent:
        day = datetime.datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d")
        bucket = daily.setdefault(day, {"count": 0, "score_sum": 0.0, "latency_sum": 0.0})
        bucket["count"] += 1
        bucket["score_sum"] += r["overall_score"] or 0
        bucket["latency_sum"] += r["latency_ms"] or 0

    daily_series = [
        {
            "date": day,
            "count": b["count"],
            "avg_overall_score": round(b["score_sum"] / b["count"], 3) if b["count"] else 0,
            "avg_latency_ms": round(b["latency_sum"] / b["count"], 1) if b["count"] else 0,
        }
        for day, b in sorted(daily.items())
    ]

    return {
        "total_queries": total_queries,
        "total_sessions": total_sessions,
        "total_documents": doc_count,
        "averages": {
            "faithfulness": round(avg_row["f"] or 0, 3),
            "relevance": round(avg_row["r"] or 0, 3),
            "context_relevance": round(avg_row["cr"] or 0, 3),
            "hallucination_risk": round(avg_row["hr"] or 0, 3),
            "overall_score": round(avg_row["os"] or 0, 3),
            "latency_ms": round(avg_row["lat"] or 0, 1),
        },
        "daily_series": daily_series,
        "recent_queries": recent[:20],
    }


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def set_user_preferences(session_id: str, prefs: dict):
    conn = get_conn()
    conn.execute(
        """INSERT INTO user_preferences (session_id, preferences, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET preferences=excluded.preferences, updated_at=excluded.updated_at""",
        (session_id, json.dumps(prefs), time.time()),
    )
    conn.commit()
    conn.close()
