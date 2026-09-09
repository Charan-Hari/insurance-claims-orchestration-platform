import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from eventing_service.envelope import EventEnvelope


class Base(DeclarativeBase):
    pass


class OutboxEvent(Base):
    __tablename__ = "event_outbox"
    __table_args__ = (
        UniqueConstraint("producer", "idempotency_key", name="uq_event_outbox_idempotency"),
        Index("ix_event_outbox_delivery", "status", "available_at"),
        Index("ix_event_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    producer: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def append(self, session: AsyncSession, event: EventEnvelope) -> tuple[OutboxEvent, bool]:
        now = datetime.now(timezone.utc)
        values = event.model_dump(mode="json")
        values["event_id"] = event.event_id
        values["occurred_at"] = event.occurred_at
        values["event_metadata"] = values.pop("metadata")
        values["available_at"] = now
        statement = insert(OutboxEvent).values(
            **values, status="pending", attempts=0,
        ).on_conflict_do_nothing(constraint="uq_event_outbox_idempotency")
        result = await session.execute(statement.returning(OutboxEvent.event_id))
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            row = await session.get(OutboxEvent, inserted_id)
            assert row is not None
            return row, True
        row = await session.scalar(select(OutboxEvent).where(
            OutboxEvent.producer == event.producer,
            OutboxEvent.idempotency_key == event.idempotency_key,
        ))
        if row is None:
            raise RuntimeError("idempotency conflict could not be resolved")
        return row, False

    async def claim(self, session: AsyncSession, *, limit: int = 10, lock_seconds: int = 60) -> list[OutboxEvent]:
        now = datetime.now(timezone.utc)
        query = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "pending",
                OutboxEvent.available_at <= now,
                (OutboxEvent.locked_until.is_(None) | (OutboxEvent.locked_until < now)),
            )
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list((await session.scalars(query)).all())
        for row in rows:
            row.locked_until = datetime.fromtimestamp(now.timestamp() + lock_seconds, timezone.utc)
            row.attempts += 1
        return rows

    async def mark_published(self, session: AsyncSession, event_id: UUID) -> None:
        row = await session.get(OutboxEvent, event_id)
        if row:
            row.status, row.published_at, row.locked_until = "published", datetime.now(timezone.utc), None

    async def mark_retry(self, session: AsyncSession, event_id: UUID, error: str, delay_seconds: int) -> None:
        row = await session.get(OutboxEvent, event_id)
        if row:
            row.status = "pending"
            row.available_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + delay_seconds, timezone.utc)
            row.locked_until, row.last_error = None, error[:4000]


def database_url() -> str:
    return os.getenv("EVENTING_DATABASE_URL", "postgresql+asyncpg://policy_user:policy_dev_password@localhost:5432/policy_db")


def create_database():
    engine = create_async_engine(database_url(), pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
