def test_unknown_route_returns_404_json(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/api/links",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
