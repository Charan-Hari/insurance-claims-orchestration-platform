from collections.abc import AsyncIterator, Iterator
from datetime import date
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
from policy_service.models.policy import PolicyStatus


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


async def seed_policy(session_factory: async_sessionmaker[AsyncSession], policyholder_id: uuid.UUID) -> Policy:
    async with session_factory() as session:
        policy = Policy(
            policyholder_id=policyholder_id,
            coverage_type="property",
            coverage_limits={"dwelling": 250000},
            effective_date=date(2026, 10, 1),
            expiry_date=date(2027, 10, 1),
            status=PolicyStatus.DRAFT,
        )
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return policy


def user(subject: str, role: str) -> CurrentUser:
    return CurrentUser(subject=subject, roles=frozenset({role}), claims={})


@pytest.mark.asyncio
async def test_policy_retrieval_enforces_customer_ownership_and_elevated_access(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    own_holder = uuid.uuid4()
    other_holder = uuid.uuid4()
    own_policy = await seed_policy(session_factory, own_holder)
    other_policy = await seed_policy(session_factory, other_holder)

    app.dependency_overrides[get_current_user] = lambda: user(str(own_holder), "customer")
    assert (await client.get(f"/policies/{own_policy.id}")).status_code == 200
    assert (await client.get(f"/policies/{other_policy.id}")).status_code == 404
    assert (await client.get(f"/policyholders/{own_holder}/policies")).status_code == 200
    assert (await client.get(f"/policyholders/{other_holder}/policies")).status_code == 403

    for role in ("admin", "agent", "underwriter"):
        app.dependency_overrides[get_current_user] = lambda role=role: user(f"{role}-1", role)
        assert (await client.get(f"/policies/{other_policy.id}")).status_code == 200
        assert (await client.get(f"/policyholders/{other_holder}/policies")).status_code == 200

    app.dependency_overrides[get_current_user] = lambda: user("admin-1", "admin")
    missing = await client.get(f"/policies/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Policy not found"