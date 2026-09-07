from collections.abc import AsyncIterator, Iterator
from datetime import date
from decimal import Decimal
import uuid
from unittest.mock import AsyncMock, patch

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
from claims_service.services.policy_client import PolicyNotActive, PolicyNotFound, PolicyServiceUnavailable


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


def payload() -> dict[str, object]:
    return {
        "policy_id": str(uuid.uuid4()),
        "policyholder_id": str(uuid.uuid4()),
        "claim_amount": "1250.00",
        "incident_date": str(date.today()),
        "description": "Water damage",
    }


def user(role: str) -> CurrentUser:
    return CurrentUser(subject=f"{role}-1", roles=frozenset({role}), claims={})


@pytest.mark.asyncio
async def test_file_claim_requires_roles_verifies_policy_and_maps_dependency_errors(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    active_policy = AsyncMock(return_value={"status": "active"})
    app.dependency_overrides[get_current_user] = lambda: user("agent")

    with patch("claims_service.services.claim_service.policy_client.get_policy", active_policy):
        created = await client.post(
            "/claims",
            json=payload(),
            headers={"Authorization": "Bearer agent-token"},
        )
    assert created.status_code == 201
    assert created.json()["status"] == "submitted"
    active_policy.assert_awaited_once()
    assert active_policy.await_args.args[1] == "Bearer agent-token"

    async with session_factory() as session:
        persisted = await session.get(Claim, uuid.UUID(created.json()["id"]))
        assert persisted is not None
        assert persisted.status.value == "submitted"

    app.dependency_overrides[get_current_user] = lambda: user("customer")
    with patch("claims_service.services.claim_service.policy_client.get_policy", active_policy):
        denied = await client.post("/claims", json=payload(), headers={"Authorization": "Bearer customer-token"})
    assert denied.status_code == 403

    for error, expected_status in (
        (PolicyNotActive(), 400),
        (PolicyNotFound(), 400),
        (PolicyServiceUnavailable(), 503),
    ):
        app.dependency_overrides[get_current_user] = lambda: user("agent")
        with patch(
            "claims_service.services.claim_service.policy_client.get_policy",
            AsyncMock(side_effect=error),
        ):
            response = await client.post("/claims", json=payload(), headers={"Authorization": "Bearer agent-token"})
        assert response.status_code == expected_status
