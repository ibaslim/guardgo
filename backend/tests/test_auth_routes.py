import pytest
from fastapi import FastAPI
from fastapi import Response
from httpx import ASGITransport, AsyncClient

from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.api.interactive.signup_manager.signup_manager import SignupManager
from orion.services.session_manager.session_manager import session_manager
from orion.helper_manager.env_handler import env_handler
from routes.auth_routes import auth_router, token as token_route
from fastapi.security import OAuth2PasswordRequestForm


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


@pytest.mark.anyio
async def test_signup_route_returns_201_and_manager_payload(monkeypatch):
    async def _signup(_data):
        return {"message": "Signup successful", "status": "pending"}

    monkeypatch.setattr(SignupManager, "signup_user", staticmethod(_signup))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/signup",
            json={
                "username": "tenantadm1",
                "email": "tenant@example.com",
                "password": "StrongPass1!",
                "tenant_type": "guard",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.anyio
async def test_signup_verificaion_route_calls_resend_manager(monkeypatch):
    async def _resend(_data):
        return {"message": "Verification email resent."}

    monkeypatch.setattr(SignupManager, "resend_verification_email", staticmethod(_resend))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/signup/verificaion",
            json={
                "username": "tenantadm1",
                "email": "tenant@example.com",
                "password": "StrongPass1!",
                "tenant_type": "guard",
            },
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email resent."


@pytest.mark.anyio
async def test_verify_route_uses_auth_manager(monkeypatch):
    async def _verify(_token):
        return {"message": "Email verified successfully. Your account is active."}

    monkeypatch.setattr(auth_manager, "verify_user", staticmethod(_verify))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/verify/token-123")

    assert response.status_code == 200
    assert response.json()["message"] == "Email verified successfully. Your account is active."


@pytest.mark.anyio
async def test_token_demo_route_uses_env_credentials(monkeypatch):
    class FakeEnv:
        def env(self, key, default=None):
            if key == "DEMO_USERNAME":
                return "demo-user"
            if key == "DEMO_PASSWORD":
                return "demo-pass"
            return default

    async def _login(username, password, free=False):
        assert username == "demo-user"
        assert password == "demo-pass"
        assert free is True
        return {"access_token": "demo-access-token", "token_type": "bearer"}

    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))
    monkeypatch.setattr(auth_manager, "login", staticmethod(_login))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/token/demo")

    assert response.status_code == 200
    assert response.json()["access_token"] == "demo-access-token"


@pytest.mark.anyio
async def test_token_demo_route_no_cookie_when_twofa_required(monkeypatch):
    class FakeEnv:
        def env(self, key, default=None):
            if key == "DEMO_USERNAME":
                return "demo-user"
            if key == "DEMO_PASSWORD":
                return "demo-pass"
            return default

    async def _login(_username, _password, free=False):
        assert free is True
        return {"twofa_required": True, "temp_token": "demo-temp-token"}

    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))
    monkeypatch.setattr(auth_manager, "login", staticmethod(_login))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/token/demo")

    assert response.status_code == 200
    assert response.json()["twofa_required"] is True
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
async def test_refresh_route_requires_token():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/token/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


@pytest.mark.anyio
async def test_refresh_route_uses_bearer_token(monkeypatch):
    class FakeSession:
        async def refresh_token(self, token):
            assert token == "header-token-1"
            return {"access_token": "refreshed-token-1", "token_type": "bearer"}

    monkeypatch.setattr(session_manager, "get_instance", staticmethod(lambda: FakeSession()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/token/refresh", headers={"Authorization": "Bearer header-token-1"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "refreshed-token-1"


@pytest.mark.anyio
async def test_token_function_sets_cookie_when_access_token_present(monkeypatch):
    async def _login(username, password, free=False):
        assert username == "tenant@example.com"
        assert password == "StrongPass1!"
        assert free is False
        return {"access_token": "access-token-1", "token_type": "bearer"}

    monkeypatch.setattr(auth_manager, "login", staticmethod(_login))

    form = OAuth2PasswordRequestForm(username="tenant@example.com", password="StrongPass1!", scope="")
    response = Response()
    result = await token_route(form_data=form, response=response)

    assert result["access_token"] == "access-token-1"
    assert "access_token=access-token-1" in (response.headers.get("set-cookie") or "")


@pytest.mark.anyio
async def test_token_function_does_not_set_cookie_when_twofa_required(monkeypatch):
    async def _login(username, password, free=False):
        return {"twofa_required": True, "temp_token": "tmp-token-1"}

    monkeypatch.setattr(auth_manager, "login", staticmethod(_login))

    form = OAuth2PasswordRequestForm(username="tenant@example.com", password="StrongPass1!", scope="")
    response = Response()
    result = await token_route(form_data=form, response=response)

    assert result["twofa_required"] is True
    assert response.headers.get("set-cookie") is None


@pytest.mark.anyio
async def test_verify_2fa_route_uses_oauth_token(monkeypatch):
    class FakeSession:
        async def verify_2fa_and_issue(self, ptoken, code):
            assert ptoken == "oauth-token-1"
            assert code == "123456"
            return {"access_token": "issued-2fa-token", "token_type": "bearer"}

    monkeypatch.setattr(session_manager, "get_instance", staticmethod(lambda: FakeSession()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/token/2fa/verify",
            json={"code": "123456"},
            headers={"Authorization": "Bearer oauth-token-1"},
        )

    assert response.status_code == 200
    assert response.json()["access_token"] == "issued-2fa-token"


@pytest.mark.anyio
async def test_logout_route_deletes_cookie_and_calls_session_logout(monkeypatch):
    captured = {}

    def _logout_user(*, ptoken):
        captured["token"] = ptoken

    monkeypatch.setattr(session_manager, "logout_user", staticmethod(_logout_user))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/logout", cookies={"access_token": "cookie-token-1"})

    assert response.status_code == 200
    assert response.json()["detail"] == "Logged out"
    assert captured["token"] == "cookie-token-1"
    set_cookie = response.headers.get("set-cookie") or ""
    assert "access_token=" in set_cookie


@pytest.mark.anyio
async def test_forgot_route_forwards_email_to_manager(monkeypatch):
    async def _forgot_password(email):
        assert email == "tenant@example.com"
        return {"message": "Reset password mail send successfully."}

    monkeypatch.setattr(auth_manager, "forgot_password", staticmethod(_forgot_password))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/forgot", json={"email": "tenant@example.com"})

    assert response.status_code == 200
    assert response.json()["message"] == "Reset password mail send successfully."


@pytest.mark.anyio
async def test_update_password_route_forwards_payload(monkeypatch):
    async def _update_password(token, password):
        assert token == "reset-token-1"
        assert password == "StrongPass1!"
        return {"message": "Password reset successfully."}

    monkeypatch.setattr(auth_manager, "update_password", staticmethod(_update_password))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/updatePassword",
            json={"token": "reset-token-1", "password": "StrongPass1!"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successfully."


@pytest.mark.anyio
async def test_reset_context_route_uses_manager(monkeypatch):
    async def _get_reset_context(token):
        assert token == "reset-token-ctx"
        return {"invite_pending": False, "email": "tenant@example.com", "username": "tenantadm1", "full_name": ""}

    monkeypatch.setattr(auth_manager, "get_password_reset_context", staticmethod(_get_reset_context))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/reset/context/reset-token-ctx")

    assert response.status_code == 200
    assert response.json()["email"] == "tenant@example.com"


@pytest.mark.anyio
async def test_invite_context_route_uses_manager(monkeypatch):
    async def _get_invite_context(token):
        assert token == "invite-token-ctx"
        return {"invite_pending": True, "email": "invite@example.com", "username": "inviteusr1", "full_name": "Invite User"}

    monkeypatch.setattr(auth_manager, "get_invite_context", staticmethod(_get_invite_context))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/invite/context/invite-token-ctx")

    assert response.status_code == 200
    assert response.json()["invite_pending"] is True


@pytest.mark.anyio
async def test_invite_activate_route_forwards_all_fields(monkeypatch):
    async def _activate(token, password, username, full_name):
        assert token == "invite-token-1"
        assert password == "StrongPass1!"
        assert username == "inviteusr1"
        assert full_name == "Invite User"
        return {"message": "Account activated successfully."}

    monkeypatch.setattr(auth_manager, "activate_invited_user", staticmethod(_activate))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/invite/activate",
            json={
                "token": "invite-token-1",
                "password": "StrongPass1!",
                "username": "inviteusr1",
                "full_name": "Invite User",
            },
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Account activated successfully."
