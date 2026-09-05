from datetime import datetime, timedelta


def test_create_link_anonymous(client):
    response = client.post("/api/links", json={"url": "https://example.com/some/long/path"})
    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) == 7
    assert body["short_url"].endswith(body["code"])
    assert body["target_url"] == "https://example.com/some/long/path"


def test_create_link_with_custom_alias(client):
    response = client.post("/api/links", json={"url": "https://example.com", "custom_alias": "my-link"})
    assert response.status_code == 201
    assert response.json()["code"] == "my-link"
    assert response.json()["is_custom_alias"] is True


def test_create_link_rejects_taken_alias(client):
    client.post("/api/links", json={"url": "https://example.com", "custom_alias": "taken"})
    response = client.post("/api/links", json={"url": "https://other.com", "custom_alias": "taken"})
    assert response.status_code == 400


def test_create_link_rejects_invalid_url(client):
    response = client.post("/api/links", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_create_link_accepts_expiry(client):
    expires = (datetime.utcnow() + timedelta(days=1)).isoformat()
    response = client.post("/api/links", json={"url": "https://example.com", "expires_at": expires})
    assert response.status_code == 201
    assert response.json()["expires_at"] is not None


def test_create_link_primes_cache(client, fake_redis):
    import json

    response = client.post("/api/links", json={"url": "https://example.com/cached"})
    code = response.json()["code"]
    cached = json.loads(fake_redis.get(f"short:{code}"))
    assert cached["target_url"] == "https://example.com/cached"
    assert cached["link_id"] == response.json()["id"]


def test_create_link_rate_limited_after_ten_per_minute(client):
    for _ in range(10):
        client.post("/api/links", json={"url": "https://example.com"})
    response = client.post("/api/links", json={"url": "https://example.com"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
