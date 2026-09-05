from datetime import datetime, timedelta

from app.models import Click, Link, User
from app.security import create_access_token


def _login(client, db_session):
    user = User(email="an@example.com", name="An", google_sub="an-sub")
    db_session.add(user)
    db_session.flush()
    client.cookies.set("access_token", create_access_token(user.id))
    return user


def test_analytics_requires_ownership(client, db_session):
    _login(client, db_session)
    other = User(email="other3@example.com", name="Other3", google_sub="other-sub-3")
    db_session.add(other)
    db_session.flush()
    link = Link(code="notmine2", target_url="https://example.com", owner_id=other.id)
    db_session.add(link)
    db_session.commit()

    response = client.get(f"/api/links/{link.id}/analytics")
    assert response.status_code == 404


def test_analytics_aggregates_clicks(client, db_session):
    owner = _login(client, db_session)
    link = Link(code="stats001", target_url="https://example.com", owner_id=owner.id)
    db_session.add(link)
    db_session.flush()
    db_session.add_all([
        Click(link_id=link.id, clicked_at=datetime.utcnow(), referrer="https://a.com"),
        Click(link_id=link.id, clicked_at=datetime.utcnow(), referrer="https://a.com"),
        Click(link_id=link.id, clicked_at=datetime.utcnow() - timedelta(days=1), referrer="https://b.com"),
    ])
    db_session.commit()

    response = client.get(f"/api/links/{link.id}/analytics")
    body = response.json()
    assert body["total_clicks"] == 3
    assert len(body["clicks_by_day"]) == 2
    assert body["top_referrers"][0] == {"referrer": "https://a.com", "count": 2}
