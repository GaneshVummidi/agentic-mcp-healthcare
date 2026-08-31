"""
Infrastructure Layer -> Redis (Cache)
Query Cache + Response Cache, TTL based.
Falls back to an in-process dict if Redis isn't running, so the app
still works out of the box without extra setup.
"""
import json
import time
from config import settings
from infrastructure.logger import system_logger, error_logger

_memory_store: dict[str, tuple[float, str]] = {}
_redis_client = None
_redis_available = False

try:
    import redis

    _redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        socket_connect_timeout=1,
        decode_responses=True,
    )
    _redis_client.ping()
    _redis_available = True
    system_logger.info("Connected to Redis cache.")
except Exception as e:  # noqa: BLE001
    _redis_available = False
    system_logger.warning(f"Redis unavailable, using in-memory cache fallback. ({e})")


def _key(prefix: str, key: str) -> str:
    return f"mediaegis:{prefix}:{key}"


def cache_get(prefix: str, key: str):
    full_key = _key(prefix, key)
    try:
        if _redis_available:
            val = _redis_client.get(full_key)
            return json.loads(val) if val else None
        else:
            item = _memory_store.get(full_key)
            if not item:
                return None
            expires_at, val = item
            if time.time() > expires_at:
                _memory_store.pop(full_key, None)
                return None
            return json.loads(val)
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"cache_get failed: {e}")
        return None


def cache_set(prefix: str, key: str, value, ttl: int | None = None):
    ttl = ttl or settings.CACHE_TTL_SECONDS
    full_key = _key(prefix, key)
    serialized = json.dumps(value)
    try:
        if _redis_available:
            _redis_client.setex(full_key, ttl, serialized)
        else:
            _memory_store[full_key] = (time.time() + ttl, serialized)
    except Exception as e:  # noqa: BLE001
        error_logger.error(f"cache_set failed: {e}")
