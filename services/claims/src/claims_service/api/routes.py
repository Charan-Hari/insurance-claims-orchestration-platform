import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from claims_service.auth.jwt import CurrentUser, bearer_scheme, require_roles
from claims_service.db.session import get_db_session
from claims_service.schemas.claim import ClaimCreate, ClaimRead, ClaimStatusUpdate
from claims_service.services.claim_service import (
    IdempotencyConflict,
    InvalidStatusTransition,
    can_view_claim,
    can_view_policyholder,
    create_claim,
    get_claim_by_id,
    list_claims_for_policyholder,
    update_claim_status,
)
from claims_service.services.policy_client import (
    PolicyNotActive,
    PolicyNotFound,
    PolicyServiceUnavailable,
)


router = APIRouter()
create_claim_authorization = require_roles("agent", "adjuster")


@router.post(
    "/claims",
    response_model=ClaimRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Policy validation or idempotency-key validation failed"},
        403: {"description": "Access denied"},
        409: {"description": "Idempotency-Key conflict"},
        503: {"description": "Policy Service unavailable"},
    },
)
async def create_claim_endpoint(
    claim_data: ClaimCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(create_claim_authorization),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ClaimRead:
    if idempotency_key is None or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    authorization = None
    if credentials is not None:
        authorization = f"{credentials.scheme} {credentials.credentials}"

    try:
        return await create_claim(
            session,
            claim_data,
            authorization,
            current_user.subject,
            idempotency_key,
        )
    except (PolicyNotFound, PolicyNotActive) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PolicyServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


retrieve_claim_authorization = require_roles("customer", "admin", "agent", "adjuster")


@router.get("/claims/{claim_id}", response_model=ClaimRead)
async def get_claim_endpoint(
    claim_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(retrieve_claim_authorization),
) -> ClaimRead:
    claim = await get_claim_by_id(session, claim_id)
    if claim is None or not can_view_claim(claim, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


@router.get("/policyholders/{policyholder_id}/claims", response_model=list[ClaimRead])
async def list_claims_endpoint(
    policyholder_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(retrieve_claim_authorization),
) -> list[ClaimRead]:
    if not can_view_policyholder(policyholder_id, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return await list_claims_for_policyholder(session, policyholder_id)


update_status_authorization = require_roles("adjuster", "admin")


@router.patch(
    "/claims/{claim_id}/status",
    response_model=ClaimRead,
    responses={
        400: {"description": "Invalid status transition"},
        403: {"description": "Access denied"},
        404: {"description": "Claim not found"},
    },
)
async def update_claim_status_endpoint(
    claim_id: uuid.UUID,
    status_update: ClaimStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: CurrentUser = Depends(update_status_authorization),
) -> ClaimRead:
    try:
        claim = await update_claim_status(session, claim_id, status_update.status, current_user.subject)
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim
