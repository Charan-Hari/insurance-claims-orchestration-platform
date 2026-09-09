from dataclasses import dataclass
from fastapi import Header, HTTPException, status

from .config import api_key


@dataclass(frozen=True)
class Principal:
    subject: str


async def require_auth(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> Principal:
    supplied = x_api_key
    if supplied is None and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or supplied != api_key():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    return Principal(subject="api-client")
