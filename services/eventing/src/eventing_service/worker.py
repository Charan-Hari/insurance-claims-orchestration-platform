import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from eventing_service.db import EventRepository

logger = logging.getLogger("eventing_service.worker")


class Publisher(Protocol):
    async def publish(self, event: object) -> None: ...


class OutboxWorker:
    """Delivery abstraction; callers provide Kafka, HTTP, or queue publishers."""

    def __init__(self, repository: EventRepository, publisher: Publisher, *, max_attempts: int = 10):
        self.repository, self.publisher, self.max_attempts = repository, publisher, max_attempts

    async def run_once(self, *, limit: int = 10) -> int:
        async with self.repository.session_factory() as session:
            async with session.begin():
                events = await self.repository.claim(session, limit=limit)
        delivered = 0
        for event in events:
            try:
                await self.publisher.publish(event)
            except Exception as exc:
                delay = min(300, 2 ** min(event.attempts, 8))
                async with self.repository.session_factory() as retry_session:
                    async with retry_session.begin():
                        await self.repository.mark_retry(retry_session, event.event_id, str(exc), delay)
                logger.warning("event_delivery_failed", extra={"event_id": str(event.event_id), "attempt": event.attempts})
            else:
                async with self.repository.session_factory() as publish_session:
                    async with publish_session.begin():
                        await self.repository.mark_published(publish_session, event.event_id)
                delivered += 1
                logger.info("event_delivered", extra={"event_id": str(event.event_id)})
        return delivered

    async def run_forever(self, stop: asyncio.Event, *, interval_seconds: float = 1.0) -> None:
        while not stop.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass
