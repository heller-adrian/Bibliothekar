"""BA-03: owner session, CSRF, cross-origin and fail-closed HTTP tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import security


@pytest.fixture()
def secure_client(monkeypatch):
    monkeypatch.delenv("BIBLIOTHEKAR_AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("BIBLIOTHEKAR_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("BIBLIOTHEKAR_ADMIN_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("BIBLIOTHEKAR_COOKIE_SECURE", raising=False)
    with security._LOCK:
        security._SESSIONS.clear()
        security._FAILURES.clear()

    app = FastAPI()

    @app.get("/")
    def home():
        return JSONResponse({"private": True})

    @app.get("/api/items")
    def items():
        return {"private": True}

    @app.post("/api/items")
    def create():
        return {"changed": True}

    @app.put("/api/items")
    def update():
        return {"changed": True}

    @app.patch("/api/items")
    def patch():
        return {"changed": True}

    @app.delete("/api/items")
    def remove():
        return {"changed": True}

    @app.get("/healthz")
    def health():
        return {"alive": True}

    @app.middleware("http")
    async def authenticate(request, call_next):
        return await security.protect_request(request, call_next)

    with TestClient(app, base_url="http://testserver", follow_redirects=False) as client:
        yield client


def _login(client, password):
    return client.post(
        "/auth/login", json={"password": password},
        headers={"Origin": "http://testserver"},
    )


def test_0500_no_password_is_never_anonymous(secure_client):
    assert secure_client.get("/healthz").status_code == 200
    assert secure_client.get("/api/items").status_code == 503
    page = secure_client.get("/")
    assert page.status_code == 503
    assert "Administratorpasswort" in page.text
    assert _login(secure_client, "NoDefaultPassword987654").status_code == 503


def test_0500_weak_password_rejected_and_does_not_open_api(secure_client, monkeypatch):
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", "short")
    assert secure_client.get("/api/items").status_code == 503


def test_0500_login_sets_httponly_cookie_csrf_and_all_unsafe_verbs_guarded(
    secure_client, monkeypatch,
):
    secret = "test-only-owner-password-123456"
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", secret)
    assert secure_client.get("/api/items").status_code == 401
    redirect = secure_client.get("/")
    assert redirect.status_code == 303
    assert redirect.headers["location"].startswith("/login?")
    page = secure_client.get("/login")
    assert "Bibliothekar" in page.text
    assert "no-store" in page.headers["cache-control"]
    assert _login(secure_client, "wrong-password-12345").status_code == 401
    login = _login(secure_client, secret)
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=strict" in login.headers["set-cookie"].lower()
    assert secure_client.get("/api/items").json() == {"private": True}
    csrf = secure_client.cookies.get("bibliothekar_csrf")
    assert csrf
    for verb in ("post", "put", "patch", "delete"):
        call = getattr(secure_client, verb)
        assert call("/api/items").status_code == 403
        assert call(
            "/api/items", headers={
                "Origin": "http://testserver",
                "X-Bibliothekar-CSRF": csrf,
            },
        ).json() == {"changed": True}
        assert call(
            "/api/items", headers={
                "Origin": "http://evil.example",
                "X-Bibliothekar-CSRF": csrf,
            },
        ).status_code == 403
        assert call(
            "/api/items", headers={
                "Origin": "http://testserver",
                "Sec-Fetch-Site": "same-site",
                "X-Bibliothekar-CSRF": csrf,
            },
        ).status_code == 403
        assert call(
            "/api/items", headers={
                "Origin": "null", "X-Bibliothekar-CSRF": csrf,
            },
        ).status_code == 403

    assert secure_client.post(
        "/auth/logout", headers={
            "Origin": "http://testserver",
            "X-Bibliothekar-CSRF": csrf,
        },
    ).status_code == 200
    assert secure_client.get("/api/items").status_code == 401


def test_0500_password_file_overrides_env_and_rotates_after_restart(
    secure_client, monkeypatch, tmp_path,
):
    file = tmp_path / "admin-password"
    file.write_text("file-only-password-123456789\n")
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", "wrong-env-123456789")
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD_FILE", str(file))
    assert _login(secure_client, "wrong-env-123456789").status_code == 401
    assert _login(secure_client, "file-only-password-123456789").status_code == 200
    file.unlink()
    assert secure_client.get("/api/items").status_code == 503


def test_0500_login_cross_site_and_rate_limit(secure_client, monkeypatch):
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", "very-long-local-secret-123456789")
    assert secure_client.post(
        "/auth/login", json={"password": "very-long-local-secret-123456789"},
        headers={"Origin": "http://evil.example"},
    ).status_code == 403
    for _ in range(8):
        assert _login(secure_client, "invalid") .status_code == 401
    assert _login(secure_client, "very-long-local-secret-123456789").status_code == 429


def test_0500_real_app_routes_are_behind_auth(monkeypatch):
    monkeypatch.delenv("BIBLIOTHEKAR_AUTH_TEST_BYPASS", raising=False)
    monkeypatch.setenv("BIBLIOTHEKAR_ADMIN_PASSWORD", "temporary-internal-test-secret-1234567")
    from app.main import app
    # Do not run the application's startup hooks in an auth-only test;
    # no database, config, import paths or background worker may be touched.
    client = TestClient(app, follow_redirects=False)
    try:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/health").status_code == 401
        assert client.get("/api/jobs").status_code == 401
        assert client.post("/api/libraries", json={"display_name": "Unauthorized"}).status_code == 401
        assert client.delete("/api/jobs/unused/events/unused").status_code == 401
    finally:
        client.close()


def test_0500_pwa_fetch_has_csrf_header_in_all_shared_layouts():
    from app.ui_shell import apply_shell
    from app.security import _client_code
    html = apply_shell(
        "<html><head></head><body><main></main></body></html>",
        active_area="workspace",
    )
    assert '<script src="/auth/client.js"></script>' in html
    js = _client_code()
    assert "X-Bibliothekar-CSRF" in js
    assert "credentials:\"same-origin\"" in js
    assert '["POST","PUT","PATCH","DELETE"]' in js


def test_0500_explicit_pytest_bypass_requires_both_guards(monkeypatch):
    monkeypatch.setenv("BIBLIOTHEKAR_AUTH_TEST_BYPASS", "pytest-isolated")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert not security._is_test_bypass()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy-test")
    assert security._is_test_bypass()
