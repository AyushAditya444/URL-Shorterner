from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import cache_delete_link, cache_set_link, ttl_for_expiry
from app.config import settings
from app.db import get_db
from app.models import Click, Link, User
from app.rate_limit import rate_limit_dependency
from app.redis_client import get_redis
from app.schemas import AnalyticsOut, LinkCreate, LinkOut
from app.security import get_current_user, get_current_user_optional
from app.shortcode import generate_code

router = APIRouter(prefix="/api/links", tags=["links"])

MAX_CODE_ATTEMPTS = 5


def _to_out(link: Link) -> LinkOut:
    return LinkOut(
        id=link.id,
        code=link.code,
        short_url=f"{settings.public_base_url}/{link.code}",
        target_url=link.target_url,
        is_custom_alias=link.is_custom_alias,
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


@router.post("", status_code=201, response_model=LinkOut, dependencies=[Depends(rate_limit_dependency("create", 10, 60))])
def create_link(
    payload: LinkCreate,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
    user: User | None = Depends(get_current_user_optional),
):
    if payload.custom_alias:
        existing = db.query(Link).filter(Link.code == payload.custom_alias).first()
        if existing:
            raise HTTPException(status_code=400, detail="Alias already taken")
        code = payload.custom_alias
        is_custom = True
    else:
        code = None
        is_custom = False
        for _ in range(MAX_CODE_ATTEMPTS):
            candidate = generate_code()
            if not db.query(Link).filter(Link.code == candidate).first():
                code = candidate
                break
        if code is None:
            raise HTTPException(status_code=500, detail="Could not generate a unique code")

    link = Link(
        code=code,
        target_url=str(payload.url),
        owner_id=user.id if user else None,
        is_custom_alias=is_custom,
        expires_at=payload.expires_at,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Alias already taken")
    db.refresh(link)

    ttl = ttl_for_expiry(link.expires_at)
    if ttl > 0:
        cache_set_link(redis_client, link.code, link.target_url, link.id, ttl_seconds=ttl)
    return _to_out(link)


@router.get("", response_model=list[LinkOut])
def list_my_links(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    links = db.query(Link).filter(Link.owner_id == user.id).order_by(Link.created_at.desc()).all()
    return [_to_out(link) for link in links]


@router.delete("/{link_id}", status_code=204)
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
    user: User = Depends(get_current_user),
):
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    cache_delete_link(redis_client, link.code)
    db.delete(link)
    db.commit()


@router.get("/{link_id}/analytics", response_model=AnalyticsOut)
def link_analytics(link_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    link = db.query(Link).filter(Link.id == link_id, Link.owner_id == user.id).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    total_clicks = db.query(func.count(Click.id)).filter(Click.link_id == link.id).scalar()

    by_day_rows = (
        db.query(func.date(Click.clicked_at), func.count(Click.id))
        .filter(Click.link_id == link.id)
        .group_by(func.date(Click.clicked_at))
        .order_by(func.date(Click.clicked_at))
        .all()
    )
    clicks_by_day = [{"date": str(day), "count": count} for day, count in by_day_rows]

    top_referrer_rows = (
        db.query(Click.referrer, func.count(Click.id).label("count"))
        .filter(Click.link_id == link.id)
        .group_by(Click.referrer)
        .order_by(func.count(Click.id).desc())
        .limit(5)
        .all()
    )
    top_referrers = [{"referrer": referrer, "count": count} for referrer, count in top_referrer_rows]

    return AnalyticsOut(total_clicks=total_clicks, clicks_by_day=clicks_by_day, top_referrers=top_referrers)
