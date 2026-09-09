import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from legacy_adapter.db.base import Base
from legacy_adapter.models.claim import LegacyClaim
from legacy_adapter.schemas.claim import LegacyClaimIn
from legacy_adapter.services.ingestion import ingest_claim


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as value:
        yield value
    await engine.dispose()


def record(**overrides):
    data = {
        "source_system": "mainframe", "legacy_claim_id": "C-1",
        "claim_amount": "100.00", "incident_date": "2026-01-01",
        "description": "Damage", "raw_payload": {"batch": "1"},
    }
    data.update(overrides)
    return LegacyClaimIn.model_validate(data)


@pytest.mark.asyncio
async def test_replay_is_idempotent(session):
    first, created = await ingest_claim(session, record())
    second, replayed = await ingest_claim(session, record())
    assert created is True
    assert replayed is False
    assert first.id == second.id
    assert await session.scalar(select(func.count()).select_from(LegacyClaim)) == 1


@pytest.mark.asyncio
async def test_conflicting_replay_is_rejected(session):
    await ingest_claim(session, record())
    with pytest.raises(ValueError, match="different content"):
        await ingest_claim(session, record(description="Changed"))
