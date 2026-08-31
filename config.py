"""
Central configuration for MediAegis AI.
Loads from .env (falls back to sane defaults so the app still boots
if the operator hasn't copied .env.example -> .env yet).
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Settings:
    # LLM / Infrastructure Layer - Ollama (Local)
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    # Redis Cache
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 3600))

    # SQLite
    SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(BASE_DIR, "data", "mediaegis.db"))

    # Web Search MCP
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

    # Medical API MCP
    USE_OPENFDA = os.getenv("USE_OPENFDA", "true").lower() == "true"

    # Server
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8000))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # Logging
    LOG_DIR = os.path.join(BASE_DIR, "logs")


settings = Settings()
