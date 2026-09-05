from fastapi import Depends, HTTPException, Request

from app.redis_client import get_redis


def check_rate_limit(redis_client, key: str, limit: int, window_seconds: int) -> bool:
    full_key = f"ratelimit:{key}"
    count = redis_client.incr(full_key)
    if count == 1:
        redis_client.expire(full_key, window_seconds)
    return count <= limit


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(bucket: str, limit: int, window_seconds: int):
    def dependency(request: Request, redis_client=Depends(get_redis)):
        key = f"ip:{_client_ip(request)}:{bucket}"
        if not check_rate_limit(redis_client, key, limit, window_seconds):
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(window_seconds)})

    return dependency
