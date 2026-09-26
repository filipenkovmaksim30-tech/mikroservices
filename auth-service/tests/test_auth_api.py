from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from auth_service.api import app
from auth_service.db.models.users import User, UserRole, UserStatus
from auth_service.routers.dependencies import get_current_user
from auth_service.routers.logout import get_logout_service


@pytest.fixture
def isolated_app():
    app.dependency_overrides.clear()
    yield app
    app.dependency_overrides.clear()


async def test_me_returns_current_user_without_password_hash(isolated_app: object) -> None:
    user = User(
        id=uuid4(),
        email="buyer@example.com",
        password_hash="must-not-leak",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == "buyer@example.com"
    assert "password_hash" not in response.json()


async def test_logout_revokes_cookie_session_and_clears_cookie(isolated_app: object) -> None:
    service = SimpleNamespace(logout=AsyncMock())
    app.dependency_overrides[get_logout_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies={"refresh_token": "test-refresh"},
    ) as client:
        response = await client.post("/auth/logout")

    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Path=/api/auth" in response.headers["set-cookie"]
    service.logout.assert_awaited_once_with("test-refresh")


async def test_logout_without_cookie_is_still_idempotent(isolated_app: object) -> None:
    service = SimpleNamespace(logout=AsyncMock())
    app.dependency_overrides[get_logout_service] = lambda: service

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/logout")

    assert response.status_code == 204
    service.logout.assert_not_awaited()
