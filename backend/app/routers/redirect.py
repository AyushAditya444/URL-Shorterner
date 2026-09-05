from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.cache import cache_get_link, cache_set_link, ttl_for_expiry
from app.db import get_db
from app.models import Click, Link
from app.rate_limit import rate_limit_dependency
from app.redis_client import get_redis

router = APIRouter(tags=["redirect"])


def _log_click(db: Session, link_id: int, referrer: str | None, user_agent: str | None) -> None:
    db.add(Click(link_id=link_id, referrer=referrer, user_agent=user_agent))
    db.commit()


@router.get("/{code}", dependencies=[Depends(rate_limit_dependency("redirect", 60, 60))])
def redirect_to_target(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
):
    cached = cache_get_link(redis_client, code)
    if cached is not None:
        target_url = cached["target_url"]
        link_id = cached["link_id"]
    else:
        link = db.query(Link).filter(Link.code == code).first()
        if link is None:
            raise HTTPException(status_code=404, detail="Not found")
        if link.expires_at and link.expires_at < datetime.utcnow():
            raise HTTPException(status_code=404, detail="Link expired")
        target_url = link.target_url
        link_id = link.id
        ttl = ttl_for_expiry(link.expires_at)
        if ttl > 0:
            cache_set_link(redis_client, code, target_url, link_id, ttl_seconds=ttl)

    background_tasks.add_task(
        _log_click, db, link_id, request.headers.get("referer"), request.headers.get("user-agent")
    )
    return RedirectResponse(url=target_url, status_code=302)
