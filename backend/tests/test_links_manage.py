from app.models import Link, User
from app.security import create_access_token


def _login(client, db_session, email="owner@example.com", sub="owner-sub"):
    user = User(email=email, name="Owner", google_sub=sub)
    db_session.add(user)
    db_session.flush()
    client.cookies.set("access_token", create_access_token(user.id))
    return user


def test_list_requires_auth(client):
    response = client.get("/api/links")
    assert response.status_code == 401


def test_list_returns_only_own_links(client, db_session):
    owner = _login(client, db_session)
    other = User(email="other@example.com", name="Other", google_sub="other-sub")
    db_session.add(other)
    db_session.flush()
    db_session.add_all([
        Link(code="mine0001", target_url="https://example.com/mine", owner_id=owner.id),
        Link(code="theirs01", target_url="https://example.com/theirs", owner_id=other.id),
    ])
    db_session.commit()

    response = client.get("/api/links")
    codes = [link["code"] for link in response.json()]
    assert codes == ["mine0001"]


def test_delete_requires_ownership(client, db_session):
    _login(client, db_session)
    other = User(email="other2@example.com", name="Other2", google_sub="other-sub-2")
    db_session.add(other)
    db_session.flush()
    link = Link(code="notmine1", target_url="https://example.com", owner_id=other.id)
    db_session.add(link)
    db_session.commit()

    response = client.delete(f"/api/links/{link.id}")
    assert response.status_code == 404


def test_delete_removes_link_and_cache_entry(client, db_session, fake_redis):
    owner = _login(client, db_session)
    link = Link(code="deleteme", target_url="https://example.com", owner_id=owner.id)
    db_session.add(link)
    db_session.commit()
    fake_redis.set("short:deleteme", "https://example.com")

    response = client.delete(f"/api/links/{link.id}")
    assert response.status_code == 204
    assert db_session.query(Link).filter(Link.id == link.id).first() is None
    assert fake_redis.get("short:deleteme") is None
