import asyncio
import os
import uuid
from typing import Any

import httpx


REQUEST_TIMEOUT_SECONDS = 2.0
MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 0.1


class PolicyNotFound(Exception):
    pass


class PolicyNotActive(Exception):
    pass


class PolicyServiceUnavailable(Exception):
    pass


def _base_url() -> str:
    value = os.getenv("POLICY_SERVICE_BASE_URL")
    if not value:
        raise RuntimeError("POLICY_SERVICE_BASE_URL must be configured")
    return value.rstrip("/")


async def get_policy(
    policy_id: uuid.UUID,
    authorization: str | None,
) -> dict[str, Any]:
    url = f"{_base_url()}/policies/{policy_id}"

    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": authorization} if authorization else None,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )

                if response.status_code == 404:
                    raise PolicyNotFound(f"Policy {policy_id} was not found")

                response.raise_for_status()
                policy = response.json()

                if policy.get("status") != "active":
                    raise PolicyNotActive(f"Policy {policy_id} is not active")

                return policy

            except (PolicyNotFound, PolicyNotActive):
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                if attempt >= MAX_RETRIES:
                    raise PolicyServiceUnavailable(
                        "Policy Service is unavailable"
                    ) from exc
                await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
            except httpx.HTTPStatusError as exc:
                if 500 <= exc.response.status_code < 600 and attempt < MAX_RETRIES:
                    await asyncio.sleep(INITIAL_BACKOFF_SECONDS * (2**attempt))
                    continue
                raise PolicyServiceUnavailable(
                    "Policy Service returned an unavailable response"
                ) from exc

    raise PolicyServiceUnavailable("Policy Service is unavailable")
