from collections.abc import AsyncIterator, Iterator
from datetime import date
from decimal import Decimal
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from claims_service.auth.jwt import CurrentUser, get_current_user
from claims_service.db.base import Base
from claims_service.db.session import get_db_session
from claims_service.main import app
from claims_service.models import Claim
from claims_service.models.claim import ClaimStatus


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


async def seed_claim(session_factory: async_sessionmaker[AsyncSession], policyholder_id: uuid.UUID) -> Claim:
    async with session_factory() as session:
        claim = Claim(
            policy_id=uuid.uuid4(),
            policyholder_id=policyholder_id,
            claim_amount=Decimal("1250.00"),
            incident_date=date(2026, 1, 1),
            description="Water damage",
            status=ClaimStatus.SUBMITTED,
        )
        session.add(claim)
        await session.commit()
        await session.refresh(claim)
        return claim


def user(subject: str, role: str) -> CurrentUser:
    return CurrentUser(subject=subject, roles=frozenset({role}), claims={})


@pytest.mark.asyncio
async def test_claim_retrieval_enforces_customer_ownership_and_elevated_access(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    own_holder = uuid.uuid4()
    other_holder = uuid.uuid4()
    own_claim = await seed_claim(session_factory, own_holder)
    other_claim = await seed_claim(session_factory, other_holder)

    app.dependency_overrides[get_current_user] = lambda: user(str(own_holder), "customer")
    assert (await client.get(f"/claims/{own_claim.id}")).status_code == 200
    assert (await client.get(f"/claims/{other_claim.id}")).status_code == 404
    assert (await client.get(f"/policyholders/{own_holder}/claims")).status_code == 200
    assert (await client.get(f"/policyholders/{other_holder}/claims")).status_code == 404

    for role in ("admin", "agent", "adjuster"):
        app.dependency_overrides[get_current_user] = lambda role=role: user(f"{role}-1", role)
        assert (await client.get(f"/claims/{other_claim.id}")).status_code == 200
        assert (await client.get(f"/policyholders/{other_holder}/claims")).status_code == 200

    app.dependency_overrides[get_current_user] = lambda: user("admin-1", "admin")
    missing = await client.get(f"/claims/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Claim not found"