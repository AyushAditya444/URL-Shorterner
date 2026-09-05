from datetime import datetime, timedelta

import jwt

from app.security import create_access_token, decode_access_token, upsert_user_and_issue_token
from app.config import settings
from app.models import User


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token(user_id=42)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_decode_rejects_invalid_token():
    assert decode_access_token("not-a-real-token") is None


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.utcnow() - timedelta(days=1)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    assert decode_access_token(expired) is None


def test_upsert_creates_new_user_and_token(db_session):
    profile = {"email": "new@example.com", "name": "New User", "sub": "google-sub-1"}
    user, token = upsert_user_and_issue_token(db_session, profile)
    assert user.email == "new@example.com"
    assert decode_access_token(token)["sub"] == str(user.id)


def test_upsert_reuses_existing_user_by_google_sub(db_session):
    existing = User(email="old@example.com", name="Old Name", google_sub="google-sub-2")
    db_session.add(existing)
    db_session.flush()

    profile = {"email": "old@example.com", "name": "Updated Name", "sub": "google-sub-2"}
    user, _ = upsert_user_and_issue_token(db_session, profile)
    assert user.id == existing.id
    assert user.name == "Updated Name"


def test_login_redirects_to_google(client):
    response = client.get("/api/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_user_when_cookie_present(client, db_session):
    user = User(email="a@example.com", name="A", google_sub="sub-a")
    db_session.add(user)
    db_session.flush()
    token = create_access_token(user_id=user.id)
    client.cookies.set("access_token", token)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "a@example.com"
