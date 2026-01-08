
def test_dashboard_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_dashboard_ok(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200


def test_dashboard_prophet_bulk_disabled(auth_client):
    response = auth_client.post(
        "/prophet/bulk", headers={"Accept": "application/json"}
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["state"] == "error"
    assert payload["message"] == "Prophet forecast disabled"


def test_health_requires_login(client):
    response = client.get("/api/health")
    assert response.status_code == 401
    assert response.json == {"error": "auth required"}


def test_auth_pages_public(client):
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200


def test_register_flow(client):
    response = client.post(
        "/register",
        data={
            "email": "newuser@example.com",
            "password": "Password123!",
            "password_confirm": "Password123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_login_logout_flow(client, user):
    response = client.post(
        "/login",
        data={"email": user.email, "password": "Password123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200
