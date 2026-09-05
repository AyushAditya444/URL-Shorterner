import json
from datetime import datetime, timedelta

from app.models import Link, Click


def test_redirect_hits_db_and_caches_on_first_request(client, db_session, fake_redis):
    link = Link(code="dbonly1", target_url="https://example.com/db")
    db_session.add(link)
    db_session.commit()

    response = client.get("/dbonly1", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/db"
    cached = json.loads(fake_redis.get("short:dbonly1"))
    assert cached == {"target_url": "https://example.com/db", "link_id": link.id}


def test_redirect_on_cache_hit_uses_cached_link_id_for_click_logging(client, db_session, fake_redis):
    from app.cache import cache_set_link

    link = Link(code="cached1", target_url="https://example.com/cached")
    db_session.add(link)
    db_session.commit()
    cache_set_link(fake_redis, "cached1", "https://example.com/cached", link_id=link.id)

    response = client.get("/cached1", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/cached"

    clicks = db_session.query(Click).filter(Click.link_id == link.id).all()
    assert len(clicks) == 1


def test_redirect_404_for_unknown_code(client):
    response = client.get("/doesnotexist", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_404_for_expired_link(client, db_session):
    link = Link(code="expired1", target_url="https://example.com", expires_at=datetime.utcnow() - timedelta(days=1))
    db_session.add(link)
    db_session.commit()

    response = client.get("/expired1", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_does_not_cache_an_already_expired_link(client, db_session, fake_redis):
    link = Link(code="expired2", target_url="https://example.com", expires_at=datetime.utcnow() - timedelta(days=1))
    db_session.add(link)
    db_session.commit()

    client.get("/expired2", follow_redirects=False)
    assert fake_redis.get("short:expired2") is None


def test_redirect_logs_a_click(client, db_session):
    link = Link(code="clicklog", target_url="https://example.com")
    db_session.add(link)
    db_session.commit()

    client.get("/clicklog", follow_redirects=False, headers={"referer": "https://ref.com", "user-agent": "pytest"})

    clicks = db_session.query(Click).filter(Click.link_id == link.id).all()
    assert len(clicks) == 1
    assert clicks[0].referrer == "https://ref.com"


def test_redirect_rate_limited_after_sixty_per_minute(client, db_session):
    link = Link(code="ratelim1", target_url="https://example.com")
    db_session.add(link)
    db_session.commit()

    for _ in range(60):
        client.get("/ratelim1", follow_redirects=False)
    response = client.get("/ratelim1", follow_redirects=False)
    assert response.status_code == 429
