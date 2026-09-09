from collections.abc import AsyncIterator, Iterator
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from policy_service.auth.jwt import CurrentUser, get_current_user
from policy_service.db.base import Base
from policy_service.db.session import get_db_session
from policy_service.main import app
from policy_service.models import Policy


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16") as postgres:
        yield postgres.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest_asyncio.fixture
async def integration_client(postgres_url: str) -> AsyncIterator[tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine(postgres_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def create_payload() -> dict[str, object]:
    return {
        "policyholder_id": str(uuid.uuid4()),
        "coverage_type": "property",
        "coverage_limits": {"dwelling": 250000},
        "effective_date": "2026-10-01",
        "expiry_date": "2027-10-01",
        "premium_amount": "1200.00",
    }


@pytest.mark.asyncio
async def test_agent_creates_policy_in_draft_and_customer_is_denied(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="agent-1", roles=frozenset({"agent"}), claims={}
    )

    created = await client.post("/policies", json=create_payload())

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"

    async with session_factory() as session:
        policy = await session.get(Policy, uuid.UUID(body["id"]))
        assert policy is not None
        assert policy.status.value == "draft"

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="customer-1", roles=frozenset({"customer"}), claims={}
    )
    denied = await client.post("/policies", json=create_payload())

    assert denied.status_code == 403
    assert denied.json()["detail"] == "Access denied"