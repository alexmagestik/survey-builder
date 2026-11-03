from __future__ import annotations

from tests.helpers import csrf, login, logout, register


def test_register_and_open_dashboard(client):
    response = register(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/surveys"

    dashboard = client.get("/surveys")
    assert dashboard.status_code == 200
    assert "user@example.com" in dashboard.text
    assert "Мои опросы" in dashboard.text


def test_duplicate_email_is_rejected(client):
    assert register(client).status_code == 303
    logout(client)
    response = register(client)
    assert response.status_code == 400
    assert "уже зарегистрирован" in response.text


def test_wrong_password_is_rejected(client):
    register(client)
    logout(client)
    response = login(client, password="wrong-password")
    assert response.status_code == 400
    assert "Неверный email или пароль" in response.text


def test_protected_page_redirects_to_login(client):
    response = client.get("/surveys", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/auth/login?next=")


def test_logout_clears_session(client):
    register(client)
    response = logout(client)
    assert response.status_code == 303
    assert client.get("/surveys", follow_redirects=False).status_code == 303


def test_csrf_is_required(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    bad = client.post(
        "/auth/login",
        data={"csrf_token": "bad-token", "email": "user@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert bad.status_code == 400
    assert "CSRF" in bad.text


def test_login_page_has_csrf_token(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert len(csrf(response)) > 10
