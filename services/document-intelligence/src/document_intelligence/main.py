import logging
import uuid
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import Response

from .api import router
from .config import storage_path
from .db import initialize

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("document-intelligence")
app = FastAPI(title="Document Intelligence Service", version="0.1.0")
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    storage_path()
    initialize()


@app.middleware("http")
async def request_context(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed request_id=%s method=%s path=%s status=%s latency_ms=%.2f",
                request_id, request.method, request.url.path, response.status_code,
                (perf_counter() - started) * 1000)
    return response


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness", include_in_schema=False)
async def readiness() -> dict[str, str]:
    try:
        initialize()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}
