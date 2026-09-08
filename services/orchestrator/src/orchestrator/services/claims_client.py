import asyncio
import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx


REQUEST_TIMEOUT_SECONDS = 2.0
MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 0.1


class ClaimsServiceUnavailable(Exception):
    pass


class ClaimsServiceRejected(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _base_url() -> str:
    value = os.getenv("CLAIMS_SERVICE_BASE_URL")
    if not value:
        raise RuntimeError("CLAIMS_SERVICE_BASE_URL must be configured")
    return value.rstrip("/")


async def create_claim(
    *,
    policy_id: uuid.UUID,
    policyholder_id: uuid.UUID,
    claim_amount: Decimal,
    incident_date: date,
    description: str,
    adjuster_notes: str | None,
    authorization: str | None,
    idempotency_key: str,
) -> dict[str, Any]:
    payload = {
        "policy_id": str(policy_id),
        "policyholder_id": str(policyholder_id),
        "claim_amount": str(claim_amount),
        "incident_date": incident_date.isoformat(),
        "description": description,
        "adjuster_notes": adjuster_notes,
    }
    headers = {
        "Idempotency-Key": idempotency_key,
    }
    if authorization:
        headers["Authorization"] = authorization

    url = f"{_base_url()}/claims"

    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code in {400, 403, 409}:
                    raise ClaimsServiceRejected(
                        response.status_code,
                        response.json(),
                    )

                response.raise_for_status()
                return response.json()

            except ClaimsServiceRejected:
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                if attempt >= MAX_RETRIES:
                    raise ClaimsServiceUnavailable(
                        "Claims Service is unavailable"
                    ) from exc
                await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
            except httpx.HTTPStatusError as exc:
                if 500 <= exc.response.status_code < 600 and attempt < MAX_RETRIES:
                    await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise ClaimsServiceUnavailable(
                    "Claims Service returned an unavailable response"
                ) from exc

    raise ClaimsServiceUnavailable("Claims Service is unavailable")
