import logging
import time
import uuid

from fastapi import FastAPI, Request

from orchestrator.logging_config import configure_logging

from orchestrator.api.routes import router

configure_logging()
logger = logging.getLogger("orchestrator")
app = FastAPI(title="Orchestrator Service", version="0.1.0")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed", extra={"request_id": request_id, "method": request.method, "path": request.url.path, "status_code": response.status_code, "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
    return response
app.include_router(router)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
async def readiness() -> dict[str, str]:
    return {"status": "ready"}
