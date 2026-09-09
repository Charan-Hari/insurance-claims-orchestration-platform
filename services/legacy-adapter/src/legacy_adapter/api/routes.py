from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from legacy_adapter.auth.jwt import CurrentUser, require_ingestion_role
from legacy_adapter.db.session import get_db_session
from legacy_adapter.schemas.claim import LegacyClaimIn, LegacyClaimRead
from legacy_adapter.services.ingestion import ingest_claim

router = APIRouter()


@router.post("/legacy/claims", response_model=LegacyClaimRead, responses={409: {"description": "Conflicting duplicate"}})
async def ingest_legacy_claim(
    record: LegacyClaimIn,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(require_ingestion_role),
) -> LegacyClaimRead:
    try:
        claim, created = await ingest_claim(session, record)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return claim


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readiness", include_in_schema=False)
async def readiness(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}
