from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    _structured_fields = (
		"request_id",
        "method",
        "path",
        "status_code",
        "latency_ms",
        "actor_id",
        "action",
        "policy_id",
        "old_status",
        "new_status",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._structured_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
