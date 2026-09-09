import asyncio
import logging
import os
from time import perf_counter
from typing import Any
import uuid

import httpx


logger = logging.getLogger("claims_service")
REQUEST_TIMEOUT_SECONDS = 2.0
MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 0.1


class PolicyNotFound(Exception):
    """Raised when the Policy Service returns 404."""


class PolicyNotActive(Exception):
    """Raised when the referenced policy is not active."""


class PolicyServiceUnavailable(Exception):
    """Raised when the Policy Service cannot be reached after retries."""


def _base_url() -> str:
    value = os.getenv("POLICY_SERVICE_BASE_URL")
    if not value:
        raise RuntimeError("POLICY_SERVICE_BASE_URL must be configured")
    return value.rstrip("/")


async def _request_policy(
    client: httpx.AsyncClient,
    policy_id: uuid.UUID,
    authorization: str | None,
) -> dict[str, Any]:
    headers = {"Authorization": authorization} if authorization else None
    url = f"{_base_url()}/policies/{policy_id}"
    started_at = perf_counter()
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 404:
                logger.info(
                    "policy_client_call",
                    extra={"target_service": "policy-service", "outcome": "not_found", "latency_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                raise PolicyNotFound(f"Policy {policy_id} was not found")
            response.raise_for_status()
            policy = response.json()
            if policy.get("status") != "active":
                logger.info(
                    "policy_client_call",
                    extra={"target_service": "policy-service", "outcome": "not_active", "latency_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                raise PolicyNotActive(f"Policy {policy_id} is not active")
            logger.info(
                "policy_client_call",
                extra={"target_service": "policy-service", "outcome": "success", "latency_ms": round((perf_counter() - started_at) * 1000, 2)},
            )
            return policy
        except (PolicyNotFound, PolicyNotActive):
            raise
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
            if attempt >= MAX_RETRIES:
                logger.warning(
                    "policy_client_call",
                    extra={"target_service": "policy-service", "outcome": "unavailable", "latency_ms": round((perf_counter() - started_at) * 1000, 2)},
                )
                raise PolicyServiceUnavailable("Policy Service is unavailable") from exc
            await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
        except httpx.HTTPStatusError as exc:
            if 500 <= exc.response.status_code < 600 and attempt < MAX_RETRIES:
                await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
                continue
            raise PolicyServiceUnavailable("Policy Service returned an unavailable response") from exc

    raise PolicyServiceUnavailable("Policy Service is unavailable")


async def get_policy(policy_id: uuid.UUID, authorization: str | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        return await _request_policy(client, policy_id, authorization)