import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

bearer_scheme = HTTPBearer(auto_error=False)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass(frozen=True)
class CurrentUser:
    subject: str
    roles: frozenset[str]


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    issuer = os.getenv("KEYCLOAK_ISSUER")
    if not issuer:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    issuer = issuer.rstrip("/")
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        cached = _cache.get(issuer)
        if not cached or cached[0] <= time.monotonic() or not any(k.get("kid") == header.get("kid") for k in cached[1].get("keys", [])):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{issuer}/protocol/openid-connect/certs", timeout=5)
                response.raise_for_status()
            _cache[issuer] = (time.monotonic() + 600, response.json())
        jwks = _cache[issuer][1]
        key = next((item for item in jwks.get("keys", []) if item.get("kid") == header.get("kid")), None)
        if key is None:
            raise JWTError("unknown key")
        claims = jwt.decode(credentials.credentials, key, algorithms=["RS256"], issuer=issuer,
                            audience=os.getenv("KEYCLOAK_AUDIENCE", "account"))
        subject = claims.get("sub")
        if not subject:
            raise JWTError("missing subject")
    except (httpx.HTTPError, JWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc
    roles = frozenset({*claims.get("roles", []), *claims.get("realm_access", {}).get("roles", [])})
    return CurrentUser(subject=subject, roles=roles)


def require_ingestion_role(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    allowed = set(filter(None, os.getenv("LEGACY_ADAPTER_ROLES", "agent,admin,legacy-adapter").split(",")))
    if not user.roles.intersection(allowed):
        raise HTTPException(status_code=403, detail="Access denied")
    return user
