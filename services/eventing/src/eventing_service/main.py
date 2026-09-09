import logging
import json
import sys
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from eventing_service.db import Base, EventRepository, create_database
from eventing_service.envelope import EventEnvelope

engine, session_factory = create_database()
repository = EventRepository(session_factory)
logger = logging.getLogger("eventing_service")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }, separators=(",", ":"))


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Platform Eventing", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_logging(request: Request, call_next) -> Response:
    started = perf_counter()
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    response = await call_next(request)
    logger.info("request_completed request_id=%s method=%s path=%s status=%s latency_ms=%.2f",
                request_id, request.method, request.url.path, response.status_code,
                (perf_counter() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
async def readiness() -> JSONResponse:
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return JSONResponse({"status": "ready"})


@app.post("/events", status_code=201)
async def append_event(event: EventEnvelope) -> dict:
    async with session_factory() as session:
        async with session.begin():
            row, inserted = await repository.append(session, event)
    return {"event_id": str(row.event_id), "accepted": inserted, "status": row.status}
