"""
Redis client — token cache için singleton bağlantı yönetimi.

TOKEN_EXPIRY_HOURS kadar süreyle token → user_data JSON'ını önbelleğe alır.
Redis erişilemez durumdaysa tüm işlemler sessizce atlanır (graceful degradation);
doğrulama PostgreSQL'e düşer.
"""

import json
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis():
    """Redis client singleton döner. Bağlantı yoksa None döner."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis
        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("Redis bağlantısı kuruldu: %s", url)
    except Exception as e:
        logger.warning("Redis bağlanamadı, token cache devre dışı: %s", e)
        _redis_client = None

    return _redis_client


def _key(token: str) -> str:
    return f"auth:token:{token}"


def cache_token(token: str, user_data: Dict, ttl_seconds: int) -> None:
    """Token → user_data eşlemesini Redis'e yaz."""
    r = get_redis()
    if not r:
        return
    try:
        r.setex(_key(token), ttl_seconds, json.dumps(user_data))
    except Exception as e:
        logger.debug("Redis cache_token hatası: %s", e)


def get_cached_token(token: str) -> Optional[Dict]:
    """Redis'ten token karşılığı user_data'yı döner. Yoksa None."""
    r = get_redis()
    if not r:
        return None
    try:
        raw = r.get(_key(token))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug("Redis get_cached_token hatası: %s", e)
    return None


def invalidate_token(token: str) -> None:
    """Tek token'ı Redis'ten sil."""
    r = get_redis()
    if not r:
        return
    try:
        r.delete(_key(token))
    except Exception as e:
        logger.debug("Redis invalidate_token hatası: %s", e)


def invalidate_user_tokens(user_id: int, tokens: list) -> None:
    """Bir kullanıcıya ait tüm token'ları Redis'ten sil."""
    r = get_redis()
    if not r or not tokens:
        return
    try:
        r.delete(*[_key(t) for t in tokens])
    except Exception as e:
        logger.debug("Redis invalidate_user_tokens hatası: %s", e)
