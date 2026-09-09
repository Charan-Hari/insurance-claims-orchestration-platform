import json
import logging
import uuid
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import Response

from legacy_adapter.api.routes import router

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }, separators=(",", ":"))


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("legacy_adapter")
logger.handlers.clear()
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
app = FastAPI(title="Legacy Adapter Service", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    response.headers["X-Request-ID"] = request_id
    logger.info("request_completed request_id=%s method=%s path=%s status=%s latency_ms=%.2f",
                request_id, request.method, request.url.path, response.status_code, (perf_counter() - started) * 1000)
    return response
