"""
MCP Server: Database
Tools:
  - cache_lookup(query) -> cached prior answer if available
  - conversation_history(session_id) -> recent turns
  - user_preferences(session_id) -> stored preferences
  - previous_answers(session_id) -> prior assistant answers this session
"""
from infrastructure import db, cache

TOOL_SCHEMA = {
    "name": "database_lookup",
    "description": "Look up cached answers, conversation history, or user preferences.",
    "parameters": {"session_id": "string", "query": "string"},
}


def cache_lookup(query: str):
    return cache.cache_get("qa", query.strip().lower())


def conversation_history(session_id: str, limit: int = 6):
    return db.get_history(session_id, limit=limit)


def user_preferences(session_id: str):
    return db.get_user_preferences(session_id)


def previous_answers(session_id: str, limit: int = 6):
    history = db.get_history(session_id, limit=limit * 2)
    return [h for h in history if h["role"] == "assistant"][-limit:]


def call(action: str, session_id: str = "", query: str = ""):
    if action == "cache_lookup":
        return cache_lookup(query)
    if action == "conversation_history":
        return conversation_history(session_id)
    if action == "user_preferences":
        return user_preferences(session_id)
    if action == "previous_answers":
        return previous_answers(session_id)
    return None
