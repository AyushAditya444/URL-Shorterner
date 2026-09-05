import json
from datetime import datetime

DEFAULT_TTL_SECONDS = 3600


def _key(code: str) -> str:
    return f"short:{code}"


def cache_set_link(redis_client, code: str, target_url: str, link_id: int, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    payload = json.dumps({"target_url": target_url, "link_id": link_id})
    redis_client.set(_key(code), payload, ex=ttl_seconds)


def cache_get_link(redis_client, code: str) -> dict | None:
    raw = redis_client.get(_key(code))
    if raw is None:
        return None
    return json.loads(raw)


def cache_delete_link(redis_client, code: str) -> None:
    redis_client.delete(_key(code))


def ttl_for_expiry(expires_at: datetime | None, default_ttl: int = DEFAULT_TTL_SECONDS) -> int:
    if expires_at is None:
        return default_ttl
    seconds_left = int((expires_at - datetime.utcnow()).total_seconds())
    return max(min(default_ttl, seconds_left), 0)
