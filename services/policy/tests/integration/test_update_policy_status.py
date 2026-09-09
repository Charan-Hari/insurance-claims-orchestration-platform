from collections.abc import AsyncIterator, Iterator
from datetime import date
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from policy_service.auth.jwt import CurrentUser, get_current_user
from policy_service.db.base import Base
from policy_service.db.session import get_db_session
from policy_service.main import app
from policy_service.models import AuditRecord, Policy
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


async def seed_policy(
    session_factory: async_sessionmaker[AsyncSession], status: PolicyStatus
) -> Policy:
    async with session_factory() as session:
        policy = Policy(
            policyholder_id=uuid.uuid4(),
            coverage_type="property",
            coverage_limits={"dwelling": 250000},
            effective_date=date(2026, 10, 1),
            expiry_date=date(2027, 10, 1),
            status=status,
        )
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return policy


def user(subject: str, role: str) -> CurrentUser:
    return CurrentUser(subject=subject, roles=frozenset({role}), claims={})


@pytest.mark.asyncio
async def test_status_update_audits_valid_transitions_rejects_invalid_and_enforces_roles(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    policy = await seed_policy(session_factory, PolicyStatus.DRAFT)

    app.dependency_overrides[get_current_user] = lambda: user("customer-1", "customer")
    assert (await client.patch(f"/policies/{policy.id}/status", json={"status": "pending_underwriting"})).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: user("agent-1", "agent")
    assert (await client.patch(f"/policies/{policy.id}/status", json={"status": "pending_underwriting"})).status_code == 403

    app.dependency_overrides[get_current_user] = lambda: user("underwriter-1", "underwriter")
    valid = await client.patch(f"/policies/{policy.id}/status", json={"status": "pending_underwriting"})
    assert valid.status_code == 200
    assert valid.json()["status"] == "pending_underwriting"

    async with session_factory() as session:
        audit = (await session.execute(select(AuditRecord).where(AuditRecord.policy_id == policy.id))).scalars().all()
        assert len(audit) == 1
        assert audit[0].actor_id == "underwriter-1"
        assert audit[0].old_status is PolicyStatus.DRAFT
        assert audit[0].new_status is PolicyStatus.PENDING_UNDERWRITING

    app.dependency_overrides[get_current_user] = lambda: user("admin-1", "admin")
    admin_update = await client.patch(f"/policies/{policy.id}/status", json={"status": "active"})
    assert admin_update.status_code == 200

    invalid_policy = await seed_policy(session_factory, PolicyStatus.ACTIVE)
    app.dependency_overrides[get_current_user] = lambda: user("underwriter-1", "underwriter")
    invalid = await client.patch(f"/policies/{invalid_policy.id}/status", json={"status": "draft"})
    assert invalid.status_code == 400
    assert "active -> draft" in invalid.json()["detail"]

    async with session_factory() as session:
        unchanged = await session.get(Policy, invalid_policy.id)
        audits = (
            await session.execute(select(AuditRecord).where(AuditRecord.policy_id == invalid_policy.id))
        ).scalars().all()
        assert unchanged is not None
        assert unchanged.status is PolicyStatus.ACTIVE
        assert audits == []