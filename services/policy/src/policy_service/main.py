import logging
from time import perf_counter
import uuid

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import Response

from policy_service.api.routes import router
from policy_service.logging_config import configure_logging


logger = configure_logging()
app = FastAPI(title="Policy Service", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    started_at = perf_counter()
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            extra={
                    "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        raise

    logger.info(
        "request_completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
async def readiness() -> dict[str, str]:
    return {"status": "ready"}