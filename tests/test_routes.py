
def test_dashboard(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_auth_placeholders(client):
    assert client.get("/login").status_code == 200
    assert client.get("/logout").status_code == 200
