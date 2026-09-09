from collections.abc import AsyncIterator, Iterator
from datetime import date
from decimal import Decimal
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from claims_service.auth.jwt import CurrentUser, get_current_user
from claims_service.db.base import Base
from claims_service.db.session import get_db_session
from claims_service.main import app
from claims_service.models import AuditRecord, Claim
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


async def seed_claim(session_factory: async_sessionmaker[AsyncSession], status: ClaimStatus) -> Claim:
    async with session_factory() as session:
        claim = Claim(
            policy_id=uuid.uuid4(),
            policyholder_id=uuid.uuid4(),
            claim_amount=Decimal("1250.00"),
            incident_date=date(2026, 1, 1),
            description="Water damage",
            status=status,
        )
        session.add(claim)
        await session.commit()
        await session.refresh(claim)
        return claim


def user(subject: str, role: str) -> CurrentUser:
    return CurrentUser(subject=subject, roles=frozenset({role}), claims={})


@pytest.mark.asyncio
async def test_claim_status_update_audits_valid_transitions_rejects_invalid_and_enforces_roles(
    integration_client: tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_factory = integration_client
    claim = await seed_claim(session_factory, ClaimStatus.SUBMITTED)

    for role in ("customer", "agent"):
        app.dependency_overrides[get_current_user] = lambda role=role: user(f"{role}-1", role)
        denied = await client.patch(f"/claims/{claim.id}/status", json={"status": "under_review"})
        assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: user("adjuster-1", "adjuster")
    valid = await client.patch(f"/claims/{claim.id}/status", json={"status": "under_review"})
    assert valid.status_code == 200
    assert valid.json()["status"] == "under_review"

    async with session_factory() as session:
        audit = (await session.execute(select(AuditRecord).where(AuditRecord.claim_id == claim.id))).scalars().all()
        assert len(audit) == 1
        assert audit[0].actor_id == "adjuster-1"
        assert audit[0].old_status is ClaimStatus.SUBMITTED
        assert audit[0].new_status is ClaimStatus.UNDER_REVIEW

    app.dependency_overrides[get_current_user] = lambda: user("admin-1", "admin")
    admin_update = await client.patch(f"/claims/{claim.id}/status", json={"status": "approved"})
    assert admin_update.status_code == 200

    invalid_claim = await seed_claim(session_factory, ClaimStatus.SUBMITTED)
    app.dependency_overrides[get_current_user] = lambda: user("adjuster-1", "adjuster")
    invalid = await client.patch(f"/claims/{invalid_claim.id}/status", json={"status": "paid"})
    assert invalid.status_code == 400
    assert "submitted -> paid" in invalid.json()["detail"]

    async with session_factory() as session:
        unchanged = await session.get(Claim, invalid_claim.id)
        audits = (await session.execute(select(AuditRecord).where(AuditRecord.claim_id == invalid_claim.id))).scalars().all()
        assert unchanged is not None
        assert unchanged.status is ClaimStatus.SUBMITTED
        assert audits == []