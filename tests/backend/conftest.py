"""Shared fixtures: in-memory SQLite DB, test settings, authenticated clients.

The test environment uses the Fake LLM provider, local embeddings and the
in-memory vector store — the full stack runs deterministically with no network.
"""

import os

os.environ.update(
    ENVIRONMENT="test",
    SECRET_KEY="test-secret-key-for-ci-only-0123456789",
    DEFAULT_LLM_PROVIDER="fake",
    DEFAULT_LLM_MODEL="fake-model",
    FALLBACK_LLM_PROVIDER="fake",
    FALLBACK_LLM_MODEL="fake-model",
    DEFAULT_EMBEDDING_PROVIDER="local",
    EMBEDDING_DIMENSION="256",
    ADMIN_EMAIL="admin@test.local",
    ADMIN_PASSWORD="TestAdmin123!",
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.infrastructure.database.models import Base, OrganizationModel, UserModel
from app.infrastructure.database.session import get_db_session
from app.main import app


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(session_factory):
    async def override_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


async def _create_user(session_factory, email: str, role: str) -> None:
    async with session_factory() as session:
        org = OrganizationModel(name="Test Org", slug=f"org-{email.split('@')[0]}")
        session.add(org)
        await session.flush()
        session.add(
            UserModel(
                email=email,
                full_name="Test User",
                hashed_password=hash_password("Password123!"),
                role=role,
                organization_id=org.id,
            )
        )
        await session.commit()


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client, session_factory):
    await _create_user(session_factory, "admin@test.local", "platform_admin")
    return await _login(client, "admin@test.local")


@pytest.fixture
async def engineer_headers(client, session_factory):
    await _create_user(session_factory, "engineer@test.local", "engineer")
    return await _login(client, "engineer@test.local")


@pytest.fixture
async def viewer_headers(client, session_factory):
    await _create_user(session_factory, "viewer@test.local", "viewer")
    return await _login(client, "viewer@test.local")
