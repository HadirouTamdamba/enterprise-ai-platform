"""API tests: authentication, RBAC enforcement, security behaviors."""


async def test_health_endpoints_are_public(client):
    assert (await client.get("/api/v1/health")).status_code == 200
    assert (await client.get("/api/v1/health/live")).status_code == 200


async def test_register_login_me_flow(client):
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@corp.com", "full_name": "New User",
              "password": "SuperSecret123!"},
    )
    assert register.status_code == 201
    assert register.json()["role"] == "viewer"

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "new@corp.com", "password": "SuperSecret123!"},
    )
    assert login.status_code == 200
    tokens = login.json()

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "new@corp.com"


async def test_wrong_password_gives_generic_401(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "victim@corp.com", "full_name": "V", "password": "SuperSecret123!"},
    )
    bad_password = await client.post(
        "/api/v1/auth/login", data={"username": "victim@corp.com", "password": "wrong-pass-123"}
    )
    unknown_user = await client.post(
        "/api/v1/auth/login", data={"username": "ghost@corp.com", "password": "wrong-pass-123"}
    )
    assert bad_password.status_code == unknown_user.status_code == 401
    # Same message in both cases — no account enumeration.
    assert bad_password.json()["message"] == unknown_user.json()["message"]


async def test_protected_route_requires_token(client):
    assert (await client.get("/api/v1/projects")).status_code == 401


async def test_weak_password_rejected(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@corp.com", "full_name": "W", "password": "short"},
    )
    assert response.status_code == 422


async def test_refresh_rotates_tokens(client, viewer_headers):
    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "viewer@test.local", "password": "Password123!"},
    )
    refresh_token = login.json()["refresh_token"]
    refreshed = await client.post("/api/v1/auth/refresh",
                                  json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


async def test_rbac_viewer_cannot_create_project(client, viewer_headers):
    response = await client.post(
        "/api/v1/projects",
        headers=viewer_headers,
        json={"name": "Forbidden Project", "workspace_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_error"


async def test_rbac_viewer_cannot_list_users(client, viewer_headers):
    assert (await client.get("/api/v1/users", headers=viewer_headers)).status_code == 403


async def test_error_responses_carry_request_id(client):
    response = await client.get("/api/v1/projects")
    assert response.status_code == 401
    assert "x-request-id" in response.headers
