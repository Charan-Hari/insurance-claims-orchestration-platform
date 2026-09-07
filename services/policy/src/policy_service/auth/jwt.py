from dataclasses import dataclass
import os
import time
from typing import Any, Callable

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt


bearer_scheme = HTTPBearer(auto_error=False)
JWKS_CACHE_TTL_SECONDS = 600
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass(frozen=True)
class CurrentUser:
    subject: str
    roles: frozenset[str]
    claims: dict[str, Any]


def _issuer() -> str:
    value = os.getenv("KEYCLOAK_ISSUER")
    if not value:
        raise RuntimeError("KEYCLOAK_ISSUER must be configured")
    return value.rstrip("/")


def _key_for_kid(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    return next((item for item in jwks.get("keys", []) if item.get("kid") == kid), None)


async def _get_jwks(issuer: str, kid: str | None) -> dict[str, Any]:
    now = time.monotonic()
    cached = _jwks_cache.get(issuer)
    if cached is not None:
        expires_at, jwks = cached
        if expires_at > now and _key_for_kid(jwks, kid) is not None:
            return jwks

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{issuer}/protocol/openid-connect/certs",
            timeout=5.0,
        )
        response.raise_for_status()
    jwks = response.json()
    _jwks_cache[issuer] = (now + JWKS_CACHE_TTL_SECONDS, jwks)
    return jwks


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    issuer = _issuer()
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        jwks = await _get_jwks(issuer, header.get("kid"))
        key = _key_for_kid(jwks, header.get("kid"))
        if key is None:
            raise JWTError("Signing key not found")
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=os.getenv("KEYCLOAK_AUDIENCE", "account"),
        )
    except (httpx.HTTPError, JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from exc

    realm_roles = claims.get("realm_access", {}).get("roles", [])
    direct_roles = claims.get("roles", [])
    roles = frozenset({*realm_roles, *direct_roles})
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    return CurrentUser(subject=subject, roles=roles, claims=claims)


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    async def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.roles.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return user

    return dependency