import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from auth_service.db.models.base import Base
from auth_service.db.models.refresh_sessions import RefreshSession
from auth_service.db.models.users import User, UserRole, UserStatus
from auth_service.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
    UserBlockedError,
)
from auth_service.repositories.refresh_sessions import RefreshSessionRepository
from auth_service.repositories.users import UserRepository
from auth_service.schemas.users import UserRegister
from auth_service.security.passwords import PasswordHasher
from auth_service.security.refresh_tokens import hash_refresh_token
from auth_service.services.authentication import AuthenticationService
from auth_service.services.refresh import RefreshService
from auth_service.services.register import RegistrationService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session():
    raw_url = os.environ.get("AUTH_TEST_DATABASE_URL")
    if raw_url is None:
        pytest.skip("Set AUTH_TEST_DATABASE_URL to a dedicated PostgreSQL *_test database")

    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("AUTH_TEST_DATABASE_URL must point to a dedicated PostgreSQL *_test DB")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with engine.connect() as connection:
            outer_transaction = await connection.begin()
            session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                yield session
            finally:
                await session.close()
                await outer_transaction.rollback()
    finally:
        await engine.dispose()


async def seeded_session(
    db_session: AsyncSession, *, expired: bool = False
) -> tuple[User, RefreshSession, str]:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        password_hash="not-used-in-refresh-tests",
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    raw_token = "test-refresh-" + str(uuid4())
    old_session = RefreshSession(
        id=uuid4(),
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        family_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=-1 if expired else 30),
    )
    async with db_session.begin():
        await UserRepository(db_session).add(user)
        await RefreshSessionRepository(db_session).add(old_session)
    return user, old_session, raw_token


def refresh_service(db_session: AsyncSession) -> RefreshService:
    token_service = SimpleNamespace(create_access_token=Mock(return_value="test-access-token"))
    return RefreshService(
        session=db_session,
        refresh_repository=RefreshSessionRepository(db_session),
        user_repository=UserRepository(db_session),
        token_service=token_service,
        access_token_expire_minutes=15,
    )


async def test_rotation_revokes_old_and_preserves_family(db_session: AsyncSession) -> None:
    user, old_session, raw_token = await seeded_session(db_session)

    issued = await refresh_service(db_session).refresh(raw_token)

    async with db_session.begin():
        old = await RefreshSessionRepository(db_session).get_by_token_hash_for_update(
            old_session.token_hash
        )
        new = await RefreshSessionRepository(db_session).get_by_token_hash_for_update(
            hash_refresh_token(issued.refresh_token)
        )

    assert issued.token_response.access_token == "test-access-token"
    assert issued.token_response.expires_in == 900
    assert old.revoked_at is not None
    assert old.replaced_by_session_id == new.id
    assert new.user_id == user.id
    assert new.family_id == old.family_id
    assert new.expires_at == old.expires_at
    assert new.revoked_at is None


async def test_reused_old_token_revokes_current_family(db_session: AsyncSession) -> None:
    _, old_session, raw_token = await seeded_session(db_session)
    issued = await refresh_service(db_session).refresh(raw_token)

    with pytest.raises(RefreshTokenReuseError):
        await refresh_service(db_session).refresh(raw_token)

    async with db_session.begin():
        descendant = await RefreshSessionRepository(db_session).get_by_token_hash_for_update(
            hash_refresh_token(issued.refresh_token)
        )
    assert descendant.family_id == old_session.family_id
    assert descendant.revoked_at is not None


async def test_expired_refresh_token_cannot_rotate(db_session: AsyncSession) -> None:
    _, old_session, raw_token = await seeded_session(db_session, expired=True)
    old_token_hash = old_session.token_hash

    with pytest.raises(InvalidRefreshTokenError):
        await refresh_service(db_session).refresh(raw_token)

    async with db_session.begin():
        unchanged = await RefreshSessionRepository(db_session).get_by_token_hash_for_update(
            old_token_hash
        )
    assert unchanged.revoked_at is None
    assert unchanged.replaced_by_session_id is None


async def test_registration_normalizes_email_and_rejects_duplicate(
    db_session: AsyncSession,
) -> None:
    email = f"{uuid4()}@example.com"
    hasher = PasswordHasher()
    service = RegistrationService(db_session, UserRepository(db_session), hasher)
    registration = UserRegister(
        email=email.upper(), password="password12345", repeat_password="password12345"
    )

    user = await service.register(registration)

    assert user.email == email
    assert hasher.verify("password12345", user.password_hash)
    with pytest.raises(EmailAlreadyRegisteredError):
        await service.register(registration)


async def test_wrong_password_is_rejected(db_session: AsyncSession) -> None:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        password_hash=PasswordHasher().hash("correct12345"),
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
    )
    async with db_session.begin():
        await UserRepository(db_session).add(user)
    service = AuthenticationService(db_session, UserRepository(db_session), PasswordHasher())

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate(email=user.email, password="wrong12345")

async def test_blocked_user_cannot_refresh(
    db_session: AsyncSession,
) -> None:
    user, old_session, raw_token = await seeded_session(db_session)

    async with db_session.begin():
        user.status = UserStatus.BLOCKED

    with pytest.raises(UserBlockedError):
        await refresh_service(db_session).refresh(raw_token)

    async with db_session.begin():
        stored = await RefreshSessionRepository(
            db_session
        ).get_by_token_hash_for_update(old_session.token_hash)

    assert stored.revoked_at is not None
    assert stored.replaced_by_session_id is None