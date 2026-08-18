import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from src.dependencies import AuthenticatedUserDep
from src.middlewares import (
    BearerTokenAuthMiddleware,
    RequestLoggingMiddleware,
    log_error,
    log_request,
)


@pytest.fixture
def auth_app():
    """Create a test FastAPI application with BearerTokenAuthMiddleware."""
    test_app = FastAPI()

    test_app.add_middleware(
        BearerTokenAuthMiddleware,
        enabled=True,
        secret_token="valid-secret-token-123",
        excluded_paths={"/docs", "/openapi.json", "/api/v1/ping", "/public"},
    )
    test_app.add_middleware(RequestLoggingMiddleware)

    @test_app.get("/public")
    async def public_endpoint():
        return {"status": "public ok"}

    @test_app.get("/api/v1/ping")
    async def ping_endpoint():
        return {"status": "pong"}

    @test_app.get("/api/v1/protected")
    async def protected_endpoint(request: Request, user: AuthenticatedUserDep):
        return {
            "message": "secure data",
            "user": user,
            "state_token": getattr(request.state, "token", None),
        }

    return test_app


@pytest.mark.asyncio
async def test_auth_middleware_valid_bearer_token(auth_app):
    """Test accessing protected route with a valid bearer token."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/protected",
            headers={"Authorization": "Bearer valid-secret-token-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "secure data"
        assert data["user"] == {
            "authenticated": True,
            "token": "valid-secret-token-123",
        }
        assert data["state_token"] == "valid-secret-token-123"


@pytest.mark.asyncio
async def test_auth_middleware_missing_header(auth_app):
    """Test accessing protected route without Authorization header."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/protected")

        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "Missing Authorization header" in data["detail"]


@pytest.mark.asyncio
async def test_auth_middleware_invalid_scheme(auth_app):
    """Test accessing protected route with non-Bearer scheme."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/protected",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "Invalid authentication scheme" in data["detail"]


@pytest.mark.asyncio
async def test_auth_middleware_wrong_token(auth_app):
    """Test accessing protected route with wrong bearer token."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/protected",
            headers={"Authorization": "Bearer wrong-token-xyz"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Unauthorized"
        assert "Invalid or expired token" in data["detail"]


@pytest.mark.asyncio
async def test_auth_middleware_excluded_paths(auth_app):
    """Test that whitelisted / public paths bypass authentication."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app), base_url="http://test"
    ) as client:
        res_ping = await client.get("/api/v1/ping")
        assert res_ping.status_code == 200
        assert res_ping.json() == {"status": "pong"}

        res_public = await client.get("/public")
        assert res_public.status_code == 200
        assert res_public.json() == {"status": "public ok"}


@pytest.mark.asyncio
async def test_auth_middleware_disabled():
    """Test that when auth is disabled, all requests pass through."""
    disabled_app = FastAPI()
    disabled_app.add_middleware(
        BearerTokenAuthMiddleware,
        enabled=False,
        secret_token="some-token",
    )

    @disabled_app.get("/api/v1/data")
    async def get_data():
        return {"result": "success"}

    async with AsyncClient(
        transport=ASGITransport(app=disabled_app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/data")
        assert response.status_code == 200
        assert response.json() == {"result": "success"}


@pytest.mark.asyncio
async def test_auth_middleware_custom_verify_func():
    """Test with custom token verification function (e.g. JWT payload decoding)."""
    custom_app = FastAPI()

    def custom_verify(token: str):
        if token == "jwt.sample.token":
            return {"user_id": 42, "role": "admin", "sub": "john_doe"}
        return None

    custom_app.add_middleware(
        BearerTokenAuthMiddleware,
        enabled=True,
        verify_token_func=custom_verify,
        excluded_paths={"/docs"},
    )

    @custom_app.get("/profile")
    async def get_profile(user: AuthenticatedUserDep):
        return {"user": user}

    async with AsyncClient(
        transport=ASGITransport(app=custom_app), base_url="http://test"
    ) as client:
        # Valid custom token
        res_valid = await client.get(
            "/profile",
            headers={"Authorization": "Bearer jwt.sample.token"},
        )
        assert res_valid.status_code == 200
        assert res_valid.json() == {
            "user": {"user_id": 42, "role": "admin", "sub": "john_doe"}
        }

        # Invalid custom token
        res_invalid = await client.get(
            "/profile",
            headers={"Authorization": "Bearer invalid.jwt"},
        )
        assert res_invalid.status_code == 401


def test_helper_logging_functions(caplog):
    """Test log_request and log_error helper functions."""
    import logging

    with caplog.at_level(logging.INFO):
        log_request("GET", "/api/v1/ping")
        assert "GET /api/v1/ping" in caplog.text

    with caplog.at_level(logging.ERROR):
        log_error("Test failure", "POST", "/api/v1/ask")
        assert "Error in POST /api/v1/ask: Test failure" in caplog.text
